from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    username = Column(String(100), nullable=True)
    subscription_tier = Column(String(50), default="free")  # free, pro, enterprise
    storage_quota = Column(BigInteger, default=1073741824) # 1GB
    storage_used = Column(BigInteger, default=0)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

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


class DocumentReview(Base):
    """文档审查记录"""
    __tablename__ = "document_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    review_type = Column(String(50))  # legal, compliance, risk, general
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    annotations = Column(Text, nullable=True)  # JSON 格式的批注列表
    summary = Column(Text, nullable=True)  # 审查总结
    risk_level = Column(String(20), nullable=True)  # low, medium, high, critical
    ai_model = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class Workflow(Base):
    """工作流定义"""
    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(255))
    description = Column(Text, nullable=True)
    nodes = Column(Text)  # JSON 格式的节点定义
    edges = Column(Text)  # JSON 格式的边定义
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WorkflowExecution(Base):
    """工作流执行记录"""
    __tablename__ = "workflow_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    input_file_ids = Column(ARRAY(UUID(as_uuid=True)))
    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    current_node = Column(String(100), nullable=True)
    node_results = Column(Text, nullable=True)  # JSON 格式的每个节点执行结果
    output_file_id = Column(UUID(as_uuid=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AudioTranscription(Base):
    """音频转录记录"""
    __tablename__ = "audio_transcriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    audio_file_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    transcript = Column(Text, nullable=True)  # 原始转录文本
    speakers = Column(Text, nullable=True)  # JSON 格式的说话人分离结果
    summary = Column(Text, nullable=True)  # 会议纪要摘要
    action_items = Column(Text, nullable=True)  # JSON 格式的行动项
    result_file_id = Column(UUID(as_uuid=True), nullable=True)  # 生成的会议纪要文档
    ai_model = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class DocumentVersion(Base):
    """文档版本历史"""
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    minio_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    change_description = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WebhookConfig(Base):
    """Webhook 配置"""
    __tablename__ = "webhook_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    events = Column(ARRAY(String), nullable=False)  # task_completed, document_uploaded, review_completed, etc.
    is_active = Column(Boolean, default=True)
    secret = Column(String(255), nullable=True)  # 用于签名验证
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_triggered = Column(DateTime(timezone=True), nullable=True)


class SystemStats(Base):
    """系统统计数据（按天汇总）"""
    __tablename__ = "system_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    total_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    total_documents = Column(Integer, default=0)
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    storage_used = Column(BigInteger, default=0)
    ai_calls = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
