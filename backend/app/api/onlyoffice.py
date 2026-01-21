from fastapi import APIRouter, Depends, HTTPException, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Document
from app.core.config import get_settings
import jwt
import httpx
import uuid
import time

router = APIRouter()
settings = get_settings()

def create_jwt_token(payload: dict):
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

@router.get("/files/{file_id}/onlyoffice-config")
async def get_onlyoffice_config(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Document).where(Document.id == uuid.UUID(file_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Generate Key (using timestamp to invalidate cache on update)
    # Using last 10 chars of id + timestamp
    doc_key = f"{str(doc.id).replace('-', '')[:10]}{int(time.time())}"
    
    # OnlyOffice fetches the document via backend proxy (no direct MinIO / presigned URL exposure)
    download_url = f"{settings.BACKEND_INTERNAL_URL}{settings.API_V1_STR}/files/{doc.id}/download"

    # Callback URL (OnlyOffice -> Backend), must be reachable from OnlyOffice container
    callback_url = f"{settings.BACKEND_INTERNAL_URL}{settings.API_V1_STR}/onlyoffice/track?fileId={doc.id}"
    
    config = {
        "document": {
            "fileType": doc.filename.split('.')[-1],
            "key": doc_key,
            "title": doc.filename,
            "url": download_url,
            "permissions": {
                "edit": True,
                "download": True,
                "print": True
            }
        },
        "editorConfig": {
            "callbackUrl": callback_url,
            "mode": "edit",
            "lang": settings.ONLYOFFICE_LANG,
            "user": {
                "id": "test-user-1", # Mock user
                "name": "Test User"
            },
            "customization": {
                "autosave": True,
                "forcesave": True
            }
        }
    }
    
    # Sign token
    token = create_jwt_token(config)
    config["token"] = token
    
    return config

@router.post("/onlyoffice/track")
async def track_document_changes(
    fileId: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db)
):
    # Verify status
    # 2 - Ready for saving
    # 6 - Editing force saved
    status = body.get("status")
    
    if status == 2 or status == 6:
        download_link = body.get("url")
        if not download_link:
            return {"error": 1, "message": "No url provided"}
            
        # Download the new file from OnlyOffice
        async with httpx.AsyncClient() as client:
            response = await client.get(download_link)
            if response.status_code != 200:
                return {"error": 1, "message": "Failed to download from OnlyOffice"}
            file_content = response.content
            
        # Update MinIO
        stmt = select(Document).where(Document.id == uuid.UUID(fileId))
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            return {"error": 1, "message": "Document not found"}
            
        # Overwrite file in MinIO
        # We use the same path to keep it simple, or we could version it
        from app.services.minio_client import minio_client

        minio_client.upload_file(
            file_content,
            doc.minio_path.split('/')[-1], # filename only
            doc.mime_type
        )
        
        # Update DB
        doc.file_size = len(file_content)
        # doc.updated_at = func.now() # if we had this field
        await db.commit()
        
    return {"error": 0}
