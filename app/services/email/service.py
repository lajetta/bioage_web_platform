from __future__ import annotations

import smtplib
import ssl
import time
from email.message import EmailMessage

from app.core.settings import settings


def send_email(to_email: str, subject: str, body: str, attachment: tuple[str, bytes, str] | None = None) -> None:
    """Send an email via SMTP.

    attachment: (filename, content_bytes, mime_type)
    """

    if not settings.smtp_host or not settings.email_from:
        # Dev fallback: print to logs
        print("[EMAIL DEV MODE] To:", to_email)
        print("[EMAIL DEV MODE] Subject:", subject)
        print(body)
        return

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment:
        filename, content, mime = attachment
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    last_err: Exception | None = None
    for attempt in range(1, max(settings.email_send_retries, 1) + 1):
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as server:
                if settings.smtp_use_tls:
                    server.starttls(context=ssl.create_default_context())
                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)
            return
        except Exception as e:
            last_err = e
            if attempt < settings.email_send_retries:
                time.sleep(min(2 * attempt, 5))
    if last_err:
        raise last_err
