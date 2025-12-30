from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "DocAI-MCP"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Backend URLs
    # Public URL is for browsers; internal URL is for other containers (e.g., OnlyOffice)
    BACKEND_PUBLIC_URL: str | None = None
    BACKEND_INTERNAL_URL: str = "http://backend:8000"
    
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: str | None = None
    
    # MinIO
    MINIO_ENDPOINT: str
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_BUCKET_UPLOADS: str = "uploads"
    MINIO_BUCKET_OUTPUTS: str = "outputs"
    MINIO_SECURE: bool = False
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # OnlyOffice
    ONLYOFFICE_API_URL: str # Internal URL for backend callbacks
    ONLYOFFICE_PUBLIC_URL: str | None = None # Public URL for frontend JS
    JWT_SECRET: str
    
    # AI Config
    AI_API_KEY: str | None = None
    AI_API_BASE_URL: str | None = None
    AI_MODEL_NAME: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore" # Ignore extra fields in .env

    def model_post_init(self, __context):
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

@lru_cache()
def get_settings():
    return Settings()
