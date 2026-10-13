import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import UploadFile

from app.config import UPLOADS_DIR

SESSION_ID_RE = re.compile(r"[0-9a-f]{32}")
THUMB_NAME_RE = re.compile(r"[0-9a-f]{32}\.png")
BUSY_MARKER = ".busy"
INPUT_DIR = "in"

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_UNSAFE_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_MAX_NAME_LEN = 120


def safe_filename(name: str | None, default: str = "arquivo") -> str:
    """Reduz o nome enviado pelo cliente a um nome de arquivo simples, sem diretorios."""
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = _UNSAFE_CHARS.sub("_", name).strip(" .")
    if not name:
        name = default
    if name.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        name = f"_{name}"
    if len(name) > _MAX_NAME_LEN:
        stem, suffix = os.path.splitext(name)
        suffix = suffix[:20]
        name = stem[: _MAX_NAME_LEN - len(suffix)] + suffix
    return name


def is_valid_session_id(session_id: str | None) -> bool:
    return bool(session_id) and SESSION_ID_RE.fullmatch(session_id) is not None


def is_valid_thumb_name(name: str | None) -> bool:
    return bool(name) and THUMB_NAME_RE.fullmatch(name) is not None


def session_dir_for(session_id: str) -> Path | None:
    """Pasta de uma sessao existente, ou None se o id for invalido ou a pasta nao existir."""
    if not is_valid_session_id(session_id):
        return None
    path = UPLOADS_DIR / session_id
    return path if path.is_dir() else None


def new_session_dir() -> Path:
    path = UPLOADS_DIR / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


def remove_session_dir(path: Path):
    shutil.rmtree(str(path), ignore_errors=True)


def touch(path: Path):
    try:
        os.utime(path, None)
    except OSError:
        pass


def save_upload(upload: UploadFile, session_dir: Path) -> Path:
    """Grava o upload em uma subpasta propria, evitando colisao entre arquivos de mesmo nome."""
    target_dir = session_dir / INPUT_DIR / uuid.uuid4().hex[:12]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_filename(upload.filename)
    upload.file.seek(0)
    with open(target, "wb") as out:
        shutil.copyfileobj(upload.file, out, length=1024 * 1024)
    return target


@contextmanager
def busy(session_dir: Path):
    """Protege a pasta da limpeza automatica enquanto um processamento longo roda."""
    marker = session_dir / BUSY_MARKER
    marker.touch()
    try:
        yield
    finally:
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
        touch(session_dir)


@contextmanager
def file_lock(path: Path, timeout: float = 30.0, stale_after: float = 60.0):
    """Lock entre processos (varios workers do uvicorn) baseado em criacao exclusiva de arquivo."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > stale_after:
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timeout aguardando lock {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
