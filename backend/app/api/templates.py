"""
模板库 API 端点
包括模板的增删改查、分类、标签管理等功能
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from pydantic import BaseModel
from app.database import get_db
from app.models import TemplateLibrary, Document, User
from app.core.auth import get_current_user_optional
from app.services.minio_client import minio_client
import uuid
import os

router = APIRouter(tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    description: str
    tags: list[str] | None = None
    document_id: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    preview_image_url: str | None = None


class TemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    preview_image_url: str | None
    document_id: str | None
    tags: list[str]
    usage_count: int
    is_system: bool


@router.post("/ templates")
async def create_template(
    name: str = Form(...),
    description: str = Form(...),
    tags: str = Form(None),  # 逗号分隔的标签
    file: UploadFile | None = File(None),
    preview_image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
   current_user: User | None = Depends(get_current_user_optional)
):
    """创建模板（可同时上传文件）"""
    document_id = None
    preview_image_url = None
    
    # 上传模板文件
    if file:
        file_content = await file.read()
        file_ext = os.path.splitext(file.filename)[1]
        storage_filename = f"{uuid.uuid4()}{file_ext}"
        
        minio_path = minio_client.upload_file(
            file_content,
            storage_filename,
            file.content_type
        )
        
        # 创建文档记录
        new_doc = Document(
            id=uuid.uuid4(),
            user_id=current_user.id if current_user else None,
            filename=file.filename,
            file_size=len(file_content),
            mime_type=file.content_type,
            minio_path=minio_path,
            status="uploaded",
            is_template=True
        )
        db.add(new_doc)
        await db.flush()
        document_id = new_doc.id
    
    # 上传预览图
    if preview_image:
        img_content = await preview_image.read()
        img_ext = os.path.splitext(preview_image.filename)[1]
        img_filename = f"{uuid.uuid4()}{img_ext}"
        
        minio_path = minio_client.upload_file(
            img_content,
            img_filename,
            preview_image.content_type
        )
        preview_image_url = f"/api/v1/templates/preview/{img_filename}"
    
    # 解析标签
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    
    # 创建模板记录
    new_template = TemplateLibrary(
        id=uuid.uuid4(),
        name=name,
        description=description,
        preview_image_url=preview_image_url,
        document_id=document_id,
        tags=tag_list,
        usage_count=0,
        is_system=False
    )
    
    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)
    
    return {
        "template_id": str(new_template.id),
        "name": new_template.name,
        "document_id": str(new_template.document_id) if new_template.document_id else None
    }


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    category: str | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """获取模板列表"""
    stmt = select(TemplateLibrary).order_by(TemplateLibrary.usage_count.desc())
    
    # 按标签筛选
    if tag:
        stmt = stmt.where(TemplateLibrary.tags.contains([tag]))
    
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    return [
        TemplateResponse(
            template_id=str(t.id),
            name=t.name,
            description=t.description,
            preview_image_url=t.preview_image_url,
            document_id=str(t.document_id) if t.document_id else None,
            tags=t.tags or [],
            usage_count=t.usage_count,
            is_system=t.is_system
        )
        for t in templates
    ]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    """获取模板详情"""
    stmt = select(TemplateLibrary).where(TemplateLibrary.id == uuid.UUID(template_id))
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return TemplateResponse(
        template_id=str(template.id),
        name=template.name,
        description=template.description,
        preview_image_url=template.preview_image_url,
        document_id=str(template.document_id) if template.document_id else None,
        tags=template.tags or [],
        usage_count=template.usage_count,
        is_system=template.is_system
    )


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    template_in: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """更新模板"""
    stmt = select(TemplateLibrary).where(TemplateLibrary.id == uuid.UUID(template_id))
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 系统模板只有管理员可以修改
    if template.is_system and (not current_user or not current_user.is_admin):
        raise HTTPException(status_code=403, detail="Cannot modify system template")
    
    # 更新字段
    if template_in.name is not None:
        template.name = template_in.name
    if template_in.description is not None:
        template.description = template_in.description
    if template_in.tags is not None:
        template.tags = template_in.tags
    if template_in.preview_image_url is not None:
        template.preview_image_url = template_in.preview_image_url
    
    await db.commit()
    await db.refresh(template)
    
    return {"message": "Template updated", "template_id": str(template.id)}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """删除模板"""
   stmt = select(TemplateLibrary).where(TemplateLibrary.id == uuid.UUID(template_id))
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 系统模板只有管理员可以删除
    if template.is_system and (not current_user or not current_user.is_admin):
        raise HTTPException(status_code=403, detail="Cannot delete system template")
    
    await db.delete(template)
    await db.commit()
    
    return {"message": "Template deleted", "template_id": template_id}


@router.post("/templates/{template_id}/use")
async def use_template(template_id: str, db: AsyncSession = Depends(get_db)):
    """使用模板（增加使用计数）"""
    stmt = update(TemplateLibrary).where(
        TemplateLibrary.id == uuid.UUID(template_id)
    ).values(
        usage_count=TemplateLibrary.usage_count + 1
    )
    await db.execute(stmt)
    await db.commit()
    
    return {"message": "Usage count incremented"}


@router.get("/templates/tags/list")
async def list_tags(db: AsyncSession = Depends(get_db)):
    """获取所有标签列表"""
    stmt = select(func.unnest(TemplateLibrary.tags).label("tag")).distinct()
    result = await db.execute(stmt)
    tags = [row[0] for row in result if row[0]]
    
    return {"tags": sorted(tags)}
