from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Document, ProcessingTask, DocumentReview, Workflow, WorkflowExecution, AudioTranscription
from app.services.minio_client import minio_client
from app.services.workflow import process_task_background
from app.core.config import get_settings
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
import uuid
import os
from urllib.parse import quote
import httpx
import json

router = APIRouter()
settings = get_settings()

class TaskCreate(BaseModel):
    task_type: str
    content_file_ids: list[str]
    template_file_id: str | None = None
    preset_template: str | None = None
    requirements: str | None = None
    ai_model: str | None = None

class TaskResponse(BaseModel):
    task_id: str
    status: str

class DocumentResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    is_template: bool
    created_at: str | None = None
    size: int | None = None

class TaskListItem(BaseModel):
    task_id: str
    task_type: str
    status: str
    requirements: str | None = None
    content_file_ids: list[str]
    template_file_id: str | None = None
    result_file_id: str | None = None
    error: str | None = None
    created_at: str | None = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] | None = None
    file_ids: list[str] | None = None
    template_file_id: str | None = None
    template_text: str | None = None
    preset_template: str | None = None
    model: str | None = None

class ChatResponse(BaseModel):
    reply: str

class ModifyRequest(BaseModel):
    file_id: str
    modifications: str
    ai_model: str | None = None


def _resolve_chat_completions_url() -> str:
    """解析 AI API URL，支持完整路径或基础路径"""
    url = (settings.AI_API_BASE_URL or "").strip()
    if not url:
        raise HTTPException(status_code=500, detail="AI_API_BASE_URL 未配置")
    # 如果已经是完整的 chat/completions 路径，直接返回
    if "/chat/completions" in url:
        return url
    # 否则追加路径
    return url.rstrip("/") + "/chat/completions"


def _resolve_model(requested_model: str | None) -> str:
    model = (requested_model or settings.AI_MODEL_NAME or "").strip()
    return model or "minimaxai/minimax-m2.1"

@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    is_template: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    file_content = await file.read()
    file_ext = os.path.splitext(file.filename)[1]
    storage_filename = f"{uuid.uuid4()}{file_ext}"
    
    minio_path = minio_client.upload_file(
        file_content, 
        storage_filename, 
        file.content_type
    )
    
    new_doc = Document(
        id=uuid.uuid4(),
        user_id=None,
        filename=file.filename,
        file_size=len(file_content),
        mime_type=file.content_type,
        minio_path=minio_path,
        status="uploaded",
        is_template=bool(is_template)
    )
    
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    
    return {
        "fileId": str(new_doc.id),
        "filename": new_doc.filename,
        "status": new_doc.status,
        "size": new_doc.file_size
    }

