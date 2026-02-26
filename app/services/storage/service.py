from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import quote

from app.core.settings import settings


def _is_http(url: str) -> bool:
    v = (url or "").lower()
    return v.startswith("http://") or v.startswith("https://")


def is_s3_ref(value: str | None) -> bool:
    return bool(value and value.startswith("s3://"))


def is_local_static_ref(value: str | None) -> bool:
    return bool(value and value.startswith("/static/"))


def is_local_abs_path(value: str | None) -> bool:
    return bool(value and os.path.isabs(value) and value.startswith("/"))


def _s3_key_from_ref(ref: str) -> str:
    # ref format: s3://bucket/key
    return ref.split("/", 3)[3]


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        endpoint_url=settings.s3_endpoint_url,
    )


def _ensure_local_dirs() -> None:
    os.makedirs(settings.report_dir, exist_ok=True)
    os.makedirs(settings.uploads_dir, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads"), exist_ok=True)


def store_report(filename: str, data: bytes) -> str:
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("storage_backend=s3 but S3_BUCKET is not configured")
        key = f"{settings.s3_reports_prefix}/{datetime.utcnow().strftime('%Y/%m/%d')}/{filename}"
        _s3_client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType="application/pdf")
        return f"s3://{settings.s3_bucket}/{key}"

    _ensure_local_dirs()
    path = os.path.join(settings.report_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    return path


def store_upload(filename: str, data: bytes, content_type: str | None = None) -> str:
    safe_name = filename.replace("\\", "_").replace("/", "_")
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("storage_backend=s3 but S3_BUCKET is not configured")
        key = f"{settings.s3_uploads_prefix}/{datetime.utcnow().strftime('%Y/%m/%d')}/{safe_name}"
        kwargs = {"Bucket": settings.s3_bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        _s3_client().put_object(**kwargs)
        return f"s3://{settings.s3_bucket}/{key}"

    _ensure_local_dirs()
    abs_path = os.path.join(settings.uploads_dir, safe_name)
    with open(abs_path, "wb") as f:
        f.write(data)
    # Keep UI-friendly path if upload dir is under static root fallback
    return abs_path


def presigned_download_url(ref: str) -> str | None:
    if not is_s3_ref(ref):
        return None
    if not settings.s3_bucket:
        return None
    key = _s3_key_from_ref(ref)
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_presign_expiry_seconds,
    )


def media_view_url(ref: str | None) -> str:
    if not ref:
        return ""
    if _is_http(ref) or is_local_static_ref(ref):
        return ref
    if is_s3_ref(ref):
        if settings.s3_public_base_url:
            key = _s3_key_from_ref(ref)
            return f"{settings.s3_public_base_url.rstrip('/')}/{quote(key)}"
        signed = presigned_download_url(ref)
        return signed or ""
    if is_local_abs_path(ref):
        # Not web-accessible as path. Keep empty to avoid leaking server internals in UI.
        return ""
    return ref
