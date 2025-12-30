from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True)
    subscription_tier = Column(String(50), default="free")
    storage_quota = Column(BigInteger, default=1073741824) # 1GB
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    filename = Column(String(500))
    file_size = Column(BigInteger)
    mime_type = Column(String(100))
    minio_path = Column(String(500))
    status = Column(String(50), default="uploading") # uploading, uploaded, processing, completed, failed
    is_template = Column(Boolean, default=False)
    template_category = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    task_type = Column(String(50)) # fill_template, format_document, batch_process
    content_file_ids = Column(ARRAY(UUID(as_uuid=True)))
    template_file_id = Column(UUID(as_uuid=True), nullable=True)
    requirements = Column(Text, nullable=True)
    status = Column(String(50), default="pending") # pending, processing, completed, failed
    result_file_id = Column(UUID(as_uuid=True), nullable=True)
    ai_model = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class TemplateLibrary(Base):
    __tablename__ = "template_library"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255))
    description = Column(Text)
    preview_image_url = Column(String(500))
    document_id = Column(UUID(as_uuid=True), nullable=True)
    tags = Column(ARRAY(String))
    usage_count = Column(Integer, default=0)
    is_system = Column(Boolean, default=False)
