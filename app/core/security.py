from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from itsdangerous import URLSafeSerializer

from app.core.settings import settings


serializer = URLSafeSerializer(settings.secret_key, salt="bioage-session")


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_code(length: int = 6) -> str:
    # numeric-like code
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def expires_in(minutes: int = 10) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)


def sign_session(user_id: str) -> str:
    return serializer.dumps({"user_id": user_id})


def unsign_session(token: str) -> str | None:
    try:
        data = serializer.loads(token)
        return data.get("user_id")
    except Exception:
        return None
