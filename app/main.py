from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select

from app.core.i18n import get_lang, t
from app.core.questions import QUESTIONS, validate_answer
from app.core.security import (
    expires_in,
    generate_code,
    hash_code,
    hash_password,
    sign_csrf,
    sign_session,
    sign_signup_token,
    unsign_session,
    unsign_signup_token,
    verify_csrf,
    verify_password,
)
from app.core.settings import settings
from app.db.session import SessionLocal
from app.db import models
from app.services.email.service import send_login_code_email
from app.services.payments.service import create_checkout
from app.services.report.pdf import build_pdf
from app.services.subscriptions.service import (
    PLAN_FEATURES,
    can_generate_report,
    get_current_plan_id,
    get_latest_subscription,
    has_plan_access,
    upsert_subscription,
)
from app.services.storage.service import is_s3_ref, media_view_url, presigned_download_url, store_upload

import redis
from rq import Queue


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(title=settings.app_name)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if settings.allowed_hosts and settings.allowed_hosts.strip() != "*":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[h.strip() for h in settings.allowed_hosts.split(",") if h.strip()])


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    if settings.enforce_https:
        forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
        is_secure = forwarded_proto == "https" or request.url.scheme == "https"
        if not is_secure:
            https_url = str(request.url.replace(scheme="https"))
            return RedirectResponse(https_url, status_code=307)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.enforce_https:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "media-src 'self' https: blob:; "
        "frame-src https://www.youtube.com https://player.vimeo.com; "
        "connect-src 'self' https:; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["Content-Security-Policy"] = csp
    return response


@app.on_event("startup")
async def startup_bootstrap_admins() -> None:
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    if not settings.admin_emails:
        return
    emails = [e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()]
    if not emails:
        return
    async with SessionLocal() as db:
        q = select(models.User).where(models.User.email.in_(emails))
        res = await db.execute(q)
        users = list(res.scalars().all())
        for u in users:
            u.is_admin = True
        await db.commit()


async def get_db():
    async with SessionLocal() as session:
        yield session


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db=Depends(get_db),
) -> models.User | None:
    if not session_token:
        return None
    user_id = unsign_session(session_token)
    if not user_id:
        return None
    return await db.get(models.User, user_id)


def _render(request: Request, name: str, context: dict):
    lang = get_lang(request)
    base = {
        "request": request,
        "lang": lang,
        "t": lambda k: t(lang, k),
        "supported_langs": ("en", "uk", "ru"),
        "app_name": settings.app_name,
        "settings": settings,
    }
    base.update(context)
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    csrf_token = csrf_cookie if csrf_cookie and verify_csrf(csrf_cookie) else sign_csrf()
    base["csrf_token"] = csrf_token
    resp = templates.TemplateResponse(name, base)
    if csrf_cookie != csrf_token:
        resp.set_cookie(
            settings.csrf_cookie_name,
            csrf_token,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            max_age=settings.csrf_max_age_seconds,
        )
    return resp


def _localize_validation_error(lang: str, error: str) -> str:
    mapping = {
        "This field is required": "error_required",
        "Please enter a number": "error_number",
        "Invalid choice": "error_invalid_choice",
    }
    return t(lang, mapping.get(error, error))