@router.post("/files/upload-batch")
async def upload_batch(
    content_files: list[UploadFile] = File([]),
    template_file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db)
):
    uploaded: list[dict] = []

    async def _save_one(up: UploadFile, is_template: bool):
        data = await up.read()
        ext = os.path.splitext(up.filename)[1]
        storage_filename = f"{uuid.uuid4()}{ext}"
        minio_path = minio_client.upload_file(data, storage_filename, up.content_type)
        doc = Document(
            id=uuid.uuid4(),
            user_id=None,
            filename=up.filename,
            file_size=len(data),
            mime_type=up.content_type,
            minio_path=minio_path,
            status="uploaded",
            is_template=is_template
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return {"fileId": str(doc.id), "filename": doc.filename, "status": doc.status, "isTemplate": doc.is_template}

    for f in content_files:
        uploaded.append(await _save_one(f, False))

    template_uploaded = None
    if template_file is not None:
        template_uploaded = await _save_one(template_file, True)

    return {"content": uploaded, "template": template_uploaded}

@router.post("/tasks/create")
async def create_task(
    task_in: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    new_task = ProcessingTask(
        id=uuid.uuid4(),
        user_id=None,
        task_type=task_in.task_type,
        content_file_ids=[uuid.UUID(fid) for fid in task_in.content_file_ids],
        template_file_id=uuid.UUID(task_in.template_file_id) if task_in.template_file_id else None,
        requirements=task_in.requirements,
        ai_model=task_in.ai_model,
        status="pending"
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    background_tasks.add_task(process_task_background, str(new_task.id), task_in.preset_template, None, task_in.ai_model)
    
    return TaskResponse(task_id=str(new_task.id), status=new_task.status)

@router.post("/tasks/modify")
async def modify_document(
    req: ModifyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    new_task = ProcessingTask(
        id=uuid.uuid4(),
        user_id=None,
        task_type="modify_document",
        content_file_ids=[uuid.UUID(req.file_id)],
        requirements=req.modifications,
        ai_model=req.ai_model,
        status="pending"
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    background_tasks.add_task(process_task_background, str(new_task.id), None, req.modifications, req.ai_model)
    
    return TaskResponse(task_id=str(new_task.id), status=new_task.status)

@router.get("/files", response_model=list[DocumentResponse])
async def list_files(db: AsyncSession = Depends(get_db)):
    stmt = select(Document).order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [
        DocumentResponse(
            file_id=str(d.id),
            filename=d.filename,
            status=d.status,
            is_template=bool(d.is_template),
            created_at=d.created_at.isoformat() if d.created_at else None,
            size=d.file_size
        )
        for d in docs
    ]

@router.get("/tasks", response_model=list[TaskListItem])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    stmt = select(ProcessingTask).order_by(ProcessingTask.created_at.desc())
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [
        TaskListItem(
            task_id=str(t.id),
            task_type=t.task_type,
            status=t.status,
            requirements=t.requirements,
            content_file_ids=[str(fid) for fid in (t.content_file_ids or [])],
            template_file_id=str(t.template_file_id) if t.template_file_id else None,
            result_file_id=str(t.result_file_id) if t.result_file_id else None,
            error=t.error_message,
            created_at=t.created_at.isoformat() if t.created_at else None
        )
        for t in tasks
    ]

@router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(payload: ChatRequest):
    if not settings.AI_API_KEY:
        raise HTTPException(status_code=500, detail="AI_API_KEY 未配置")

    url = _resolve_chat_completions_url()
    model = _resolve_model(payload.model)

    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="message 不能为空")

    prompt = user_text
    if payload.file_ids:
        file_ids_text = ", ".join(payload.file_ids)
        template_text = payload.template_file_id or payload.preset_template or "无"
        prompt = f"内容文档ID：{file_ids_text}\n模板文档ID：{template_text}\n用户需求：{user_text}\n请用中文给出可执行的处理方案与结果预期。"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"AI 调用失败: {resp.status_code}: {resp.text}")
        data = resp.json()
        try:
            reply = data["choices"][0]["message"]["content"]
        except Exception:
            raise HTTPException(status_code=502, detail=f"AI 返回格式异常: {data}")
    return ChatResponse(reply=reply)

@router.post("/ai/chat/stream")
async def ai_chat_stream(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    """流式聊天接口，支持SSE"""
    if not settings.AI_API_KEY:
        raise HTTPException(status_code=500, detail="AI_API_KEY 未配置")

    url = _resolve_chat_completions_url()
    model = _resolve_model(payload.model)

    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="message 不能为空")

    async def generate():
        yield f"data: {json.dumps({'type': 'thinking', 'content': '正在思考...'}, ensure_ascii=False)}\n\n"
        try:
            async def _extract_via_mcp(file_id: str) -> str:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "http://mcp-server:3000/api/tools/content_extractor/invoke",
                        json={"file_id": file_id, "format": "markdown"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return (data.get("content") or "").strip()
                    return f"内容提取失败（HTTP {resp.status_code}）：{(resp.text or '')[:200]}"

            async def _condense_template_text(template_raw: str) -> str:
                text = (template_raw or "").strip()
                if not text:
                    return ""
                if len(text) <= 12000:
                    return text
                prompt = (
                    "请将下面“模板描述”整理为一个可执行的输出模板（用于总结/结构化输出），要求：\n"
                    "1) 输出为分级要点（1./1.1/1.2...）；2) 保留字段名、顺序、约束；3) 不要编造；4) 尽量压缩在 1500 字以内。\n\n"
                    f"{text}"
                )
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
                        json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
                    )
                    if resp.status_code >= 400:
                        return text[:12000]
                    data = resp.json()
                    try:
                        return (data["choices"][0]["message"]["content"] or "").strip()
                    except Exception:
                        return text[:12000]

            file_contents: list[str] = []
            if payload.file_ids:
                for file_id in payload.file_ids:
                    try:
                        content = await _extract_via_mcp(file_id)
                        if content:
                            file_contents.append(f"【文档内容】:\n{content}")
                    except Exception as e:
                        file_contents.append(f"【文档 {file_id}】: 内容提取失败 - {str(e)}")

            template_spec_blocks: list[str] = []
            if payload.preset_template:
                template_spec_blocks.append(f"【模板类型】{payload.preset_template}")

            if payload.template_file_id:
                try:
                    tcontent = await _extract_via_mcp(payload.template_file_id)
                    if tcontent:
                        tcontent = await _condense_template_text(tcontent)
                        template_spec_blocks.append(f"【模板文件内容】\n{tcontent}")
                    else:
                        template_spec_blocks.append("【模板文件内容】获取失败或为空")
                except Exception as e:
                    template_spec_blocks.append(f"【模板文件内容】提取失败：{str(e)}")

            if payload.template_text:
                ttext = await _condense_template_text(payload.template_text)
                if ttext:
                    template_spec_blocks.append(f"【模板描述文本】\n{ttext}")

            messages: list[dict] = []
            system_content = (
                "你是一个智能文档助手。请根据用户提供的文档内容与模板要求进行总结与输出。\n"
                "要求：优先严格按照模板输出；模板未覆盖的内容可追加“补充信息”。缺失字段请输出“无”。"
            )

            if template_spec_blocks:
                system_content += "\n\n以下是用户提供的模板信息：\n" + "\n\n".join(template_spec_blocks)

            if file_contents:
                docs_text = "\n\n".join(file_contents)
                system_content += f"\n\n以下是用户上传的文档内容：\n\n{docs_text}"
            elif payload.file_ids:
                file_ids_text = ", ".join(payload.file_ids)
                system_content += f"\n\n用户上传了文档（ID: {file_ids_text}），但内容提取失败。请提示用户检查文档。"

            messages.append({"role": "system", "content": system_content})

            if payload.history:
                for msg in payload.history:
                    if msg.content:
                        messages.append({"role": msg.role, "content": msg.content})

            messages.append({"role": "user", "content": user_text})

            # 设置合理的超时：连接10秒，读取120秒（AI模型可能需要较长时间响应）
            timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
                    json={"model": model, "messages": messages, "stream": True},
                ) as resp:
                    if resp.status_code >= 400:
                        text = await resp.aread()
                        raise RuntimeError(f"AI 调用失败: {resp.status_code}: {text.decode('utf-8', errors='ignore')}")

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue

                        data_part = line[len("data:"):].strip()
                        if data_part == "[DONE]":
                            yield f"data: {json.dumps({'type': 'done', 'content': ''}, ensure_ascii=False)}\n\n"
                            return

                        try:
                            event = json.loads(data_part)
                        except Exception:
                            continue

                        delta = None
                        try:
                            delta = event.get("choices", [{}])[0].get("delta")
                        except Exception:
                            delta = None

                        if isinstance(delta, dict):
                            reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                            if reasoning:
                                yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning}, ensure_ascii=False)}\n\n"
                            content = delta.get("content")
                            if content:
                                # 直接发送原始内容，由前端解析 <think> 标签
                                yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

                    yield f"data: {json.dumps({'type': 'done', 'content': ''}, ensure_ascii=False)}\n\n"
        except httpx.TimeoutException as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'AI 服务响应超时，请稍后重试: {str(e)}'}, ensure_ascii=False)}\n\n"
        except httpx.ConnectError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'无法连接到 AI 服务: {str(e)}'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

