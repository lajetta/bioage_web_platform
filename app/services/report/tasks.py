from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.core.settings import settings
from app.db import models
from app.services.openai_service import generate_report_json
from app.services.report.pdf import build_pdf
from app.services.email.service import send_email


REPORT_DIR = os.getenv("REPORT_DIR", "/data/reports")


def generate_and_send_report(report_id: str) -> None:
    """RQ worker task: generate report JSON + PDF and email it."""
    os.makedirs(REPORT_DIR, exist_ok=True)

    async def _run() -> None:
        async with SessionLocal() as session:
            report = await session.get(models.Report, report_id)
            if not report:
                return
            user = await session.get(models.User, report.user_id)
            if not user:
                return
            assessment_answers = {}
            if report.assessment_id:
                assessment = await session.get(models.Assessment, report.assessment_id)
                if assessment:
                    assessment_answers = assessment.answers or {}

            report.status = "generating"
            await session.commit()

            content = generate_report_json(assessment_answers, user.language)
            pdf_bytes = build_pdf(content, user.language)

            filename = f"bioage_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{report.id}.pdf"
            path = os.path.join(REPORT_DIR, filename)
            with open(path, "wb") as f:
                f.write(pdf_bytes)

            report.content_json = content
            report.file_path = path
            report.status = "sent"
            await session.commit()

            download_url = f"{settings.base_url}/reports/{report.id}/download"

            send_email(
                to_email=user.email,
                subject="Your BioAge Reset Report",
                body=(
                    "Attached is your BioAge Reset Protocol report PDF.\n\n"
                    f"You can also download it from your dashboard:\n{download_url}"
                ),
                attachment=(filename, pdf_bytes, "application/pdf"),
            )

    import asyncio

    asyncio.run(_run())
