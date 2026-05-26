import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    UPLOADS_DIR,
    STATIC_DIR,
    MAX_UPLOAD_SIZE_MB,
    MAX_FILES,
    CLEANUP_DELAY_MINUTES,
    CLEANUP_INTERVAL_SECONDS,
    CORS_ORIGINS,
    LOG_LEVEL,
)
from app.services.cleanup import cleanup_loop, cleanup_orphans
from app.routes import pages, merge, split, compress, extract, convert, detailed_merge, blank_remover

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pdf_toolbox")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_orphans(UPLOADS_DIR)
    logger.info("Cleaned up orphan session directories on startup")
    task = asyncio.create_task(
        cleanup_loop(UPLOADS_DIR, CLEANUP_DELAY_MINUTES, CLEANUP_INTERVAL_SECONDS)
    )
    logger.info(
        "Cleanup loop started (delay=%dmin, interval=%ds)",
        CLEANUP_DELAY_MINUTES,
        CLEANUP_INTERVAL_SECONDS,
    )
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Cleanup loop stopped")


app = FastAPI(title="PDF Toolbox", version="2.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_cors_origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()] if CORS_ORIGINS else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def upload_size_limit_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            cl = int(content_length)
            max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
            if cl > max_bytes:
                return JSONResponse(
                    {"error": f"Arquivo excede o limite de {MAX_UPLOAD_SIZE_MB} MB"},
                    status_code=413,
                )
        except ValueError:
            pass
    return await call_next(request)


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        if origin:
            request_host = request.headers.get("host", "")
            if origin not in (f"http://{request_host}", f"https://{request_host}"):
                origin_domain = origin.split("://")[-1] if "://" in origin else origin
                host_domain = request_host.split(":")[0]
                if origin_domain != host_domain:
                    return JSONResponse({"error": "Origem da requisicao invalida"}, status_code=403)
        elif referer:
            request_host = request.headers.get("host", "")
            if request_host not in referer:
                return JSONResponse({"error": "Origem da requisicao invalida"}, status_code=403)
    return await call_next(request)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"error": "Erro interno do servidor"}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


app.include_router(pages.router)
app.include_router(merge.router, prefix="/api")
app.include_router(split.router, prefix="/api")
app.include_router(compress.router, prefix="/api")
app.include_router(extract.router, prefix="/api")
app.include_router(convert.router, prefix="/api")
app.include_router(detailed_merge.router, prefix="/api")
app.include_router(blank_remover.router, prefix="/api")