@router.get("/files/{file_id}/download")
async def download_file(request: Request, file_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.id == uuid.UUID(file_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    bucket = settings.MINIO_BUCKET_UPLOADS
    object_name = doc.minio_path
    if doc.minio_path and "/" in doc.minio_path:
        prefix, rest = doc.minio_path.split("/", 1)
        if prefix == settings.MINIO_BUCKET_OUTPUTS or prefix == "outputs":
            bucket = settings.MINIO_BUCKET_OUTPUTS
            object_name = rest
        elif prefix == settings.MINIO_BUCKET_UPLOADS or prefix == "uploads":
            bucket = settings.MINIO_BUCKET_UPLOADS
            object_name = rest
        else:
            object_name = rest
    object_name = object_name.split("/")[-1]

    try:
        # stat = minio_client.client.stat_object(bucket, object_name)
        # 使用 run_in_threadpool 避免阻塞事件循环
        stat = await run_in_threadpool(minio_client.client.stat_object, bucket, object_name)
        total_size = int(stat.size)
    except Exception:
        # Fallback to DB size if stat fails
        total_size = int(doc.file_size or 0)

    range_header = request.headers.get("range")
    if range_header and total_size <= 0:
        range_header = None

    def _stream_object(offset: int | None = None, length: int | None = None):
        response = minio_client.client.get_object(bucket, object_name, offset=offset, length=length)
        try:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            response.close()
            response.release_conn()

    # Content-Disposition must be latin-1 encodable in Starlette headers.
    # Use RFC 5987 (filename*) for UTF-8 filenames with an ASCII fallback.
    ascii_fallback = "download"
    try:
        doc.filename.encode("latin-1")
        content_disposition = f'attachment; filename="{doc.filename}"'
    except Exception:
        quoted = quote(doc.filename, safe="")
        content_disposition = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": content_disposition,
    }

    # Support single-range requests: Range: bytes=start-end
    if range_header:
        try:
            unit, value = range_header.split("=", 1)
            if unit.strip().lower() != "bytes":
                raise ValueError("Unsupported range unit")

            start_s, end_s = value.split("-", 1)
            if start_s == "":
                # Suffix range: last N bytes
                suffix_len = int(end_s)
                if suffix_len <= 0:
                    raise ValueError("Invalid suffix")
                start = max(total_size - suffix_len, 0)
                end = total_size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else (total_size - 1)

            if total_size <= 0:
                raise HTTPException(status_code=404, detail="Empty file")
            if start < 0 or start >= total_size:
                raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")
            end = min(end, total_size - 1)
            if end < start:
                raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

            length = end - start + 1
            headers.update(
                {
                    "Content-Range": f"bytes {start}-{end}/{total_size}",
                    "Content-Length": str(length),
                }
            )
            return StreamingResponse(
                _stream_object(offset=start, length=length),
                status_code=206,
                media_type=doc.mime_type or "application/octet-stream",
                headers=headers,
            )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Range header")

    if total_size > 0:
        headers["Content-Length"] = str(total_size)

    return StreamingResponse(
        _stream_object(),
        media_type=doc.mime_type or "application/octet-stream",
        headers=headers,
    )

@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ProcessingTask).where(ProcessingTask.id == uuid.UUID(task_id))
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return {
        "taskId": str(task.id),
        "status": task.status,
        "resultFileId": str(task.result_file_id) if task.result_file_id else None,
        "error": task.error_message
    }