def _verify_csrf_or_403(request: Request, csrf_token: str) -> None:
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    if not csrf_token or not cookie_token or csrf_token != cookie_token or not verify_csrf(csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def _rate_limit_ok(key: str, limit: int, window_seconds: int) -> bool:
    try:
        conn = redis.from_url(settings.redis_url)
        count = conn.incr(key)
        if count == 1:
            conn.expire(key, window_seconds)
        return int(count) <= int(limit)
    except Exception:
        # fail open if redis is unavailable; availability first
        return True


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    return (request.client.host if request.client else "") or "unknown"


async def _get_site_content(db) -> models.SiteContent:
    content = await db.get(models.SiteContent, 1)
    if content:
        return content

    content = models.SiteContent(
        id=1,
        founder_name="Founder",
        founder_intro="I built this protocol to make practical longevity guidance simple and measurable.",
        founder_photo_url="",
        founder_video_url="",
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


def _normalize_video_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""

    parsed = urlparse(value)
    host = (parsed.netloc or "").lower()
    if "youtube.com" in host and parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"
    if "youtu.be" in host:
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

    return value


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug[:96]


def _normalize_username(value: str) -> str:
    username = (value or "").strip()
    username = re.sub(r"\s+", "_", username)
    username = re.sub(r"[^A-Za-z0-9_.-]", "", username)
    return username[:64]


def _normalize_name(value: str, *, max_len: int = 100) -> str:
    return (value or "").strip()[:max_len]


def _validate_signup_password(password: str) -> str | None:
    if len(password) < 10:
        return "error_password_too_short"
    if not re.search(r"[A-Z]", password):
        return "error_password_missing_upper"
    if not re.search(r"[a-z]", password):
        return "error_password_missing_lower"
    if not re.search(r"[0-9]", password):
        return "error_password_missing_digit"
    if not re.search(r"[^A-Za-z0-9]", password):
        return "error_password_missing_special"
    return None


def _is_embed_video_url(url: str) -> bool:
    value = (url or "").lower()
    return "youtube.com/embed/" in value or "player.vimeo.com/video/" in value


def _upload_ext(filename: str, content_type: str | None) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext and len(ext) <= 8 and ext[1:].isalnum():
        return ext
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "application/pdf": ".pdf",
        "text/plain": ".txt",
    }
    return mapping.get((content_type or "").lower(), "")


async def _save_upload(
    upload: UploadFile,
    *,
    allowed_prefix: str,
    allowed_exts: set[str],
    max_bytes: int,
    name_prefix: str,
    invalid_type_key: str,
    too_large_key: str,
) -> str:
    content_type = (upload.content_type or "").lower()
    ext = _upload_ext(upload.filename or "", content_type)
    if not content_type.startswith(allowed_prefix) and ext not in allowed_exts:
        raise ValueError(invalid_type_key)

    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(too_large_key)

    filename = f"{name_prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(6).hex()}{ext or ''}"
    if settings.storage_backend == "s3":
        return store_upload(filename, data, content_type=content_type)

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    path = os.path.join(UPLOADS_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    return f"/static/uploads/{filename}"


def _normalize_plan_id(value: str | None) -> str:
    return value if value in {"free", "pro", "premium"} else "free"


def _report_filename(report: models.Report) -> str:
    return f"bioage_report_{report.id}.pdf"


async def _admin_context(db, user: models.User, *, saved: bool, error: str | None):
    site_content = await _get_site_content(db)
    q_updates = select(models.MonthlyUpdate).where(models.MonthlyUpdate.status == "pending_review").order_by(models.MonthlyUpdate.created_at.asc())
    res_updates = await db.execute(q_updates)
    updates = list(res_updates.scalars().all())

    q_categories = select(models.TutorialCategory).order_by(models.TutorialCategory.created_at.desc())
    res_categories = await db.execute(q_categories)
    categories = list(res_categories.scalars().all())

    q_tutorials = (
        select(models.Tutorial, models.TutorialCategory.title)
        .join(models.TutorialCategory, models.Tutorial.category_id == models.TutorialCategory.id)
        .order_by(models.Tutorial.created_at.desc())
    )
    res_tutorials = await db.execute(q_tutorials)
    tutorials = [{"tutorial": t, "category_title": ctitle} for t, ctitle in res_tutorials.all()]

    return {
        "user": user,
        "updates": updates,
        "site_content": site_content,
        "saved": saved,
        "error": error,
        "tutorial_categories": categories,
        "tutorials_admin": tutorials,
    }


@app.get("/lang/{code}")
async def set_lang(code: str, request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    if code not in ("en", "uk", "ru"):
        raise HTTPException(400, "Unsupported language")
    if user and user.language != code:
        user.language = code
        await db.commit()
    resp = RedirectResponse(url=request.headers.get("referer") or "/", status_code=302)
    resp.set_cookie("lang", code, max_age=60 * 60 * 24 * 365, secure=settings.session_cookie_secure, samesite=settings.session_cookie_samesite)
    return resp


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    site_content = await _get_site_content(db)
    founder_photo_url = media_view_url(site_content.founder_photo_url)
    founder_video_url = media_view_url(site_content.founder_video_url)
    return _render(
        request,
        "home.html",
        {
            "user": user,
            "site_content": site_content,
            "founder_photo_url": founder_photo_url,
            "founder_video_url": founder_video_url,
            "founder_video_is_embed": _is_embed_video_url(founder_video_url),
        },
    )


@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    current_plan = "free"
    if user:
        current_plan = await get_current_plan_id(db, user.id)
    return _render(request, "pricing.html", {"user": user, "current_plan": current_plan, "plans": PLAN_FEATURES})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    mode = (request.query_params.get("mode") or "signup").strip().lower()
    if mode not in {"signup", "signin"}:
        mode = "signup"
    return _render(
        request,
        "login.html",
        {
            "user": None,
            "signup_error": None,
            "signin_error": None,
            "signup_form": {"email": "", "username": "", "first_name": "", "last_name": ""},
            "signin_form": {"email": ""},
            "auth_mode": mode,
        },
    )


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
    return resp


@app.post("/signup/request-code")
async def signup_request_code(
    request: Request,
    username: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(...),
    password: str = Form(""),
    password_confirm: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    from email_validator import validate_email, EmailNotValidError

    _verify_csrf_or_403(request, csrf_token)
    lang = get_lang(request)
    username_norm = _normalize_username(username)
    first_name_norm = _normalize_name(first_name)
    last_name_norm = _normalize_name(last_name)
    if not username_norm:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_username_required"),
                "signin_error": None,
                "signup_form": {"email": email, "username": username, "first_name": first_name, "last_name": last_name},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )
    if not first_name_norm:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_first_name_required"),
                "signin_error": None,
                "signup_form": {"email": email, "username": username_norm, "first_name": first_name, "last_name": last_name},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )
    if not last_name_norm:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_last_name_required"),
                "signin_error": None,
                "signup_form": {"email": email, "username": username_norm, "first_name": first_name_norm, "last_name": last_name},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )
    password_error_key = _validate_signup_password(password)
    if password_error_key:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, password_error_key),
                "signin_error": None,
                "signup_form": {"email": email, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )
    if password != password_confirm:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_password_mismatch"),
                "signin_error": None,
                "signup_form": {"email": email, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )

    client_ip = _client_ip(request)
    if not _rate_limit_ok(
        f"rl:login:ip:{client_ip}",
        settings.rate_limit_login_ip_limit,
        settings.rate_limit_login_ip_window_seconds,
    ):
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_rate_limited"),
                "signin_error": None,
                "signup_form": {"email": email, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )

    try:
        email_norm = validate_email(email, check_deliverability=False).email
    except EmailNotValidError:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_invalid_email"),
                "signin_error": None,
                "signup_form": {"email": email, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )

    existing_by_email_q = select(models.User).where(models.User.email == email_norm)
    existing_by_email_res = await db.execute(existing_by_email_q)
    existing_by_email = existing_by_email_res.scalars().first()

    existing_by_username_q = select(models.User).where(models.User.username == username_norm)
    existing_by_username_res = await db.execute(existing_by_username_q)
    existing_by_username = existing_by_username_res.scalars().first()

    if existing_by_email:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_signup_email_exists"),
                "signin_error": None,
                "signup_form": {"email": email_norm, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )
    if existing_by_username and existing_by_username.email != email_norm:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_signup_username_taken"),
                "signin_error": None,
                "signup_form": {"email": email_norm, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )

    if not _rate_limit_ok(
        f"rl:login:email:{email_norm}",
        settings.rate_limit_login_email_limit,
        settings.rate_limit_login_email_window_seconds,
    ):
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_rate_limited"),
                "signin_error": None,
                "signup_form": {"email": email_norm, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )

    code = generate_code()
    code_h = hash_code(code)

    # store code
    rec = models.MagicLoginCode(email=email_norm, code_hash=code_h, expires_at=expires_in(10), used=False)
    db.add(rec)
    await db.commit()

    if not send_login_code_email(to_email=email_norm, code=code, lang=lang):
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": t(lang, "error_email_send_failed"),
                "signin_error": None,
                "signup_form": {"email": email_norm, "username": username_norm, "first_name": first_name_norm, "last_name": last_name_norm},
                "signin_form": {"email": ""},
                "auth_mode": "signup",
            },
        )

    signup_token = sign_signup_token(
        {
            "email": email_norm,
            "username": username_norm,
            "first_name": first_name_norm,
            "last_name": last_name_norm,
            "password_hash": hash_password(password),
            "language": lang,
        }
    )

    # In dev, show a hint if SMTP is not configured
    hint = None
    if not settings.smtp_host:
        hint = code

    resp = _render(
        request,
        "verify.html",
        {
            "email": email_norm,
            "hint": hint,
            "error": None,
            "username": username_norm,
            "signup_token": signup_token,
            "auth_mode": "signup",
        },
    )
    return resp


