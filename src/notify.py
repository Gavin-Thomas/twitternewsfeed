"""Push notifications via ntfy.sh — free, no account, works from anywhere."""
import logging
import requests

logger = logging.getLogger(__name__)

NTFY_URL = "https://ntfy.sh"


def send_ntfy(message: str, topic: str, title: str = "AI Digest") -> bool:
    """Send a push notification via ntfy.sh.

    Args:
        message: The notification body text.
        topic: The ntfy topic (acts as a private channel).
        title: Notification title.

    Returns True if sent successfully.
    """
    if not topic:
        logger.error("No ntfy topic configured. Set ULTRAPLAN_NTFY_TOPIC in .env")
        return False

    try:
        # ASCII-safe title for HTTP header; full unicode in body
        safe_title = title.encode("ascii", errors="replace").decode("ascii")
        resp = requests.post(
            f"{NTFY_URL}/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": safe_title,
                "Priority": "default",
                "Tags": "robot",
                "Content-Type": "text/plain; charset=utf-8",
            },
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("ntfy notification sent to topic '%s'", topic)
        return True
    except Exception as e:
        logger.error("ntfy send failed: %s", e)
        return False


def send_ntfy_long(message: str, topic: str, title: str = "AI Digest", chunk_size: int = 4000) -> bool:
    """Send a long message via ntfy, splitting into multiple notifications if needed."""
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
