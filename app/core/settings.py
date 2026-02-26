from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    # App
    app_name: str = "BioAge Reset Protocol"
    base_url: str = "http://localhost:8000"
    secret_key: str = "CHANGE_ME"
    environment: str = "dev"  # dev|prod

    # Database
    database_url: str = "postgresql+asyncpg://bioage:bioage@db:5432/bioage"

    # Email (SMTP)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None

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

    # Optional: bootstrap admins by email (comma-separated)
    admin_emails: str | None = None


settings = Settings()