# ==================== 文档审查 API ====================

class ReviewRequest(BaseModel):
    file_id: str
    review_type: str = "general"  # legal, compliance, risk, general
    ai_model: str | None = None

class ReviewResponse(BaseModel):
    review_id: str
    status: str

class ReviewResult(BaseModel):
    review_id: str
    status: str
    review_type: str
    annotations: list | None = None
    summary: str | None = None
    risk_level: str | None = None
    error: str | None = None


@router.post("/reviews/create", response_model=ReviewResponse)
async def create_review(
    req: ReviewRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """创建文档审查任务"""
    from app.services.workflow import process_review_background
    
    new_review = DocumentReview(
        id=uuid.uuid4(),
        user_id=None,
        document_id=uuid.UUID(req.file_id),
        review_type=req.review_type,
        ai_model=req.ai_model,
        status="pending"
    )
    
    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)
    
    background_tasks.add_task(process_review_background, str(new_review.id), req.ai_model)
    
    return ReviewResponse(review_id=str(new_review.id), status=new_review.status)


@router.get("/reviews/{review_id}", response_model=ReviewResult)
async def get_review(review_id: str, db: AsyncSession = Depends(get_db)):
    """获取审查结果"""
    stmt = select(DocumentReview).where(DocumentReview.id == uuid.UUID(review_id))
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    annotations = None
    if review.annotations:
        try:
            annotations = json.loads(review.annotations)
        except:
            pass
    
    return ReviewResult(
        review_id=str(review.id),
        status=review.status,
        review_type=review.review_type,
        annotations=annotations,
        summary=review.summary,
        risk_level=review.risk_level,
        error=review.error_message
    )


