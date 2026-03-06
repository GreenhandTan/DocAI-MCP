"""
扩展功能 API
包括文档版本历史、多格式导出、批量下载、系统监控、Webhook等
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from app.database import get_db
from app.models import DocumentVersion, Document, SystemStats, WebhookConfig, User, ProcessingTask
from app.core.auth import get_current_user, get_current_user_optional
from app.services.minio_client import minio_client
from app.core.config import get_settings
from starlette.concurrency import run_in_threadpool
import uuid
import datetime
import httpx
import hashlib
import hmac
import json
import zipfile
import io
import tempfile
import os

router = APIRouter(tags=["extended"])
settings = get_settings()


# ==================== 文档版本历史 ====================

class VersionResponse(BaseModel):
    version_id: str
    document_id: str
    version_number: int
    file_size: int
    change_description: str | None
    created_at: str


@router.get("/files/{file_id}/versions", response_model=list[VersionResponse])
async def list_file_versions(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """获取文档版本历史"""
    # 验证文档存在和权限
    stmt = select(Document).where(Document.id == uuid.UUID(file_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if current_user and doc.user_id and doc.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # 获取版本列表
    stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == uuid.UUID(file_id)
    ).order_by(DocumentVersion.version_number.desc())
    
    result = await db.execute(stmt)
    versions = result.scalars().all()
    
    return [
        VersionResponse(
            version_id=str(v.id),
            document_id=str(v.document_id),
            version_number=v.version_number,
            file_size=v.file_size,
            change_description=v.change_description,
            created_at=v.created_at.isoformat() if v.created_at else ""
        )
        for v in versions
    ]


@router.post("/files/{file_id}/create-version")
async def create_version(
    file_id: str,
    change_description: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """为文档创建新版本快照"""
    # 获取当前文档
    stmt = select(Document).where(Document.id == uuid.UUID(file_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 权限检查
    if current_user and doc.user_id and doc.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # 获取当前最大版本号
    stmt = select(func.max(DocumentVersion.version_number)).where(
        DocumentVersion.document_id == uuid.UUID(file_id)
    )
    result = await db.execute(stmt)
    max_version = result.scalar() or 0
    
    # 创建版本记录（指向当前文档的 MinIO 路径）
    new_version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=uuid.UUID(file_id),
        version_number=max_version + 1,
        minio_path=doc.minio_path,
        file_size=doc.file_size,
        change_description=change_description,
        created_by=current_user.id if current_user else None
    )
    
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    
    return {
        "version_id": str(new_version.id),
        "version_number": new_version.version_number
    }


@router.post("/files/{file_id}/restore-version/{version_id}")
async def restore_version(
    file_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """恢复到指定版本"""
    # 获取文档和版本
    stmt = select(Document).where(Document.id == uuid.UUID(file_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    stmt = select(DocumentVersion).where(DocumentVersion.id == uuid.UUID(version_id))
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()
    
    if not version or version.document_id != uuid.UUID(file_id):
        raise HTTPException(status_code=404, detail="Version not found")
    
    # 权限检查
    if current_user and doc.user_id and doc.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # 先保存当前版本
    await create_version(file_id, "Auto-save before restore", db, current_user)
    
    # 恢复到指定版本（指向版本的 MinIO 路径）
    doc.minio_path = version.minio_path
    doc.file_size = version.file_size
    await db.commit()
    
    return {"message": "Version restored successfully"}


# ==================== 多格式导出 ====================

@router.post("/files/{file_id}/export")
async def export_file(
    file_id: str,
    format: str,  # pdf, markdown, html
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """导出文档为不同格式"""
    # 验证文档存在
    stmt = select(Document).where(Document.id == uuid.UUID(file_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 调用 MCP 服务进行格式转换
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "http://mcp-server:3000/api/tools/format_converter/invoke",
            json={
                "file_id": file_id,
                "output_format": format
            }
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Format conversion failed: {resp.text}")
        
        result_data = resp.json()
        result_file_id = result_data.get("result_file_id")
        
        if not result_file_id:
            raise HTTPException(status_code=500, detail="No result file returned")
        
        return {
            "message": "Export successful",
            "result_file_id": result_file_id,
            "format": format
        }


# ==================== 批量下载打包 ====================

@router.post("/files/download-batch")
async def download_batch(
    file_ids: list[str],
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """批量下载文件，打包为 ZIP"""
    if not file_ids:
        raise HTTPException(status_code=400, detail="No files specified")
    
    if len(file_ids) > 100:
        raise HTTPException(status_code=400, detail="Too many files (max 100)")
    
    # 获取所有文档
    stmt = select(Document).where(Document.id.in_([uuid.UUID(fid) for fid in file_ids]))
    result = await db.execute(stmt)
    docs = result.scalars().all()
    
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")
    
    # 创建 ZIP 文件
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for doc in docs:
            try:
                # 从 MinIO 下载文件
                bucket = settings.MINIO_BUCKET_UPLOADS
                object_name = doc.minio_path
                
                if "/" in doc.minio_path:
                    prefix, rest = doc.minio_path.split("/", 1)
                    if prefix in [settings.MINIO_BUCKET_OUTPUTS, "outputs"]:
                        bucket = settings.MINIO_BUCKET_OUTPUTS
                        object_name = rest
                    elif prefix in [settings.MINIO_BUCKET_UPLOADS, "uploads"]:
                        object_name = rest
                
                object_name = object_name.split("/")[-1]
                
                # 读取文件内容
                response = await run_in_threadpool(
                    minio_client.client.get_object, 
                    bucket, 
                    object_name
                )
                file_data = response.read()
                response.close()
                response.release_conn()
                
                # 添加到 ZIP（使用原始文件名避免重复）
                safe_filename = f"{doc.filename}"
                if safe_filename in zip_file.namelist():
                    name, ext = os.path.splitext(doc.filename)
                    safe_filename = f"{name}_{str(doc.id)[:8]}{ext}"
                
                zip_file.writestr(safe_filename, file_data)
                
            except Exception as e:
                print(f"Failed to add file {doc.id} to ZIP: {e}")
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="documents_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"'
        }
    )


# ==================== 系统监控 ====================

@router.get("/admin/stats")
async def get_system_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取系统统计信息（需要管理员权限）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # 用户统计
    stmt = select(func.count(User.id)).where(User.is_active == True)
    result = await db.execute(stmt)
    total_users = result.scalar() or 0
    
    # 文档统计
    stmt = select(func.count(Document.id))
    result = await db.execute(stmt)
    total_documents = result.scalar() or 0
    
    stmt = select(func.sum(Document.file_size))
    result = await db.execute(stmt)
    total_storage = result.scalar() or 0
    
    # 任务统计
    stmt = select(func.count(ProcessingTask.id))
    result = await db.execute(stmt)
    total_tasks = result.scalar() or 0
    
    stmt = select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "completed")
    result = await db.execute(stmt)
    completed_tasks = result.scalar() or 0
    
    stmt = select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "failed")
    result = await db.execute(stmt)
    failed_tasks = result.scalar() or 0
    
    # 今日统计
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    stmt = select(func.count(User.id)).where(User.created_at >= today)
    result = await db.execute(stmt)
    new_users_today = result.scalar() or 0
    
    stmt = select(func.count(ProcessingTask.id)).where(ProcessingTask.created_at>= today)
    result = await db.execute(stmt)
    tasks_today = result.scalar() or 0
    
    return {
        "total_users": total_users,
        "total_documents": total_documents,
        "total_storage_bytes": total_storage,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        "today": {
            "new_users": new_users_today,
            "tasks": tasks_today
        }
    }


@router.get("/admin/stats/history")
async def get_stats_history(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取历史统计数据"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    start_date = datetime.datetime.now() - datetime.timedelta(days=days)
    
    stmt = select(SystemStats).where(
        SystemStats.date >= start_date
    ).order_by(SystemStats.date)
    
    result = await db.execute(stmt)
    stats = result.scalars().all()
    
    return [
        {
            "date": s.date.isoformat(),
            "total_users": s.total_users,
            "active_users": s.active_users,
            "total_documents": s.total_documents,
            "total_tasks": s.total_tasks,
            "completed_tasks": s.completed_tasks,
            "failed_tasks": s.failed_tasks,
            "storage_used": s.storage_used,
            "ai_calls": s.ai_calls
        }
        for s in stats
    ]


# ==================== Webhook 管理 ====================

class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str]  # ["task_completed", "document_uploaded", "review_completed"]
    secret: str | None = None


class WebhookResponse(BaseModel):
    webhook_id: str
    name: str
    url: str
    events: list[str]
    is_active: bool


@router.post("/webhooks", response_model=WebhookResponse)
async def create_webhook(
    webhook_in: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建 Webhook"""
    new_webhook = WebhookConfig(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=webhook_in.name,
        url=webhook_in.url,
        events=webhook_in.events,
        is_active=True,
        secret=webhook_in.secret
    )
    
    db.add(new_webhook)
    await db.commit()
    await db.refresh(new_webhook)
    
    return WebhookResponse(
        webhook_id=str(new_webhook.id),
        name=new_webhook.name,
        url=new_webhook.url,
        events=new_webhook.events,
        is_active=new_webhook.is_active
    )


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的所有 Webhook"""
    stmt = select(WebhookConfig).where(
        WebhookConfig.user_id == current_user.id
    ).order_by(WebhookConfig.created_at.desc())
    
    result = await db.execute(stmt)
    webhooks = result.scalars().all()
    
    return [
        WebhookResponse(
            webhook_id=str(w.id),
            name=w.name,
            url=w.url,
            events=w.events,
            is_active=w.is_active
        )
        for w in webhooks
    ]


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除 Webhook"""
    stmt = select(WebhookConfig).where(
        and_(
            WebhookConfig.id == uuid.UUID(webhook_id),
            WebhookConfig.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    await db.delete(webhook)
    await db.commit()
    
    return {"message": "Webhook deleted"}


async def trigger_webhooks(event_type: str, payload: dict, user_id: uuid.UUID | None = None, db: AsyncSession = None):
    """触发 Webhook（内部函数）"""
    if not db or not user_id:
        return
    
    # 获取用户的所有活跃 Webhook
    stmt = select(WebhookConfig).where(
        and_(
            WebhookConfig.user_id == user_id,
            WebhookConfig.is_active == True,
            WebhookConfig.events.contains([event_type])
        )
    )
    result = await db.execute(stmt)
    webhooks = result.scalars().all()
    
    # 发送 Webhook 请求
    async with httpx.AsyncClient(timeout=10.0) as client:
        for webhook in webhooks:
            try:
                headers = {"Content-Type": "application/json"}
                
                # 添加签名（如果配置了 secret）
                if webhook.secret:
                    payload_str = json.dumps(payload)
                    signature = hmac.new(
                        webhook.secret.encode(),
                        payload_str.encode(),
                        hashlib.sha256
                    ).hexdigest()
                    headers["X-Webhook-Signature"] = signature
                
                await client.post(
                    webhook.url,
                    json=payload,
                    headers=headers
                )
                
                # 更新最后触发时间
                webhook.last_triggered = datetime.datetime.utcnow()
                await db.commit()
                
            except Exception as e:
                print(f"Failed to trigger webhook {webhook.id}: {e}")


# ==================== 订阅层级管理 ====================

@router.post("/subscription/upgrade")
async def upgrade_subscription(
    tier: str,  # pro, enterprise
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """升级订阅层级"""
    # 定义层级配额
    tier_quotas = {
        "free": 1 * 1024 * 1024 * 1024,  # 1GB
        "pro": 10 * 1024 * 1024 * 1024,  # 10GB
        "enterprise": 100 * 1024 * 1024 * 1024  # 100GB
    }
    
    if tier not in tier_quotas:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    current_user.subscription_tier = tier
    current_user.storage_quota = tier_quotas[tier]
    
    await db.commit()
    
    return {
        "message": "Subscription upgraded",
        "tier": tier,
        "storage_quota": tier_quotas[tier]
    }


@router.get("/subscription/info")
async def get_subscription_info(
    current_user: User = Depends(get_current_user)
):
    """获取订阅信息"""
    return {
        "tier": current_user.subscription_tier,
        "storage_quota": current_user.storage_quota,
        "storage_used": current_user.storage_used,
        "storage_available": current_user.storage_quota - current_user.storage_used,
        "usage_percentage": (current_user.storage_used / current_user.storage_quota * 100) if current_user.storage_quota > 0 else 0
    }
