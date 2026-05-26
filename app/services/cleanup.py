import asyncio
import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger("pdf_toolbox.cleanup")


async def cleanup_loop(uploads_dir: Path, delay_minutes: int, interval_seconds: int):
    while True:
        await asyncio.sleep(interval_seconds)
        _cleanup_expired(uploads_dir, delay_minutes)


def _cleanup_expired(uploads_dir: Path, delay_minutes: int):
    if not uploads_dir.exists():
        return
    now = time.time()
    cutoff = delay_minutes * 60
    for entry in list(uploads_dir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            age_seconds = now - entry.stat().st_mtime
            if age_seconds > cutoff:
                shutil.rmtree(str(entry), ignore_errors=True)
                logger.debug("Cleaned up session dir: %s", entry.name)
        except FileNotFoundError:
            pass
        except OSError:
            pass


def cleanup_orphans(uploads_dir: Path):
    if not uploads_dir.exists():
        return
    for entry in list(uploads_dir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            shutil.rmtree(str(entry), ignore_errors=True)
            logger.debug("Cleaned up orphan session dir: %s", entry.name)
        except Exception:
            pass
