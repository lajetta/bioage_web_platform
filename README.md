# BioAge Reset Protocol — Web Platform (MVP)

This repository is an **end‑to‑end web platform** that replicates and extends the core Telegram bot concept into a public website / landing page:

- Landing page + pricing (EN/UK/RU)
- Email **passwordless login** (one-time code)
- 7–15 question **assessment wizard**
- Payments **(mock mode by default)** or **Stripe Checkout subscription**
- AI generation (OpenAI, optional) → **structured JSON**
- **Clean medical PDF** generation (ReportLab)
- Background worker (Redis + RQ) to generate and email the PDF
- Basic admin page (review queue scaffold)

> If `OPENAI_API_KEY` is not set, the app generates a deterministic **mock report** so the whole pipeline still works.

---

## 1) Quick start (local, Docker)

### Requirements
- Docker + Docker Compose

### Steps
```bash
# 1) Configure env
cp .env.example .env
# edit .env (at minimum: SECRET_KEY)

# 2) Start services
docker compose up --build

# 3) Run DB migrations (in a separate terminal)
docker compose exec web alembic upgrade head

# 4) Open the app
# http://localhost:8000
```

### Create an admin user (optional)
Add to `.env`:
```env
ADMIN_EMAILS=you@example.com
```
Then log in with that email once, restart the web container:
```bash
docker compose restart web
```
Now `/admin` will work for that user.

---

## 2) Quick start (local, without Docker)

### Requirements
- Python 3.11+
- Postgres + Redis running locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env from template
cp .env.example .env

# Point to your local services in .env
# DATABASE_URL=postgresql+asyncpg://...
# REDIS_URL=redis://...

alembic upgrade head
uvicorn app.main:app --reload

# In another terminal
python worker.py
```

---

## 3) Payments

### Mock mode (default)
Set:
```env
PAYMENTS_MODE=mock
```
After finishing the assessment, the payment step simulates success and queues report generation.

### Stripe (subscription via Checkout)
Set:
```env
PAYMENTS_MODE=stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_PRICE_ID_MONTHLY=price_...
BASE_URL=https://your-domain
```
Notes:
- This MVP creates a **Stripe Checkout subscription session**.
- For production you should add a webhook endpoint to confirm payment events and update membership states.

---

## 4) Email

If SMTP is not configured:
- login codes are shown as a **dev hint on the verify page**
- report emails print to logs

To enable SMTP (SendGrid-compatible):
```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=<your-sendgrid-api-key>
EMAIL_FROM=reports@yourdomain.tld
```

---

## 5) Production deployment patterns

This project is container-friendly, so you can deploy anywhere that runs Docker.

### Option A: Single VM (simple)
- Provision a VM (Ubuntu)
- Install Docker
- Copy repo + `.env`
- `docker compose up -d --build`
- Put Nginx/Caddy in front for TLS (recommended)

### Option B: PaaS (Render / Fly / Railway / etc.)
You typically create:
- **Web service**: runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Worker service**: runs `python worker.py`
- **Managed Postgres**
- **Managed Redis**
- Set env vars from `.env`

**Important:** the PDF files are written to `/data/reports` inside the container. In production, you should store PDFs in object storage (S3/R2/etc.) and only keep a signed download URL in the DB.

### Security + storage checklist (production)

Set these env vars:

```env
ENVIRONMENT=prod
ENFORCE_HTTPS=true
ALLOWED_HOSTS=your-domain.railway.app,your-custom-domain.com
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax
SESSION_MAX_AGE_SECONDS=2592000
```

For durable files (reports/uploads), use S3-compatible storage:

```env
STORAGE_BACKEND=s3
S3_BUCKET=...
S3_REGION=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_ENDPOINT_URL=...          # optional for non-AWS providers
S3_PUBLIC_BASE_URL=...       # optional (public media URL base)
S3_PRESIGN_EXPIRY_SECONDS=3600
S3_REPORTS_PREFIX=reports
S3_UPLOADS_PREFIX=uploads
```

Email reliability:

```env
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
EMAIL_FROM=...
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=20
EMAIL_SEND_RETRIES=3
```

---

## 6) Folder structure

- `app/main.py` — FastAPI app + HTML routes
- `app/core/*` — settings, i18n, security, questions
- `app/db/*` — SQLAlchemy models + async session
- `app/services/*` — email, payments, OpenAI, PDF generation
- `app/services/report/tasks.py` — RQ worker task
- `worker.py` — RQ worker entrypoint
- `migrations/` — Alembic migrations
- `docker-compose.yml` — web + worker + postgres + redis

---

## 7) Next upgrades (recommended)

- Add a **Stripe webhook** endpoint (`/webhooks/stripe`) to mark payments paid and manage subscription lifecycle.
- Add a real **monthly update submission** UI + admin approve/reject actions + new PDF generation.
- Add object storage (S3/R2) for report PDFs.
- Add proper user session expiration + logout.
- Add tests + CI (pytest) and linting (ruff).
