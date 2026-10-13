import logging
from pathlib import Path
from typing import Callable

from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.config import MAX_FILES
from app.services.errors import UserError
from app.services.storage import busy, new_session_dir, remove_session_dir

GENERIC_ERROR = "Erro ao processar o arquivo"


def error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def too_many_files(files: list) -> JSONResponse | None:
    if not files:
        return error("Nenhum arquivo enviado")
    if len(files) > MAX_FILES:
        return error(f"Maximo de {MAX_FILES} arquivos permitidos")
    return None


def download(path: Path, session_dir: Path, media_type: str | None = None,
             filename: str | None = None) -> FileResponse:
    """Envia o arquivo e apaga a pasta da sessao assim que o download termina."""
    return FileResponse(
        path,
        filename=filename or path.name,
        media_type=media_type,
        background=BackgroundTask(remove_session_dir, session_dir),
    )


def run_job(logger: logging.Logger, log_message: str, job: Callable[[Path], object],
            keep_dir: bool = False):
    """Cria a pasta da sessao, executa o job e converte erros em respostas JSON.

    keep_dir=True mantem a pasta apos sucesso (previews que servem miniaturas);
    ela sera removida pela limpeza automatica.
    """
    session_dir = new_session_dir()
    try:
        with busy(session_dir):
            result = job(session_dir)
    except UserError as e:
        remove_session_dir(session_dir)
        return error(e.message, e.status_code)
    except Exception:
        logger.exception(log_message)
        remove_session_dir(session_dir)
        return error(GENERIC_ERROR, 500)
    if not keep_dir and not isinstance(result, FileResponse):
        remove_session_dir(session_dir)
    return result
