from __future__ import annotations

import smtplib
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

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
