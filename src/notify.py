"""Notification delivery — email (Gmail SMTP) and ntfy.sh."""
import logging
import smtplib
from email.mime.text import MIMEText
import os

import requests

logger = logging.getLogger(__name__)

NTFY_URL = "https://ntfy.sh"


# --- Email via Gmail SMTP ---

def send_email(message: str, to_email: str, subject: str = "AI Digest") -> bool:
    """Send an email via Gmail SMTP. Requires ULTRAPLAN_GMAIL_APP_PASSWORD in .env."""
    from_email = os.environ.get("ULTRAPLAN_GMAIL_USER", "")
    app_password = os.environ.get("ULTRAPLAN_GMAIL_APP_PASSWORD", "")

    if not from_email or not app_password:
        logger.error("Gmail not configured. Set ULTRAPLAN_GMAIL_USER and ULTRAPLAN_GMAIL_APP_PASSWORD in .env")
        return False

    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(from_email, app_password)
            server.send_message(msg)

        logger.info("Email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


# --- ntfy.sh (kept as optional fallback) ---

def send_ntfy(message: str, topic: str, title: str = "AI Digest") -> bool:
    """Send a push notification via ntfy.sh."""
    if not topic:
        return False

    try:
        safe_title = title.encode("ascii", errors="replace").decode("ascii")
        resp = requests.post(
            f"{NTFY_URL}/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": safe_title,
                "Priority": "default",
                "Tags": "robot",
                "Content-Type": "text/plain; charset=utf-8",
                "Markdown": "yes",
            },
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("ntfy sent to topic '%s'", topic)
        return True
    except Exception as e:
        logger.error("ntfy send failed: %s", e)
        return False


def send_ntfy_long(message: str, topic: str, title: str = "AI Digest", chunk_size: int = 4000) -> bool:
    """Send a long message via ntfy, splitting if needed."""
    if len(message) <= chunk_size:
        return send_ntfy(message, topic, title)

    lines = message.split("\n")
    chunks = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > chunk_size:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)

    all_ok = True
    for i, chunk in enumerate(chunks):
        chunk_title = f"{title} ({i+1}/{len(chunks)})" if len(chunks) > 1 else title
        if not send_ntfy(chunk, topic, chunk_title):
            all_ok = False
    return all_ok