@app.post("/verify")
async def verify_code(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    signup_token: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    _verify_csrf_or_403(request, csrf_token)
    lang = get_lang(request)
    email = email.strip().lower()
    payload = unsign_signup_token(signup_token)
    if not payload:
        return _render(request, "login.html", {"user": None, "signup_error": t(lang, "error_signup_session_expired"), "signin_error": None, "signup_form": {"email": email, "username": "", "first_name": "", "last_name": ""}, "signin_form": {"email": ""}, "auth_mode": "signup"})
    if payload.get("email") != email:
        return _render(request, "login.html", {"user": None, "signup_error": t(lang, "error_signup_session_expired"), "signin_error": None, "signup_form": {"email": email, "username": "", "first_name": "", "last_name": ""}, "signin_form": {"email": ""}, "auth_mode": "signup"})

    username_norm = _normalize_username(payload.get("username", ""))
    first_name_norm = _normalize_name(payload.get("first_name", ""))
    last_name_norm = _normalize_name(payload.get("last_name", ""))
    password_hash_value = (payload.get("password_hash", "") or "").strip()
    language = payload.get("language", lang)
    if not username_norm or not first_name_norm or not last_name_norm or not password_hash_value:
        return _render(request, "login.html", {"user": None, "signup_error": t(lang, "error_signup_session_expired"), "signin_error": None, "signup_form": {"email": email, "username": "", "first_name": "", "last_name": ""}, "signin_form": {"email": ""}, "auth_mode": "signup"})

    client_ip = _client_ip(request)
    if not _rate_limit_ok(
        f"rl:verify:ip:{client_ip}",
        settings.rate_limit_verify_ip_limit,
        settings.rate_limit_verify_ip_window_seconds,
    ):
        return _render(
            request,
            "verify.html",
            {
                "email": email,
                "hint": None,
                "error": t(lang, "error_rate_limited"),
                "username": username_norm,
                "signup_token": signup_token,
            },
        )
    if not _rate_limit_ok(
        f"rl:verify:email:{email}",
        settings.rate_limit_verify_email_limit,
        settings.rate_limit_verify_email_window_seconds,
    ):
        return _render(
            request,
            "verify.html",
            {
                "email": email,
                "hint": None,
                "error": t(lang, "error_rate_limited"),
                "username": username_norm,
                "signup_token": signup_token,
            },
        )
    code_h = hash_code(code.strip())

    q = select(models.MagicLoginCode).where(
        models.MagicLoginCode.email == email,
        models.MagicLoginCode.used == False,  # noqa: E712
        models.MagicLoginCode.expires_at > datetime.now(tz=timezone.utc),
    ).order_by(models.MagicLoginCode.created_at.desc())
    res = await db.execute(q)
    rec = res.scalars().first()

    if not rec or rec.code_hash != code_h:
        return _render(
            request,
            "verify.html",
            {
                "email": email,
                "hint": None,
                "error": t(lang, "error_wrong_code"),
                "username": username_norm,
                "signup_token": signup_token,
            },
        )

    uq = select(models.User).where(models.User.email == email)
    ures = await db.execute(uq)
    user = ures.scalars().first()

    if user:
        return _render(
            request,
            "verify.html",
            {
                "email": email,
                "hint": None,
                "error": t(lang, "error_signup_email_exists"),
                "username": username_norm,
                "signup_token": signup_token,
            },
        )

    existing_by_username_q = select(models.User).where(models.User.username == username_norm)
    existing_by_username_res = await db.execute(existing_by_username_q)
    existing_by_username = existing_by_username_res.scalars().first()
    if existing_by_username and existing_by_username.email != email:
        return _render(
            request,
            "verify.html",
            {
                "email": email,
                "hint": None,
                "error": t(lang, "error_signup_username_taken"),
                "username": username_norm,
                "signup_token": signup_token,
            },
        )

    user = models.User(
        email=email,
        language=language if language in ("en", "uk", "ru") else get_lang(request),
        username=username_norm,
        first_name=first_name_norm,
        last_name=last_name_norm,
        password_hash=password_hash_value,
    )
    db.add(user)
    await db.flush()

    rec.used = True
    await db.commit()

    token = sign_session(user.id)
    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_max_age_seconds,
    )
    return resp


