from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.core.i18n import get_lang, t
from app.core.questions import QUESTIONS, validate_answer
from app.core.security import expires_in, generate_code, hash_code, sign_session, unsign_session
from app.core.settings import settings
from app.db.session import SessionLocal
from app.db import models
from app.services.email.service import send_email
from app.services.payments.service import create_checkout
from app.services.subscriptions.service import (
    PLAN_FEATURES,
    can_generate_report,
    get_current_plan_id,
    get_latest_subscription,
    has_plan_access,
    upsert_subscription,
)

import redis
from rq import Queue


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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


async def get_current_user(session_token: str | None = Cookie(default=None), db=Depends(get_db)) -> models.User | None:
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
    return templates.TemplateResponse(name, base)


def _localize_validation_error(lang: str, error: str) -> str:
    mapping = {
        "This field is required": "error_required",
        "Please enter a number": "error_number",
        "Invalid choice": "error_invalid_choice",
    }
    return t(lang, mapping.get(error, error))


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

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{name_prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(6).hex()}{ext or ''}"
    path = os.path.join(UPLOADS_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    return f"/static/uploads/{filename}"


def _normalize_plan_id(value: str | None) -> str:
    return value if value in {"free", "pro", "premium"} else "free"


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
async def set_lang(code: str, request: Request):
    if code not in ("en", "uk", "ru"):
        raise HTTPException(400, "Unsupported language")
    resp = RedirectResponse(url=request.headers.get("referer") or "/", status_code=302)
    resp.set_cookie("lang", code, max_age=60 * 60 * 24 * 365)
    return resp


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    site_content = await _get_site_content(db)
    return _render(
        request,
        "home.html",
        {"user": user, "site_content": site_content, "founder_video_is_embed": _is_embed_video_url(site_content.founder_video_url)},
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
    return _render(request, "login.html", {"user": None, "error": None})


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session_token")
    return resp


@app.post("/login")
async def login_send_code(request: Request, email: str = Form(...), db=Depends(get_db)):
    from email_validator import validate_email, EmailNotValidError

    try:
        email_norm = validate_email(email, check_deliverability=False).email
    except EmailNotValidError:
        return _render(request, "login.html", {"user": None, "error": t(get_lang(request), "error_invalid_email")})

    code = generate_code()
    code_h = hash_code(code)

    # store code
    rec = models.MagicLoginCode(email=email_norm, code_hash=code_h, expires_at=expires_in(10), used=False)
    db.add(rec)
    await db.commit()

    send_email(
        to_email=email_norm,
        subject="Your BioAge login code",
        body=f"Your login code is: {code}\n\nIt expires in 10 minutes.",
    )

    # In dev, show a hint if SMTP is not configured
    hint = None
    if not settings.smtp_host:
        hint = code

    resp = _render(request, "verify.html", {"email": email_norm, "hint": hint, "error": None})
    return resp


@app.post("/verify")
async def verify_code(request: Request, email: str = Form(...), code: str = Form(...), db=Depends(get_db)):
    email = email.strip().lower()
    code_h = hash_code(code.strip())

    q = select(models.MagicLoginCode).where(
        models.MagicLoginCode.email == email,
        models.MagicLoginCode.used == False,  # noqa: E712
        models.MagicLoginCode.expires_at > datetime.now(tz=timezone.utc),
    ).order_by(models.MagicLoginCode.created_at.desc())
    res = await db.execute(q)
    rec = res.scalars().first()

    if not rec or rec.code_hash != code_h:
        return _render(request, "verify.html", {"email": email, "hint": None, "error": t(get_lang(request), "error_wrong_code")})

    rec.used = True

    # upsert user
    uq = select(models.User).where(models.User.email == email)
    ures = await db.execute(uq)
    user = ures.scalars().first()
    if not user:
        user = models.User(email=email, language=get_lang(request))
        db.add(user)
        await db.flush()

    await db.commit()

    token = sign_session(user.id)
    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie("session_token", token, httponly=True, max_age=60 * 60 * 24 * 30)
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
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    assessment = await db.get(models.Assessment, assessment_id)
    if not assessment or assessment.user_id != user.id:
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
async def start_report_generation(assessment_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    assessment = await db.get(models.Assessment, assessment_id)
    if not assessment or assessment.user_id != user.id or assessment.status != "completed":
        raise HTTPException(400)

    allowed, _plan_id = await can_generate_report(db, user.id)
    if not allowed:
        return RedirectResponse("/pricing?upgrade=1", status_code=302)

    report = models.Report(user_id=user.id, assessment_id=assessment.id, status="queued")
    db.add(report)
    await db.flush()

    conn = redis.from_url(settings.redis_url)
    q_ = Queue(connection=conn)
    q_.enqueue("app.services.report.tasks.generate_and_send_report", report.id)

    await db.commit()
    return RedirectResponse("/dashboard?report=queued", status_code=302)


@app.post("/billing/checkout/{plan_id}")
async def billing_checkout(plan_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
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
        raise HTTPException(404, "Report file is not ready")
    if not os.path.isfile(report.file_path):
        raise HTTPException(404, "Report file not found on server")

    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=os.path.basename(report.file_path),
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
            items.append({"tutorial": tutorial, "category": category})
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
    return _render(
        request,
        "tutorial_detail.html",
        {"user": user, "tutorial": tutorial, "category": category, "slug": slug, "current_plan": plan_id, "tutorial_video_is_embed": _is_embed_video_url(tutorial.video_url)},
    )


@app.post("/admin/tutorial-categories")
async def admin_create_tutorial_category(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user or not user.is_admin:
        raise HTTPException(403)

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
    tutorial_file: UploadFile | None = File(default=None),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user or not user.is_admin:
        raise HTTPException(403)

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
    founder_photo_file: UploadFile | None = File(default=None),
    founder_video_file: UploadFile | None = File(default=None),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not user or not user.is_admin:
        raise HTTPException(403)

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
