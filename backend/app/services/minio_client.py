from minio import Minio
from app.core.config import get_settings
import io

settings = get_settings()

class MinioClient:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_SECURE
        )
        self._ensure_buckets()

    def _ensure_buckets(self):
        for bucket in [settings.MINIO_BUCKET_UPLOADS, settings.MINIO_BUCKET_OUTPUTS]:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)

    def upload_file(self, file_data: bytes, filename: str, content_type: str) -> str:
        result = self.client.put_object(
            settings.MINIO_BUCKET_UPLOADS,
            filename,
            io.BytesIO(file_data),
            len(file_data),
            content_type=content_type
        )
        return f"{settings.MINIO_BUCKET_UPLOADS}/{filename}"

    def get_file_url(self, bucket: str, filename: str) -> str:
        return self.client.presigned_get_object(bucket, filename)

    def get_file_content(self, bucket: str, filename: str) -> bytes:
        response = self.client.get_object(bucket, filename)
        try:
            return response.read()
        finally:
            response.close()
            
minio_client = MinioClient()
