"""Send iMessage via AppleScript and Messages.app."""
import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def _build_applescript(message: str, phone: str) -> str:
    """Build the AppleScript command to send an iMessage."""
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    return f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{phone}" of targetService
        send "{escaped}" to targetBuddy
    end tell
    '''


def _chunk_message(message: str, max_len: int = 3000) -> list[str]:
    """Split a message into chunks, preferring newline boundaries."""
    if len(message) <= max_len:
        return [message]

    chunks = []
    lines = message.split("\n")
    current = ""

    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len:
            if current:
                chunks.append(current)
            while len(line) > max_len:
                chunks.append(line[:max_len])
                line = line[max_len:]
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def send_imessage(
    message: str,
    phone: str,
    max_chunk: int = 3000,
    retry: int = 2,
    delay: float = 1.0,
) -> bool:
    """Send a message via iMessage. Returns True if all chunks sent successfully."""
    chunks = _chunk_message(message, max_len=max_chunk)
    logger.info("Sending iMessage to %s (%d chunks)", phone, len(chunks))

    for i, chunk in enumerate(chunks):
        success = False
        for attempt in range(retry + 1):
            script = _build_applescript(chunk, phone)
            try:
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                logger.warning("Chunk %d/%d attempt %d timed out", i + 1, len(chunks), attempt + 1)
                if attempt < retry:
                    time.sleep(delay)
                continue

            if result.returncode == 0:
                success = True
                logger.info("Chunk %d/%d sent successfully", i + 1, len(chunks))
                break
            else:
                logger.warning(
                    "Chunk %d/%d attempt %d failed: %s",
                    i + 1, len(chunks), attempt + 1, result.stderr.strip(),
                )
                if attempt < retry:
                    time.sleep(delay)

        if not success:
            logger.error("Failed to send chunk %d/%d after %d attempts", i + 1, len(chunks), retry + 1)
            return False

        if i < len(chunks) - 1:
            time.sleep(delay)

    return True
