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
from zhipuai import ZhipuAI
from pydantic import BaseModel
import uuid
import os
from urllib.parse import quote

router = APIRouter()
settings = get_settings()

class TaskCreate(BaseModel):
    task_type: str
    content_file_ids: list[str]
    template_file_id: str | None = None
    preset_template: str | None = None
    requirements: str | None = None

class TaskResponse(BaseModel):
    task_id: str
    status: str

class DocumentResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    is_template: bool
    created_at: str | None = None

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

class ChatResponse(BaseModel):
    reply: str

class ModifyRequest(BaseModel):
    file_id: str
    modifications: str

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
        "status": new_doc.status
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
        status="pending"
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    background_tasks.add_task(process_task_background, str(new_task.id), task_in.preset_template)
    
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
        status="pending"
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    background_tasks.add_task(process_task_background, str(new_task.id), None, req.modifications)
    
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
            created_at=d.created_at.isoformat() if d.created_at else None
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

    model = settings.AI_MODEL_NAME or "glm-4.5-air"
    client = ZhipuAI(api_key=settings.AI_API_KEY)

    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="message 不能为空")

    prompt = user_text
    if payload.file_ids:
        file_ids_text = ", ".join(payload.file_ids)
        template_text = payload.template_file_id or payload.preset_template or "无"
        prompt = f"内容文档ID：{file_ids_text}\n模板文档ID：{template_text}\n用户需求：{user_text}\n请用中文给出可执行的处理方案与结果预期。"

    def _call():
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        return resp.choices[0].message.content

    reply = await run_in_threadpool(_call)
    return ChatResponse(reply=reply)

@router.post("/ai/chat/stream")
async def ai_chat_stream(payload: ChatRequest):
    """流式聊天接口，支持SSE"""
    if not settings.AI_API_KEY:
        raise HTTPException(status_code=500, detail="AI_API_KEY 未配置")

    model = settings.AI_MODEL_NAME or "glm-4.5-air"
    client = ZhipuAI(api_key=settings.AI_API_KEY)

    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="message 不能为空")

    prompt = user_text
    if payload.file_ids:
        file_ids_text = ", ".join(payload.file_ids)
        template_text = payload.template_file_id or payload.preset_template or "无"
        prompt = f"内容文档ID：{file_ids_text}\n模板文档ID：{template_text}\n用户需求：{user_text}\n请用中文给出可执行的处理方案与结果预期。"

    import json
    
    def generate():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )
            
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    # 检查是否有思考过程（reasoning_content）
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        yield f"data: {json.dumps({'type': 'thinking', 'content': delta.reasoning_content}, ensure_ascii=False)}\n\n"
                    # 正常内容输出
                    if hasattr(delta, 'content') and delta.content:
                        yield f"data: {json.dumps({'type': 'content', 'content': delta.content}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
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
