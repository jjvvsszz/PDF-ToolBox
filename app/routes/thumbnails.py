from fastapi.responses import FileResponse

from app.routes._common import error
from app.services.storage import is_valid_thumb_name, session_dir_for


def thumbnail_response(session_id: str, thumb_name: str):
    session_dir = session_dir_for(session_id)
    if session_dir is None or not is_valid_thumb_name(thumb_name):
        return error("Thumbnail nao encontrada", 404)
    thumb_path = session_dir / "thumbs" / thumb_name
    if not thumb_path.is_file():
        return error("Thumbnail nao encontrada", 404)
    return FileResponse(str(thumb_path), media_type="image/png")
