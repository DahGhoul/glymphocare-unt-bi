"""Respaldo opcional en Amazon S3 para archivos CSV y reportes PDF (AWS)."""

from __future__ import annotations

from app.core.config import get_settings


def upload_bytes_to_s3(key: str, content: bytes, content_type: str) -> str | None:
    """Sube un objeto a S3 si AWS_S3_BUCKET esta configurado; retorna la clave S3 o None."""
    settings = get_settings()
    if not settings.aws_s3_bucket:
        return None
    try:
        import boto3

        client = boto3.client("s3", region_name=settings.aws_region)
        client.put_object(Bucket=settings.aws_s3_bucket, Key=key, Body=content, ContentType=content_type)
        return f"s3://{settings.aws_s3_bucket}/{key}"
    except Exception:
        return None
