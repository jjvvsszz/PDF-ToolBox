import asyncio
import logging
import shutil
import time
from pathlib import Path

from app.services.storage import BUSY_MARKER, is_valid_session_id

logger = logging.getLogger("pdf_toolbox.cleanup")

INTERACTIVE_SESSION_FILE = "session.json"


async def cleanup_loop(uploads_dir: Path, delay_minutes: int, interval_seconds: int,
                       session_idle_minutes: int, busy_timeout_minutes: int):
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await asyncio.to_thread(
                cleanup_expired, uploads_dir, delay_minutes, session_idle_minutes, busy_timeout_minutes
            )
        except Exception:
            logger.exception("Falha na limpeza automatica")


def _is_expired(entry: Path, now: float, delay_s: float, idle_s: float, busy_s: float) -> bool:
    busy = entry / BUSY_MARKER
    if busy.exists():
        return now - busy.stat().st_mtime > busy_s
    limit = idle_s if (entry / INTERACTIVE_SESSION_FILE).exists() else delay_s
    return now - entry.stat().st_mtime > limit


def cleanup_expired(uploads_dir: Path, delay_minutes: int, session_idle_minutes: int,
                    busy_timeout_minutes: int) -> int:
    """Remove pastas de sessao inativas. Seguro com varios workers: so apaga o que expirou."""
    if not uploads_dir.exists():
        return 0
    now = time.time()
    removed = 0
    for entry in list(uploads_dir.iterdir()):
        if not entry.is_dir() or not is_valid_session_id(entry.name):
            continue
        try:
            if _is_expired(entry, now, delay_minutes * 60, session_idle_minutes * 60,
                           busy_timeout_minutes * 60):
                shutil.rmtree(str(entry), ignore_errors=True)
                removed += 1
                logger.debug("Cleaned up session dir: %s", entry.name)
        except OSError:
            pass
    return removed
