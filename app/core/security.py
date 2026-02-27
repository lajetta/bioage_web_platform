from __future__ import annotations

import hashlib
import secrets
import hmac
from datetime import datetime, timedelta, timezone

from itsdangerous import URLSafeTimedSerializer

from app.core.settings import settings


serializer = URLSafeTimedSerializer(settings.secret_key, salt="bioage-session")
csrf_serializer = URLSafeTimedSerializer(settings.secret_key, salt="bioage-csrf")
signup_serializer = URLSafeTimedSerializer(settings.secret_key, salt="bioage-signup")


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
        data = serializer.loads(token, max_age=settings.session_max_age_seconds)
        return data.get("user_id")
    except Exception:
        return None


def sign_csrf() -> str:
    return csrf_serializer.dumps({"nonce": secrets.token_hex(16)})


def verify_csrf(token: str) -> bool:
    try:
        csrf_serializer.loads(token, max_age=settings.csrf_max_age_seconds)
        return True
    except Exception:
        return False


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        scheme, salt, expected = password_hash.split("$", 2)
        if scheme != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000)
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def sign_signup_token(payload: dict) -> str:
    return signup_serializer.dumps(payload)


def unsign_signup_token(token: str, max_age_seconds: int = 1200) -> dict | None:
    try:
        data = signup_serializer.loads(token, max_age=max_age_seconds)
        return data if isinstance(data, dict) else None
    except Exception:
        return None
