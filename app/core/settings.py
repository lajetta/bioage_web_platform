from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    # App
    app_name: str = "BioAge Reset Protocol"
    base_url: str = "http://localhost:8000"
    secret_key: str = "CHANGE_ME"
    environment: str = "dev"  # dev|prod
    allowed_hosts: str = "*"
    enforce_https: bool = False
    session_max_age_seconds: int = 60 * 60 * 24 * 30
    session_cookie_name: str = "session_token"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"  # lax|strict|none
    csrf_cookie_name: str = "csrf_token"
    csrf_max_age_seconds: int = 60 * 60 * 12

    # Database
    database_url: str = "postgresql+asyncpg://bioage:bioage@db:5432/bioage"

    # Email (SMTP)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = 20
    email_send_retries: int = 3

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.2"

    # Payments (Stripe)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id_monthly: str | None = None
    stripe_price_id_pro: str | None = None
    stripe_price_id_premium: str | None = None
    payments_mode: str = "mock"  # mock|stripe

    # RQ/Redis
    redis_url: str = "redis://redis:6379/0"
    rate_limit_login_ip_limit: int = 10
    rate_limit_login_ip_window_seconds: int = 60
    rate_limit_login_email_limit: int = 5
    rate_limit_login_email_window_seconds: int = 300
    rate_limit_verify_ip_limit: int = 20
    rate_limit_verify_ip_window_seconds: int = 60
    rate_limit_verify_email_limit: int = 8
    rate_limit_verify_email_window_seconds: int = 300

    # Storage
    storage_backend: str = "local"  # local|s3
    report_dir: str = "/data/reports"
    uploads_dir: str = "/data/uploads"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_endpoint_url: str | None = None
    s3_public_base_url: str | None = None
    s3_presign_expiry_seconds: int = 3600
    s3_reports_prefix: str = "reports"
    s3_uploads_prefix: str = "uploads"

    # Optional: bootstrap admins by email (comma-separated)
    admin_emails: str | None = None


settings = Settings()
