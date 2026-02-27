from __future__ import annotations

import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

from app.core.settings import settings

logger = logging.getLogger(__name__)


def _lang_text(lang: str, en: str, uk: str, ru: str) -> str:
    if lang == "uk":
        return uk
    if lang == "ru":
        return ru
    return en


def _from_header() -> str:
    if settings.email_from_name and settings.email_from:
        return f"{settings.email_from_name} <{settings.email_from}>"
    return settings.email_from or ""


def send_email(to_email: str, subject: str, body: str, attachment: tuple[str, bytes, str] | None = None) -> None:
    """Send an email via SMTP with retry logic.

    attachment: (filename, content_bytes, mime_type)
    Raises on final failure.
    """
    if not settings.smtp_host or not settings.email_from:
        logger.warning("[EMAIL DEV MODE] smtp_host/email_from not configured; skipping SMTP send to %s", to_email)
        logger.info("[EMAIL DEV MODE] Subject: %s", subject)
        logger.info("[EMAIL DEV MODE] Body: %s", body)
        return

    msg = EmailMessage()
    msg["From"] = _from_header()
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment:
        filename, content, mime = attachment
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    retries = max(int(settings.email_send_retries), 1)
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds, context=ssl.create_default_context()) as server:
                    if settings.smtp_username and settings.smtp_password:
                        server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as server:
                    if settings.smtp_use_tls:
                        server.starttls(context=ssl.create_default_context())
                    if settings.smtp_username and settings.smtp_password:
                        server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(msg)
            return
        except Exception as e:
            last_err = e
            logger.exception("SMTP send failed (attempt %s/%s) to %s", attempt, retries, to_email)
            if attempt < retries:
                time.sleep(min(2 * attempt, 5))
    if last_err:
        raise last_err


def safe_send_email(to_email: str, subject: str, body: str, attachment: tuple[str, bytes, str] | None = None) -> bool:
    try:
        send_email(to_email=to_email, subject=subject, body=body, attachment=attachment)
        return True
    except Exception:
        logger.exception("Email send failed permanently to %s", to_email)
        return False


def send_login_code_email(to_email: str, code: str, lang: str = "en") -> bool:
    subject = _lang_text(
        lang,
        "Your BioAge login code",
        "\u0412\u0430\u0448 \u043a\u043e\u0434 \u0432\u0445\u043e\u0434\u0443 BioAge",
        "\u0412\u0430\u0448 \u043a\u043e\u0434 \u0432\u0445\u043e\u0434\u0430 BioAge",
    )
    body = _lang_text(
        lang,
        f"Your login code is: {code}\n\nIt expires in 10 minutes.",
        f"\u0412\u0430\u0448 \u043a\u043e\u0434 \u0432\u0445\u043e\u0434\u0443: {code}\n\n\u0412\u0456\u043d \u0434\u0456\u0439\u0441\u043d\u0438\u0439 10 \u0445\u0432\u0438\u043b\u0438\u043d.",
        f"\u0412\u0430\u0448 \u043a\u043e\u0434 \u0432\u0445\u043e\u0434\u0430: {code}\n\n\u041e\u043d \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 10 \u043c\u0438\u043d\u0443\u0442.",
    )
    return safe_send_email(to_email=to_email, subject=subject, body=body)


def send_report_email(
    to_email: str,
    download_url: str,
    attachment: tuple[str, bytes, str] | None = None,
    lang: str = "en",
) -> bool:
    subject = _lang_text(
        lang,
        "Your BioAge Reset Report",
        "\u0412\u0430\u0448 \u0437\u0432\u0456\u0442 BioAge Reset",
        "\u0412\u0430\u0448 \u043e\u0442\u0447\u0435\u0442 BioAge Reset",
    )
    body = _lang_text(
        lang,
        "Attached is your BioAge Reset Protocol report PDF.\n\n"
        f"You can also download it from your dashboard:\n{download_url}",
        "\u0414\u043e \u043b\u0438\u0441\u0442\u0430 \u0434\u043e\u0434\u0430\u043d\u043e PDF-\u0437\u0432\u0456\u0442 BioAge Reset Protocol.\n\n"
        f"\u0422\u0430\u043a\u043e\u0436 \u0432\u0438 \u043c\u043e\u0436\u0435\u0442\u0435 \u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0438\u0442\u0438 \u0439\u043e\u0433\u043e \u0432 \u043a\u0430\u0431\u0456\u043d\u0435\u0442\u0456:\n{download_url}",
        "\u041a \u043f\u0438\u0441\u044c\u043c\u0443 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d PDF-\u043e\u0442\u0447\u0435\u0442 BioAge Reset Protocol.\n\n"
        f"\u0422\u0430\u043a\u0436\u0435 \u0432\u044b \u043c\u043e\u0436\u0435\u0442\u0435 \u0441\u043a\u0430\u0447\u0430\u0442\u044c \u0435\u0433\u043e \u0432 \u043b\u0438\u0447\u043d\u043e\u043c \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435:\n{download_url}",
    )
    return safe_send_email(to_email=to_email, subject=subject, body=body, attachment=attachment)