@router.get("/reviews")
async def list_reviews(db: AsyncSession = Depends(get_db)):
    """获取所有审查任务"""
    stmt = select(DocumentReview).order_by(DocumentReview.created_at.desc())
    result = await db.execute(stmt)
    reviews = result.scalars().all()
    
    return [
        {
            "review_id": str(r.id),
            "document_id": str(r.document_id),
            "review_type": r.review_type,
            "status": r.status,
            "risk_level": r.risk_level,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in reviews
    ]


# ==================== 工作流 API ====================

class WorkflowNode(BaseModel):
    id: str
    type: str  # content_extractor, document_analyzer, ai_processor, document_generator, etc.
    label: str
    config: dict | None = None
    position: dict | None = None

class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str

class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]

class WorkflowExecuteRequest(BaseModel):
    workflow_id: str
    input_file_ids: list[str]


@router.post("/workflows/create")
async def create_workflow(
    workflow_in: WorkflowCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建工作流"""
    new_workflow = Workflow(
        id=uuid.uuid4(),
        user_id=None,
        name=workflow_in.name,
        description=workflow_in.description,
        nodes=json.dumps([n.model_dump() for n in workflow_in.nodes], ensure_ascii=False),
        edges=json.dumps([e.model_dump() for e in workflow_in.edges], ensure_ascii=False),
        is_active=True
    )
    
    db.add(new_workflow)
    await db.commit()
    await db.refresh(new_workflow)
    
    return {"workflow_id": str(new_workflow.id), "name": new_workflow.name}


@router.get("/workflows")
async def list_workflows(db: AsyncSession = Depends(get_db)):
    """获取所有工作流"""
    stmt = select(Workflow).where(Workflow.is_active == True).order_by(Workflow.created_at.desc())
    result = await db.execute(stmt)
    workflows = result.scalars().all()
    
    return [
        {
            "workflow_id": str(w.id),
            "name": w.name,
            "description": w.description,
            "nodes": json.loads(w.nodes) if w.nodes else [],
            "edges": json.loads(w.edges) if w.edges else [],
            "created_at": w.created_at.isoformat() if w.created_at else None
        }
        for w in workflows
    ]


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    """获取工作流详情"""
    stmt = select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return {
        "workflow_id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "nodes": json.loads(workflow.nodes) if workflow.nodes else [],
        "edges": json.loads(workflow.edges) if workflow.edges else [],
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None
    }


@router.post("/workflows/execute")
async def execute_workflow(
    req: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """执行工作流"""
    from app.services.workflow import execute_workflow_background
    
    # 验证工作流存在
    stmt = select(Workflow).where(Workflow.id == uuid.UUID(req.workflow_id))
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    new_execution = WorkflowExecution(
        id=uuid.uuid4(),
        workflow_id=uuid.UUID(req.workflow_id),
        user_id=None,
        input_file_ids=[uuid.UUID(fid) for fid in req.input_file_ids],
        status="pending"
    )
    
    db.add(new_execution)
    await db.commit()
    await db.refresh(new_execution)
    
    background_tasks.add_task(execute_workflow_background, str(new_execution.id))
    
    return {"execution_id": str(new_execution.id), "status": new_execution.status}


@router.get("/workflows/executions/{execution_id}")
async def get_workflow_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    """获取工作流执行状态"""
    stmt = select(WorkflowExecution).where(WorkflowExecution.id == uuid.UUID(execution_id))
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    node_results = None
    if execution.node_results:
        try:
            node_results = json.loads(execution.node_results)
        except:
            pass
    
    return {
        "execution_id": str(execution.id),
        "workflow_id": str(execution.workflow_id),
        "status": execution.status,
        "current_node": execution.current_node,
        "node_results": node_results,
        "output_file_id": str(execution.output_file_id) if execution.output_file_id else None,
        "error": execution.error_message,
        "created_at": execution.created_at.isoformat() if execution.created_at else None
    }


# ==================== 音频转录 API ====================

class TranscriptionRequest(BaseModel):
    audio_file_id: str
    generate_minutes: bool = True  # 是否生成会议纪要
    ai_model: str | None = None

class TranscriptionResponse(BaseModel):
    transcription_id: str
    status: str


@router.post("/transcriptions/create", response_model=TranscriptionResponse)
async def create_transcription(
    req: TranscriptionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """创建音频转录任务"""
    from app.services.workflow import process_transcription_background
    
    new_transcription = AudioTranscription(
        id=uuid.uuid4(),
        user_id=None,
        audio_file_id=uuid.UUID(req.audio_file_id),
        ai_model=req.ai_model,
        status="pending"
    )
    
    db.add(new_transcription)
    await db.commit()
    await db.refresh(new_transcription)
    
    background_tasks.add_task(
        process_transcription_background, 
        str(new_transcription.id), 
        req.generate_minutes,
        req.ai_model
    )
    
    return TranscriptionResponse(
        transcription_id=str(new_transcription.id), 
        status=new_transcription.status
    )


@router.get("/transcriptions/{transcription_id}")
async def get_transcription(transcription_id: str, db: AsyncSession = Depends(get_db)):
    """获取转录结果"""
    stmt = select(AudioTranscription).where(AudioTranscription.id == uuid.UUID(transcription_id))
    result = await db.execute(stmt)
    transcription = result.scalar_one_or_none()
    
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    
    speakers = None
    action_items = None
    if transcription.speakers:
        try:
            speakers = json.loads(transcription.speakers)
        except:
            pass
    if transcription.action_items:
        try:
            action_items = json.loads(transcription.action_items)
        except:
            pass
    
    return {
        "transcription_id": str(transcription.id),
        "audio_file_id": str(transcription.audio_file_id),
        "status": transcription.status,
        "transcript": transcription.transcript,
        "speakers": speakers,
        "summary": transcription.summary,
        "action_items": action_items,
        "result_file_id": str(transcription.result_file_id) if transcription.result_file_id else None,
        "error": transcription.error_message,
        "created_at": transcription.created_at.isoformat() if transcription.created_at else None
    }


@router.get("/transcriptions")
async def list_transcriptions(db: AsyncSession = Depends(get_db)):
    """获取所有转录任务"""
    stmt = select(AudioTranscription).order_by(AudioTranscription.created_at.desc())
    result = await db.execute(stmt)
    transcriptions = result.scalars().all()
    
    return [
        {
            "transcription_id": str(t.id),
            "audio_file_id": str(t.audio_file_id),
            "status": t.status,
            "result_file_id": str(t.result_file_id) if t.result_file_id else None,
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in transcriptions
    ]