@app.post("/signin")
async def signin_password(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    from email_validator import validate_email, EmailNotValidError

    _verify_csrf_or_403(request, csrf_token)
    lang = get_lang(request)
    try:
        email_norm = validate_email(email, check_deliverability=False).email
    except EmailNotValidError:
        email_norm = ""

    if not email_norm or not password:
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": None,
                "signin_error": t(lang, "error_signin_invalid_credentials"),
                "signup_form": {"email": "", "username": "", "first_name": "", "last_name": ""},
                "signin_form": {"email": email},
                "auth_mode": "signin",
            },
        )

    client_ip = _client_ip(request)
    if not _rate_limit_ok(
        f"rl:signin:ip:{client_ip}",
        settings.rate_limit_login_ip_limit,
        settings.rate_limit_login_ip_window_seconds,
    ):
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": None,
                "signin_error": t(lang, "error_rate_limited"),
                "signup_form": {"email": "", "username": "", "first_name": "", "last_name": ""},
                "signin_form": {"email": email_norm},
                "auth_mode": "signin",
            },
        )

    q = select(models.User).where(models.User.email == email_norm)
    res = await db.execute(q)
    user = res.scalars().first()
    if not user or not verify_password(password, user.password_hash):
        return _render(
            request,
            "login.html",
            {
                "user": None,
                "signup_error": None,
                "signin_error": t(lang, "error_signin_invalid_credentials"),
                "signup_form": {"email": "", "username": "", "first_name": "", "last_name": ""},
                "signin_form": {"email": email_norm},
                "auth_mode": "signin",
            },
        )

    current_lang = get_lang(request)
    if user.language != current_lang:
        user.language = current_lang
        await db.commit()

    token = sign_session(user.id)
    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_max_age_seconds,
    )
    return resp


