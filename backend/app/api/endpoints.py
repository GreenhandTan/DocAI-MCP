from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Document, ProcessingTask
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

class ChatRequest(BaseModel):
    message: str
    file_ids: list[str] | None = None
    template_file_id: str | None = None
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

    # 提取文件内容
    file_contents = []
    if payload.file_ids:
        for file_id in payload.file_ids:
            try:
                # 调用 MCP 服务提取内容
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "http://mcp-server:3000/api/tools/content_extractor/invoke",
                        json={"file_id": file_id, "format": "markdown"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data.get("content", "")
                        if content and not content.startswith("无法") and not content.startswith("提取"):
                            file_contents.append(f"【文档内容】:\n{content[:3000]}")  # 限制长度
            except Exception as e:
                file_contents.append(f"【文档 {file_id}】: 内容提取失败 - {str(e)}")

    # 构建提示词
    prompt = user_text
    if file_contents:
        docs_text = "\n\n".join(file_contents)
        template_text = payload.preset_template or "无"
        prompt = f"以下是用户上传的文档内容：\n\n{docs_text}\n\n用户选择的模板类型：{template_text}\n\n用户需求：{user_text}\n\n请根据文档内容和用户需求，用中文给出详细的处理方案和结果预期。"
    elif payload.file_ids:
        # 文件 ID 存在但内容提取失败
        file_ids_text = ", ".join(payload.file_ids)
        template_text = payload.preset_template or "无"
        prompt = f"用户上传了文档（ID: {file_ids_text}），但内容提取失败。\n模板类型：{template_text}\n用户需求：{user_text}\n\n请提示用户重新上传文档或检查文档格式。"

    async def generate():
        yield f"data: {json.dumps({'type': 'thinking', 'content': '正在思考...'}, ensure_ascii=False)}\n\n"
        try:
            # 设置合理的超时：连接10秒，读取120秒（AI模型可能需要较长时间响应）
            timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
                    json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True},
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
    object_name = doc.minio_path.split("/")[-1]

    try:
        stat = minio_client.client.stat_object(bucket, object_name)
        total_size = int(stat.size)
    except Exception:
        # Fallback to DB size if stat fails
        total_size = int(doc.file_size or 0)

    range_header = request.headers.get("range")

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
