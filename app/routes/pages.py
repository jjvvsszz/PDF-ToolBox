from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from starlette.templating import _TemplateResponse

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


def render(name: str, request: Request):
    template = env.get_template(name)
    return HTMLResponse(template.render(request=request))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return render("index.html", request)


@router.get("/merge", response_class=HTMLResponse)
async def merge_page(request: Request):
    return render("merge.html", request)


@router.get("/split", response_class=HTMLResponse)
async def split_page(request: Request):
    return render("split.html", request)


@router.get("/compress", response_class=HTMLResponse)
async def compress_page(request: Request):
    return render("compress.html", request)


@router.get("/extract", response_class=HTMLResponse)
async def extract_page(request: Request):
    return render("extract.html", request)


@router.get("/pdf-to-images", response_class=HTMLResponse)
async def pdf_to_images_page(request: Request):
    return render("pdf-to-images.html", request)


@router.get("/images-to-pdf", response_class=HTMLResponse)
async def images_to_pdf_page(request: Request):
    return render("images-to-pdf.html", request)


@router.get("/office-to-pdf", response_class=HTMLResponse)
async def office_to_pdf_page(request: Request):
    return render("office-to-pdf.html", request)


@router.get("/pdf-to-office", response_class=HTMLResponse)
async def pdf_to_office_page(request: Request):
    return render("pdf-to-office.html", request)


@router.get("/detailed-merge", response_class=HTMLResponse)
async def detailed_merge_page(request: Request):
    return render("detailed-merge.html", request)