@app.get("/assessment", response_class=HTMLResponse)
async def assessment_start(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    assessment = models.Assessment(user_id=user.id, status="in_progress", answers={})
    db.add(assessment)
    await db.commit()

    return RedirectResponse(f"/assessment/{assessment.id}/1", status_code=302)

@app.get("/assessment/{assessment_id}/done", response_class=HTMLResponse)
async def assessment_done(request: Request, assessment_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    assessment = await db.get(models.Assessment, assessment_id)
    if not assessment or assessment.user_id != user.id:
        raise HTTPException(404)

    return _render(request, "assessment_done.html", {"user": user, "assessment": assessment})


@app.get("/assessment/{assessment_id}/{step}", response_class=HTMLResponse)
async def assessment_step(request: Request, assessment_id: str, step: int, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    assessment = await db.get(models.Assessment, assessment_id)
    if not assessment or assessment.user_id != user.id:
        raise HTTPException(404)

    if step < 1 or step > len(QUESTIONS):
        raise HTTPException(404)

    q = QUESTIONS[step - 1]
    existing = (assessment.answers or {}).get(q.qid, "")

    return _render(
        request,
        "assessment_step.html",
        {
            "user": user,
            "assessment": assessment,
            "step": step,
            "total": len(QUESTIONS),
            "q": q,
            "label": q.label(get_lang(request)),
            "existing": existing,
            "error": None,
        },
    )


@app.post("/assessment/{assessment_id}/{step}")
async def assessment_step_post(
    request: Request,
    assessment_id: str,
    step: int,
    value: str = Form(""),
    csrf_token: str = Form(""),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    _verify_csrf_or_403(request, csrf_token)

    assessment = await db.get(models.Assessment, assessment_id)
    if not assessment or assessment.user_id != user.id:
        raise HTTPException(404)
    if step < 1 or step > len(QUESTIONS):
        raise HTTPException(404)

    q = QUESTIONS[step - 1]

    try:
        v = validate_answer(q, value)
    except ValueError as e:
        lang = get_lang(request)
        return _render(
            request,
            "assessment_step.html",
            {
                "user": user,
                "assessment": assessment,
                "step": step,
                "total": len(QUESTIONS),
                "q": q,
                "label": q.label(get_lang(request)),
                "existing": value,
                "error": _localize_validation_error(lang, str(e)),
            },
        )

    answers = dict(assessment.answers or {})
    answers[q.qid] = v
    assessment.answers = answers

    if step == len(QUESTIONS):
        assessment.status = "completed"
        assessment.completed_at = datetime.now(tz=timezone.utc)
        await db.commit()
        return RedirectResponse(f"/assessment/{assessment.id}/done", status_code=302)

    await db.commit()
    return RedirectResponse(f"/assessment/{assessment.id}/{step+1}", status_code=302)


# @app.get("/assessment/{assessment_id}/done", response_class=HTMLResponse)
# async def assessment_done(request: Request, assessment_id: str, user=Depends(get_current_user), db=Depends(get_db)):
#     if not user:
#         return RedirectResponse("/login", status_code=302)

#     assessment = await db.get(models.Assessment, assessment_id)
#     if not assessment or assessment.user_id != user.id:
#         raise HTTPException(404)

#     return _render(request, "assessment_done.html", {"user": user, "assessment": assessment})


@app.post("/report/{assessment_id}/start")
async def start_report_generation(request: Request, assessment_id: str, csrf_token: str = Form(""), user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    _verify_csrf_or_403(request, csrf_token)

    assessment = await db.get(models.Assessment, assessment_id)
    if not assessment or assessment.user_id != user.id or assessment.status != "completed":
        raise HTTPException(400)

    allowed, _plan_id = await can_generate_report(db, user.id)
    if not allowed:
        return RedirectResponse("/pricing?upgrade=1", status_code=302)
    current_lang = get_lang(request)
    if user.language != current_lang:
        user.language = current_lang

    report = models.Report(user_id=user.id, assessment_id=assessment.id, status="queued")
    db.add(report)
    await db.flush()

    conn = redis.from_url(settings.redis_url)
    q_ = Queue(connection=conn)
    q_.enqueue("app.services.report.tasks.generate_and_send_report", report.id)

    await db.commit()
    return RedirectResponse("/dashboard?report=queued", status_code=302)


@app.post("/billing/checkout/{plan_id}")
async def billing_checkout(request: Request, plan_id: str, csrf_token: str = Form(""), user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    _verify_csrf_or_403(request, csrf_token)
    if plan_id not in {"pro", "premium"}:
        raise HTTPException(400, "Unsupported plan")

    checkout = create_checkout(user.id, user.email, plan_id=plan_id)
    payment = models.Payment(
        user_id=user.id,
        provider=checkout.provider,
        status="pending",
        amount="29" if plan_id == "pro" else "79",
        currency="EUR",
        provider_payload={"plan_id": plan_id},
    )
    db.add(payment)
    await db.commit()
    return RedirectResponse(checkout.url, status_code=302)


@app.get("/payments/mock/success")
async def mock_payment_success(plan: str = "pro", user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    if plan not in {"pro", "premium"}:
        raise HTTPException(400)

    # Mark latest pending payment as paid
    q = select(models.Payment).where(models.Payment.user_id == user.id).order_by(models.Payment.created_at.desc())
    res = await db.execute(q)
    p = res.scalars().first()
    if p:
        p.status = "paid"
        payload = dict(p.provider_payload or {})
        payload["plan_id"] = plan
        p.provider_payload = payload

    await upsert_subscription(
        db,
        user_id=user.id,
        provider="mock",
        plan_id=plan,
        status="active",
        provider_customer_id=None,
        provider_subscription_id=f"mock_{user.id}_{plan}",
        current_period_end=(datetime.now(tz=timezone.utc) + timedelta(days=30)).replace(microsecond=0),
        cancel_at_period_end=False,
        provider_payload={"source": "mock_success"},
    )

    await db.commit()
    return RedirectResponse("/dashboard?paid=1", status_code=302)


@app.post("/payments/stripe/webhook")
async def stripe_webhook(request: Request):
    if settings.payments_mode != "stripe":
        return PlainTextResponse("ignored", status_code=200)
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(500, "Stripe is not configured")

    import stripe

    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    async with SessionLocal() as db:
        if etype == "checkout.session.completed":
            user_id = (data.get("metadata") or {}).get("user_id")
            plan_id = (data.get("metadata") or {}).get("plan_id", "pro")
            if user_id and plan_id in {"pro", "premium"}:
                await upsert_subscription(
                    db,
                    user_id=user_id,
                    provider="stripe",
                    plan_id=plan_id,
                    status="active",
                    provider_customer_id=data.get("customer"),
                    provider_subscription_id=data.get("subscription"),
                    current_period_end=None,
                    cancel_at_period_end=False,
                    provider_payload=data,
                )
                await db.commit()

        if etype in {"customer.subscription.updated", "customer.subscription.deleted"}:
            provider_subscription_id = data.get("id")
            if provider_subscription_id:
                q = select(models.UserSubscription).where(models.UserSubscription.provider_subscription_id == provider_subscription_id)
                res = await db.execute(q)
                sub = res.scalars().first()
                if sub:
                    sub.status = data.get("status", "inactive")
                    sub.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
                    sub.provider_payload = data
                    ts = data.get("current_period_end")
                    if ts:
                        sub.current_period_end = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    await db.commit()

    return PlainTextResponse("ok", status_code=200)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    q = select(models.Report).where(models.Report.user_id == user.id).order_by(models.Report.created_at.desc())
    res = await db.execute(q)
    reports = list(res.scalars().all())
    current_plan = await get_current_plan_id(db, user.id)
    features = PLAN_FEATURES[current_plan]
    sub = await get_latest_subscription(db, user.id)

    return _render(
        request,
        "dashboard.html",
        {"user": user, "reports": reports, "current_plan": current_plan, "plan_features": features, "subscription": sub},
    )


@app.get("/reports/{report_id}/download")
async def download_report(report_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    report = await db.get(models.Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(404)
    if not report.file_path:
        if report.content_json:
            pdf_bytes = build_pdf(report.content_json, user.language)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{_report_filename(report)}"'},
            )
        raise HTTPException(404, "Report file is not ready")

    if is_s3_ref(report.file_path):
        signed_url = presigned_download_url(report.file_path, inline=False)
        if not signed_url:
            raise HTTPException(404, "Report file not found on storage")
        return RedirectResponse(signed_url, status_code=302)

    if report.file_path.startswith("/static/"):
        return RedirectResponse(report.file_path, status_code=302)

    if not os.path.isfile(report.file_path):
        if report.content_json:
            pdf_bytes = build_pdf(report.content_json, user.language)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{_report_filename(report)}"'},
            )
        raise HTTPException(404, "Report file not found on server")

    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=os.path.basename(report.file_path),
    )


@app.get("/reports/{report_id}/view")
async def view_report(report_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    report = await db.get(models.Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(404)
    if not report.file_path:
        if report.content_json:
            pdf_bytes = build_pdf(report.content_json, user.language)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{_report_filename(report)}"'},
            )
        raise HTTPException(404, "Report file is not ready")

    if is_s3_ref(report.file_path):
        filename = os.path.basename(report.file_path.split("/", 3)[-1]) if "/" in report.file_path else "report.pdf"
        signed_url = presigned_download_url(report.file_path, inline=True, filename=filename)
        if not signed_url:
            raise HTTPException(404, "Report file not found on storage")
        return RedirectResponse(signed_url, status_code=302)

    if report.file_path.startswith("/static/"):
        return RedirectResponse(report.file_path, status_code=302)

    if not os.path.isfile(report.file_path):
        if report.content_json:
            pdf_bytes = build_pdf(report.content_json, user.language)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{_report_filename(report)}"'},
            )
        raise HTTPException(404, "Report file not found on server")

    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{os.path.basename(report.file_path)}"'},
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    if not user or not user.is_admin:
        raise HTTPException(403)
    return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=None))


@app.get("/tutorials", response_class=HTMLResponse)
async def tutorials(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    plan_id = await get_current_plan_id(db, user.id)
    q = (
        select(models.Tutorial, models.TutorialCategory)
        .join(models.TutorialCategory, models.Tutorial.category_id == models.TutorialCategory.id)
        .where(models.Tutorial.is_active == True, models.TutorialCategory.is_active == True)  # noqa: E712
        .order_by(models.TutorialCategory.title.asc(), models.Tutorial.created_at.desc())
    )
    res = await db.execute(q)
    items = []
    for tutorial, category in res.all():
        if has_plan_access(plan_id, _normalize_plan_id(tutorial.required_plan)):
            items.append(
                {
                    "tutorial": tutorial,
                    "category": category,
                    "video_url": media_view_url(tutorial.video_url),
                    "file_url": media_view_url(tutorial.file_url),
                }
            )
    return _render(request, "tutorials.html", {"user": user, "tutorials": items, "current_plan": plan_id})


@app.get("/tutorials/{slug}", response_class=HTMLResponse)
async def tutorial_detail(slug: str, request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    q = (
        select(models.Tutorial, models.TutorialCategory)
        .join(models.TutorialCategory, models.Tutorial.category_id == models.TutorialCategory.id)
        .where(models.Tutorial.slug == slug, models.Tutorial.is_active == True, models.TutorialCategory.is_active == True)  # noqa: E712
    )
    res = await db.execute(q)
    row = res.first()
    if not row:
        raise HTTPException(404)
    tutorial, category = row
    plan_id = await get_current_plan_id(db, user.id)
    if not has_plan_access(plan_id, _normalize_plan_id(tutorial.required_plan)):
        return RedirectResponse("/pricing?upgrade=1", status_code=302)
    tutorial_video_url = media_view_url(tutorial.video_url)
    tutorial_file_url = media_view_url(tutorial.file_url)
    return _render(
        request,
        "tutorial_detail.html",
        {
            "user": user,
            "tutorial": tutorial,
            "category": category,
            "slug": slug,
            "current_plan": plan_id,
            "tutorial_video_url": tutorial_video_url,
            "tutorial_file_url": tutorial_file_url,
            "tutorial_video_is_embed": _is_embed_video_url(tutorial_video_url),
        },
    )


@app.post("/admin/tutorial-categories")
async def admin_create_tutorial_category(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    csrf_token: str = Form(""),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user or not user.is_admin:
        raise HTTPException(403)
    _verify_csrf_or_403(request, csrf_token)

    title_clean = title.strip()
    if not title_clean:
        return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=t(get_lang(request), "admin_tutorial_category_title_required")))

    slug_base = _slugify(title_clean)
    if not slug_base:
        return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=t(get_lang(request), "admin_tutorial_category_slug_invalid")))

    slug = slug_base
    idx = 2
    while True:
        q = select(models.TutorialCategory).where(models.TutorialCategory.slug == slug)
        res = await db.execute(q)
        if not res.scalars().first():
            break
        slug = f"{slug_base}-{idx}"
        idx += 1

    category = models.TutorialCategory(slug=slug, title=title_clean, description=description.strip(), is_active=True)
    db.add(category)
    await db.commit()
    return _render(request, "admin.html", await _admin_context(db, user, saved=True, error=None))


@app.post("/admin/tutorials")
async def admin_create_tutorial(
    request: Request,
    category_id: str = Form(""),
    title: str = Form(""),
    summary: str = Form(""),
    body: str = Form(""),
    required_plan: str = Form("free"),
    video_url: str = Form(""),
    csrf_token: str = Form(""),
    tutorial_file: UploadFile | None = File(default=None),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user or not user.is_admin:
        raise HTTPException(403)
    _verify_csrf_or_403(request, csrf_token)

    lang = get_lang(request)
    title_clean = title.strip()
    if not title_clean:
        return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=t(lang, "admin_tutorial_title_required")))
    category = await db.get(models.TutorialCategory, category_id)
    if not category:
        return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=t(lang, "admin_tutorial_category_required")))

    slug_base = _slugify(title_clean)
    if not slug_base:
        return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=t(lang, "admin_tutorial_slug_invalid")))
    slug = slug_base
    idx = 2
    while True:
        q = select(models.Tutorial).where(models.Tutorial.slug == slug)
        res = await db.execute(q)
        if not res.scalars().first():
            break
        slug = f"{slug_base}-{idx}"
        idx += 1

    file_url = ""
    try:
        if tutorial_file and tutorial_file.filename:
            file_url = await _save_upload(
                tutorial_file,
                allowed_prefix="application/",
                allowed_exts={".pdf", ".txt", ".md", ".mp4", ".webm", ".mov"},
                max_bytes=100 * 1024 * 1024,
                name_prefix="tutorial_file",
                invalid_type_key="admin_upload_error_tutorial_file_type",
                too_large_key="admin_upload_error_tutorial_file_size",
            )
    except ValueError as e:
        return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=t(lang, str(e))))

    tutorial = models.Tutorial(
        category_id=category.id,
        slug=slug,
        title=title_clean,
        summary=summary.strip(),
        body=body.strip(),
        required_plan=_normalize_plan_id(required_plan),
        video_url=_normalize_video_url(video_url),
        file_url=file_url,
        is_active=True,
    )
    db.add(tutorial)
    await db.commit()
    return _render(request, "admin.html", await _admin_context(db, user, saved=True, error=None))


