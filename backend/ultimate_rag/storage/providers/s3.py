"""S3-compatible object storage provider (optional).

Used when ``UPLOAD_STORAGE_PROVIDER=s3``. Requires ``boto3``. Falls back
gracefully when the dependency or credentials are unavailable.
"""

from __future__ import annotations

import asyncio
import io
import logging

from ultimate_rag.core.ids import new_id
from ultimate_rag.core.security import sanitize_filename
from ultimate_rag.storage.interface import FileStorage, StoredFile

logger = logging.getLogger("ultimate_rag.storage.s3")


class S3FileStorage(FileStorage):
    name = "s3"

    def __init__(self, settings):
        super().__init__(settings)
        self._bucket = getattr(settings, "s3_bucket", "ultimate-rag-uploads")
        try:
            import boto3

            self._s3 = boto3.resource(
                "s3",
                endpoint_url=getattr(settings, "s3_endpoint_url", None),
                aws_access_key_id=getattr(settings, "s3_access_key", None),
                aws_secret_access_key=getattr(settings, "s3_secret_key", None),
            )
        except Exception as e:
            logger.warning("boto3 unavailable, S3 storage disabled: %s", e)
            self._s3 = None

    async def save(self, original_name: str, data: bytes) -> StoredFile:
        file_id = new_id()
        key = f"{file_id}_{sanitize_filename(original_name)}"

        def _put() -> str:
            self._s3.Bucket(self._bucket).put_object(Key=key, Body=io.BytesIO(data))
            return key

        key = await asyncio.to_thread(_put)
        return StoredFile(
            file_id=file_id,
            filename=sanitize_filename(original_name),
            path=f"s3://{self._bucket}/{key}",
            size=len(data),
        )

    async def read(self, file_id: str) -> bytes:
        from botocore.exceptions import ClientError

        def _get() -> bytes:
            return self._s3.Bucket(self._bucket).Object(file_id).get()["Body"].read()

        try:
            return await asyncio.to_thread(_get)
        except ClientError as exc:
            raise FileNotFoundError(f"Stored file {file_id} not found") from exc

    async def delete(self, file_id: str) -> bool:
        import asyncio

        from botocore.exceptions import ClientError

        def _del() -> bool:
            try:
                self._s3.Bucket(self._bucket).Object(file_id).delete()
                return True
            except ClientError:
                return False

        return await asyncio.to_thread(_del)

    async def exists(self, file_id: str) -> bool:
        def _exists() -> bool:
            try:
                return self._s3.Bucket(self._bucket).Object(file_id).content_length is not None
            except Exception:
                return False

        return await asyncio.to_thread(_exists)
