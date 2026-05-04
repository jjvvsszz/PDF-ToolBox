import os
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import pages, merge, split, compress, extract, convert, detailed_merge

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI(title="PDF Toolbox", version="2.0.0")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(pages.router)
app.include_router(merge.router, prefix="/api")
app.include_router(split.router, prefix="/api")
app.include_router(compress.router, prefix="/api")
app.include_router(extract.router, prefix="/api")
app.include_router(convert.router, prefix="/api")
app.include_router(detailed_merge.router, prefix="/api")