@app.post("/admin/founder-content")
async def admin_update_founder_content(
    request: Request,
    founder_name: str = Form(""),
    founder_intro: str = Form(""),
    founder_photo_url: str = Form(""),
    founder_video_url: str = Form(""),
    csrf_token: str = Form(""),
    founder_photo_file: UploadFile | None = File(default=None),
    founder_video_file: UploadFile | None = File(default=None),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user or not user.is_admin:
        raise HTTPException(403)
    _verify_csrf_or_403(request, csrf_token)

    site_content = await _get_site_content(db)
    site_content.founder_name = founder_name.strip()
    site_content.founder_intro = founder_intro.strip()
    site_content.founder_photo_url = founder_photo_url.strip()
    site_content.founder_video_url = _normalize_video_url(founder_video_url)

    lang = get_lang(request)
    try:
        if founder_photo_file and founder_photo_file.filename:
            site_content.founder_photo_url = await _save_upload(
                founder_photo_file,
                allowed_prefix="image/",
                allowed_exts={".jpg", ".jpeg", ".png", ".webp"},
                max_bytes=10 * 1024 * 1024,
                name_prefix="founder_photo",
                invalid_type_key="admin_upload_error_photo_type",
                too_large_key="admin_upload_error_photo_size",
            )
        if founder_video_file and founder_video_file.filename:
            site_content.founder_video_url = await _save_upload(
                founder_video_file,
                allowed_prefix="video/",
                allowed_exts={".mp4", ".webm", ".mov"},
                max_bytes=100 * 1024 * 1024,
                name_prefix="founder_video",
                invalid_type_key="admin_upload_error_video_type",
                too_large_key="admin_upload_error_video_size",
            )
    except ValueError as e:
        return _render(request, "admin.html", await _admin_context(db, user, saved=False, error=t(lang, str(e))))

    await db.commit()
    await db.refresh(site_content)

    return _render(request, "admin.html", await _admin_context(db, user, saved=True, error=None))
