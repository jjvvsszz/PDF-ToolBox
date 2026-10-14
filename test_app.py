"""Validation tests for PDF Toolbox"""
import io
import os
import sys
import time
import zipfile

import fitz
import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from PIL import Image
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.config import BASE_DIR, UPLOADS_DIR
from app.main import app
from app.middleware import BodySizeLimitMiddleware
from app.services.cleanup import cleanup_expired
from app.services.converter import ConverterService
from app.services.storage import BUSY_MARKER, file_lock, safe_filename

client = TestClient(app)

A4 = (595, 842)


def make_pdf(pages=2, label="p", sizes=None):
    doc = fitz.open()
    for i in range(pages):
        w, h = sizes[i] if sizes else A4
        page = doc.new_page(width=w, height=h)
        page.insert_text((72, 72), f"{label}{i}", fontsize=24)
    data = doc.tobytes()
    doc.close()
    return io.BytesIO(data)


def make_blank_pdf(pages=2):
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=A4[0], height=A4[1])
    data = doc.tobytes()
    doc.close()
    return io.BytesIO(data)


def make_image(mode="RGB", size=(200, 200), fmt="PNG", exif_orientation=None):
    buf = io.BytesIO()
    color = {"RGB": "red", "RGBA": (255, 0, 0, 128), "LA": (100, 128), "L": 100, "P": 1}[mode]
    img = Image.new(mode, size, color=color)
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        kwargs["exif"] = exif
    img.save(buf, format=fmt, **kwargs)
    buf.seek(0)
    return buf


def page_texts(pdf_bytes):
    doc = fitz.open("pdf", pdf_bytes)
    texts = [p.get_text().strip() for p in doc]
    doc.close()
    return texts


def pdf_files(*items):
    return [("files", (name, data, "application/pdf")) for name, data in items]


# ---------------------------------------------------------------- funcionalidades

def test_page_routes():
    pages = ["/", "/merge", "/split", "/compress", "/extract",
             "/pdf-to-images", "/images-to-pdf", "/office-to-pdf",
             "/pdf-to-office", "/detailed-merge", "/remove-blanks"]
    for p in pages:
        r = client.get(p)
        assert r.status_code == 200, f"GET {p} returned {r.status_code}"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_merge():
    r = client.post("/api/merge", files=pdf_files(("a.pdf", make_pdf(2, "A")), ("b.pdf", make_pdf(1, "B"))))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert page_texts(r.content) == ["A0", "A1", "B0"]


def test_split():
    r = client.post("/api/split", files=[("file", ("test.pdf", make_pdf(3), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert sorted(zf.namelist()) == ["test_pag_1.pdf", "test_pag_2.pdf", "test_pag_3.pdf"]


def test_compress_light():
    r = client.post("/api/compress", data={"level": "light"},
                    files=[("file", ("test.pdf", make_pdf(2), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_compress_normal():
    r = client.post("/api/compress", data={"level": "normal"},
                    files=[("file", ("test.pdf", make_pdf(2), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_compress_extreme():
    r = client.post("/api/compress", data={"level": "extreme"},
                    files=[("file", ("test.pdf", make_pdf(2), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_compress_default():
    r = client.post("/api/compress", files=[("file", ("test.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "test_compressed" in r.headers["content-disposition"]


def test_extract():
    r = client.post("/api/extract", data={"pages": "1-2"},
                    files=[("file", ("test.pdf", make_pdf(3), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert page_texts(r.content) == ["p0", "p1"]


def test_extract_preview():
    r = client.post("/api/extract/preview", data={"pages": "1,3"},
                    files=[("file", ("test.pdf", make_pdf(3), "application/pdf"))])
    assert r.status_code == 200
    data = r.json()
    assert data["total_selected"] == 2
    assert data["pages"][0]["page_number"] == 1
    assert data["pages"][1]["page_number"] == 3
    p = data["pages"][0]
    thumb = client.get(f"/api/extract/thumbnail/{p['session_dir']}/{p['thumbnail']}")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/png"


def test_pdf_to_images():
    r = client.post("/api/pdf-to-images", data={"format": "png"},
                    files=[("file", ("test.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_images_to_pdf():
    r = client.post("/api/images-to-pdf", files=[("files", ("test.png", make_image(), "image/png"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_detailed_merge():
    r = client.post("/api/detailed-merge/create-session")
    assert r.status_code == 200
    sid = r.json()["session_id"]

    r = client.post("/api/detailed-merge/add-pdf", data={"session_id": sid},
                    files=pdf_files(("test.pdf", make_pdf(3))))
    assert r.json()["total_pages"] == 3

    r = client.post("/api/detailed-merge/reorder", data={"session_id": sid, "index": 0, "direction": "down"})
    assert r.json()["success"] is True
    assert "pages" in r.json()

    r = client.post("/api/detailed-merge/delete", data={"session_id": sid, "index": 1})
    assert r.json()["success"] is True
    assert len(r.json()["pages"]) == 2

    r = client.post("/api/detailed-merge/clear", data={"session_id": sid})
    assert r.json()["success"] is True
    assert len(r.json()["pages"]) == 0

    client.post("/api/detailed-merge/add-pdf", data={"session_id": sid}, files=pdf_files(("test.pdf", make_pdf(2))))
    r = client.post("/api/detailed-merge/save", data={"session_id": sid})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_detailed_merge_reorder_result():
    sid = client.post("/api/detailed-merge/create-session").json()["session_id"]
    client.post("/api/detailed-merge/add-pdf", data={"session_id": sid}, files=pdf_files(("x.pdf", make_pdf(3))))
    client.post("/api/detailed-merge/reorder", data={"session_id": sid, "index": 2, "direction": "up"})
    client.post("/api/detailed-merge/delete", data={"session_id": sid, "index": 0})
    r = client.post("/api/detailed-merge/save", data={"session_id": sid})
    assert page_texts(r.content) == ["p2", "p1"]


def test_pdf_to_office():
    r = client.post("/api/pdf-to-office", files=[("file", ("test.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 200


def test_office_to_pdf_route():
    r = client.post("/api/office-to-pdf", files=[
        ("file", ("test.docx", b"dummy",
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
    ])
    if ConverterService._find_soffice() is None:
        assert r.status_code == 503
        assert "LibreOffice" in r.json()["error"]
    else:
        # O LibreOffice abre conteudo invalido como texto puro, entao pode converter;
        # se recusar, o erro precisa ser o de conversao (422), nunca um 500 generico.
        assert r.status_code in (200, 422)
        if r.status_code == 422:
            assert r.json()["error"]


def make_docx(text):
    """DOCX minimo valido, sem depender de python-docx."""
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.document.main+xml"/></Types>'
        ),
        "_rels/.rels": (
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": (
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
        ),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in parts.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_office_to_pdf_real_conversion():
    if ConverterService._find_soffice() is None:
        pytest.skip("LibreOffice nao instalado")
    docx_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def convert(i):
        return client.post("/api/office-to-pdf", files=[
            ("file", (f"doc{i}.docx", make_docx(f"Documento {i}"), docx_type))
        ])

    # Conversoes simultaneas: cada uma usa um perfil proprio do LibreOffice
    with ThreadPoolExecutor(3) as ex:
        responses = list(ex.map(convert, range(3)))
    for i, r in enumerate(responses):
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert f"Documento {i}" in page_texts(r.content)[0]


def test_remove_blanks():
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=A4[0], height=A4[1])
        if i != 1:
            page.insert_text((72, 72), f"texto {i}", fontsize=36)
    pdf = io.BytesIO(doc.tobytes())

    r = client.post("/api/remove-blanks/preview", data={"threshold": "95"},
                    files=[("file", ("b.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200
    assert r.json()["blank_count"] == 1

    pdf.seek(0)
    r = client.post("/api/remove-blanks", data={"threshold": "95"},
                    files=[("file", ("b.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200
    assert page_texts(r.content) == ["texto 0", "texto 2"]


# ---------------------------------------------------------------- regressoes

def test_upload_path_traversal_is_contained():
    escaped = BASE_DIR / "PWNED_test.pdf"
    escaped.unlink(missing_ok=True)
    r = client.post("/api/compress", data={"level": "light"},
                    files=[("file", ("../../PWNED_test.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 200
    assert not escaped.exists()
    assert "PWNED_test_compressed.pdf" in r.headers["content-disposition"]


def test_safe_filename():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("..\\..\\win.ini") == "win.ini"
    assert safe_filename("C:\\Windows\\x.pdf") == "x.pdf"
    assert safe_filename("CON.pdf") == "_CON.pdf"
    assert safe_filename("") == "arquivo"
    assert safe_filename("..") == "arquivo"
    assert len(safe_filename("a" * 500 + ".pdf")) <= 120


def test_session_id_traversal_rejected():
    outside = BASE_DIR.parent / "probe_dir_test"
    r = client.post("/api/detailed-merge/add-pdf", data={"session_id": "../../probe_dir_test"},
                    files=pdf_files(("z.pdf", make_pdf(1))))
    assert r.status_code == 404
    assert not outside.exists()
    for path in ("/api/detailed-merge/thumbnail/../x.png",
                 "/api/detailed-merge/thumbnail/..%2F..%2Fapp/config.py",
                 f"/api/extract/thumbnail/{'0' * 32}/..",
                 "/api/remove-blanks/thumbnail/../main.py"):
        assert client.get(path).status_code == 404, path


def test_merge_duplicate_filenames():
    r = client.post("/api/merge", files=pdf_files(("a.pdf", make_pdf(1, "A")), ("a.pdf", make_pdf(2, "B"))))
    assert r.status_code == 200
    assert page_texts(r.content) == ["A0", "B0", "B1"]


def test_detailed_merge_duplicate_filenames():
    sid = client.post("/api/detailed-merge/create-session").json()["session_id"]
    client.post("/api/detailed-merge/add-pdf", data={"session_id": sid}, files=pdf_files(("a.pdf", make_pdf(1, "A"))))
    client.post("/api/detailed-merge/add-pdf", data={"session_id": sid}, files=pdf_files(("a.pdf", make_pdf(2, "B"))))
    r = client.post("/api/detailed-merge/save", data={"session_id": sid})
    assert page_texts(r.content) == ["A0", "B0", "B1"]


def test_detailed_merge_rejects_non_pdf():
    sid = client.post("/api/detailed-merge/create-session").json()["session_id"]
    r = client.post("/api/detailed-merge/add-pdf", data={"session_id": sid},
                    files=[("files", ("img.png", make_image(), "image/png")),
                           ("files", ("ok.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 200
    data = r.json()
    assert data["total_added"] == 1
    assert len(data["errors"]) == 1


def test_detailed_merge_expired_session():
    r = client.post("/api/detailed-merge/reorder",
                    data={"session_id": "f" * 32, "index": 0, "direction": "up"})
    assert r.status_code == 404
    assert r.headers.get("x-session-expired") == "1"


def test_detailed_merge_activity_keeps_session_alive():
    sid = client.post("/api/detailed-merge/create-session").json()["session_id"]
    client.post("/api/detailed-merge/add-pdf", data={"session_id": sid}, files=pdf_files(("a.pdf", make_pdf(2))))
    session_dir = UPLOADS_DIR / sid
    old = time.time() - 3600
    os.utime(session_dir, (old, old))
    client.post("/api/detailed-merge/reorder", data={"session_id": sid, "index": 0, "direction": "down"})
    assert time.time() - session_dir.stat().st_mtime < 60


def test_pdf_to_images_jpg():
    r = client.post("/api/pdf-to-images", data={"format": "jpg"},
                    files=[("file", ("t.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(r.content)).format == "JPEG"


def test_pdf_to_images_zip_and_invalid_format():
    r = client.post("/api/pdf-to-images", data={"format": "jpg"},
                    files=[("file", ("t.pdf", make_pdf(2), "application/pdf"))])
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert sorted(zf.namelist()) == ["t_pag_1.jpg", "t_pag_2.jpg"]

    r = client.post("/api/pdf-to-images", data={"format": "../../x"},
                    files=[("file", ("t.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 400


def _extreme_page_sizes(pdf):
    r = client.post("/api/compress", data={"level": "extreme"},
                    files=[("file", ("t.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200
    doc = fitz.open("pdf", r.content)
    sizes = [(round(p.rect.width), round(p.rect.height)) for p in doc]
    doc.close()
    return sizes


def test_compress_extreme_keeps_page_size():
    assert _extreme_page_sizes(make_pdf(2)) == [A4, A4]


def test_compress_extreme_parallel_mixed_sizes():
    sizes = [A4, (842, 595)] * 5
    assert _extreme_page_sizes(make_pdf(len(sizes), sizes=sizes)) == sizes



def make_photo_pdf(pages=1, size=(1800, 1350), seed=0):
    """PDF com uma "foto" grande sem perda (gradiente + ruido), para medir a compressao."""
    import numpy as np
    rng = np.random.default_rng(seed)
    h, w = size[1], size[0]
    yy, xx = np.mgrid[0:h, 0:w]
    base = np.stack([xx * 255 / w, yy * 255 / h, (xx + yy) * 127 / (w + h)], axis=-1)
    pixels = np.clip(base + rng.normal(0, 18, (h, w, 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(pixels).save(buf, format="PNG")
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=A4[0], height=A4[1])
        page.insert_text((72, 60), "Relatorio com foto", fontsize=18)
        page.insert_image(fitz.Rect(36, 80, A4[0] - 36, 520), stream=buf.getvalue())
    data = doc.tobytes(deflate=True)
    doc.close()
    return data


def _compress(pdf_bytes, **fields):
    data = {k: str(v) for k, v in fields.items()}
    r = client.post("/api/compress", data=data, files=[("file", ("f.pdf", pdf_bytes, "application/pdf"))])
    assert r.status_code == 200, r.text
    return r.content


def test_compress_level_zero_is_lossless():
    original = make_photo_pdf()
    out = _compress(original, level=0)
    src, dst = fitz.open("pdf", original), fitz.open("pdf", out)
    try:
        src_px = [fitz.Pixmap(src, img[0]).samples for img in src[0].get_images()]
        dst_px = [fitz.Pixmap(dst, img[0]).samples for img in dst[0].get_images()]
        assert src_px == dst_px, "nivel 0 nao pode alterar as imagens"
        assert page_texts(out) == page_texts(original)
    finally:
        src.close()
        dst.close()
    # Nivel 0 == valor antigo "light"
    assert len(out) == len(_compress(original, level="light"))


def test_compress_slider_is_monotonic_and_beats_old_normal():
    from app.services.compressor import CompressorService
    original = make_photo_pdf()
    sizes = [len(_compress(original, level=lvl)) for lvl in (0, 30, 60, 100)]
    assert sizes == sorted(sizes, reverse=True), sizes
    assert sizes[-1] < sizes[0]

    # Antigo "Normal": JPEG qualidade 50, ate 2000 px
    tmp = UPLOADS_DIR / ("e" * 32)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        src = tmp / "in.pdf"
        src.write_bytes(original)
        old = CompressorService._recompress_images(src, tmp / "old.pdf", {"quality": 50, "max_dim": 2000})
        old = CompressorService._optimize(old, tmp / "old_opt.pdf")
        assert sizes[-1] < old.stat().st_size, "nivel maximo deve comprimir mais que o antigo Normal"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_compress_never_larger_than_light():
    original = make_pdf(3).getvalue()      # so texto: recomprimir imagens nao ajuda
    light = len(_compress(original, level=0))
    for lvl in (10, 50, 100):
        assert len(_compress(original, level=lvl)) <= light
    assert len(_compress(original, level=100, extreme="true")) <= light


def test_compress_extreme_sliders():
    photo = make_photo_pdf()
    best_photo = len(_compress(photo, level=75, extreme="true", image_level=0))
    small_photo = len(_compress(photo, level=75, extreme="true", image_level=100))
    assert small_photo < best_photo

    # Barra do texto: mede a rasterizacao direto (num PDF so de texto o servico
    # devolve o "Leve", que e menor, e nao haveria imagem para comparar)
    from app.services.compressor import CompressorService, raster_params
    tmp = UPLOADS_DIR / ("d" * 32)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        src = tmp / "in.pdf"
        src.write_bytes(make_pdf(2).getvalue())
        widths = []
        for i, lvl in enumerate((0, 100)):
            out = CompressorService._rasterize(src, tmp / f"r{i}.pdf", raster_params(lvl, 50))
            doc = fitz.open(str(out))
            widths.append(fitz.Pixmap(doc, doc[0].get_images()[0][0]).width)
            assert [round(p.rect.width) for p in doc] == [A4[0], A4[0]]
            doc.close()
        assert widths[1] < widths[0], widths    # mais compressao = menos pixels
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_compress_invalid_levels():
    pdf = make_pdf(1).getvalue()
    for fields in ({"level": "150"}, {"level": "-1"}, {"level": "abc"},
                   {"level": "50", "image_level": "101"}):
        r = client.post("/api/compress", data=fields, files=[("file", ("f.pdf", pdf, "application/pdf"))])
        assert r.status_code == 400, fields
        assert "Nivel de compressao" in r.json()["error"]

def test_extract_invalid_ranges():
    cases = {
        "10-20": "fora do intervalo",
        "abc": "Intervalo invalido",
        "3-1": "invertido",
        "0": "comeca em 1",
        "-": "Intervalo invalido",
    }
    for rng, expected in cases.items():
        r = client.post("/api/extract", data={"pages": rng},
                        files=[("file", ("x.pdf", make_pdf(3), "application/pdf"))])
        assert r.status_code == 400, rng
        assert expected in r.json()["error"], (rng, r.json())


def test_extract_open_ranges():
    r = client.post("/api/extract", data={"pages": "-2, 3-"},
                    files=[("file", ("x.pdf", make_pdf(4), "application/pdf"))])
    assert r.status_code == 200
    assert page_texts(r.content) == ["p0", "p1", "p2", "p3"]


def test_blank_threshold_validation():
    for value in ("0", "100", "150", "-5"):
        r = client.post("/api/remove-blanks/preview", data={"threshold": value},
                        files=[("file", ("b.pdf", make_blank_pdf(1), "application/pdf"))])
        assert r.status_code == 400, value


def test_invalid_pdf_returns_400():
    before = {p.name for p in UPLOADS_DIR.iterdir() if p.is_dir()}
    for payload in (b"not a pdf", b"%PDF-1.7\n" + b"\x00garbage" * 50):
        r = client.post("/api/split", files=[("file", ("bad.pdf", payload, "application/pdf"))])
        assert r.status_code == 400
        assert "PDF valido" in r.json()["error"]
    after = {p.name for p in UPLOADS_DIR.iterdir() if p.is_dir()}
    assert after <= before, "pasta da sessao nao foi removida"


def test_password_protected_pdf():
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    r = client.post("/api/merge", files=pdf_files(("s.pdf", io.BytesIO(data))))
    assert r.status_code == 400
    assert "senha" in r.json()["error"]


def test_office_rejects_unsupported_extension():
    r = client.post("/api/office-to-pdf", files=[("file", ("x.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 400


def test_images_to_pdf_modes_and_exif():
    files = [
        ("files", ("rgba.png", make_image("RGBA"), "image/png")),
        ("files", ("la.png", make_image("LA"), "image/png")),
        ("files", ("p.png", make_image("P"), "image/png")),
        # Orientacao 6 = girar 90 graus: 300x100 deve virar pagina "em pe"
        ("files", ("rot.jpg", make_image("RGB", (300, 100), "JPEG", exif_orientation=6), "image/jpeg")),
    ]
    r = client.post("/api/images-to-pdf", files=files)
    assert r.status_code == 200, r.text
    doc = fitz.open("pdf", r.content)
    assert doc.page_count == 4
    last = doc[3].rect
    assert last.height > last.width
    doc.close()


def test_images_to_pdf_invalid_image():
    r = client.post("/api/images-to-pdf", files=[("files", ("x.png", b"garbage", "image/png"))])
    assert r.status_code == 400


def test_single_shot_session_removed_after_download():
    before = {p.name for p in UPLOADS_DIR.iterdir() if p.is_dir()}
    r = client.post("/api/split", files=[("file", ("t.pdf", make_pdf(1), "application/pdf"))])
    assert r.status_code == 200
    after = {p.name for p in UPLOADS_DIR.iterdir() if p.is_dir()}
    assert after <= before


def test_csrf():
    url = "/api/merge"
    files = lambda: pdf_files(("a.pdf", make_pdf(1)))
    assert client.post(url, files=files(), headers={"origin": "http://evil.com"}).status_code == 403
    assert client.post(url, files=files(), headers={"origin": "null"}).status_code == 403
    assert client.post(url, files=files(),
                       headers={"referer": "http://evil.com/?testserver"}).status_code == 403
    assert client.post(url, files=files(), headers={"origin": "http://testserver"}).status_code == 200
    assert client.post(url, files=files(), headers={"referer": "http://testserver/merge"}).status_code == 200
    assert client.post(url, files=files(), headers={
        "origin": "https://pdf.example.com", "x-forwarded-host": "pdf.example.com"}).status_code == 200


def _tiny_app(max_bytes):
    async def echo(request):
        body = await request.body()
        return PlainTextResponse(str(len(body)))
    inner = Starlette(routes=[Route("/", echo, methods=["POST"])])
    return TestClient(BodySizeLimitMiddleware(inner, max_bytes=max_bytes, max_mb=1))


def test_body_limit_content_length():
    c = _tiny_app(100)
    assert c.post("/", content=b"x" * 50).text == "50"
    r = c.post("/", content=b"x" * 200)
    assert r.status_code == 413
    assert "limite" in r.json()["error"]


def test_body_limit_chunked():
    c = _tiny_app(100)

    def gen():
        for _ in range(10):
            yield b"x" * 50

    r = c.post("/", content=gen())
    assert r.status_code == 413


def test_cleanup_rules():
    now = time.time()
    old = now - 3600

    def make_dir(name, *files):
        d = UPLOADS_DIR / name
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            (d / f).write_text("x")
        os.utime(d, (old, old))
        return d

    expired = make_dir("a" * 32)
    busy = make_dir("b" * 32, BUSY_MARKER)
    interactive = make_dir("c" * 32, "session.json")
    os.utime(interactive, (now - 10 * 60, now - 10 * 60))
    unrelated = make_dir("nao_e_sessao")
    try:
        cleanup_expired(UPLOADS_DIR, delay_minutes=3, session_idle_minutes=30, busy_timeout_minutes=60)
        assert not expired.exists()
        assert busy.exists()
        assert interactive.exists()
        assert unrelated.exists()
    finally:
        import shutil
        for d in (expired, busy, interactive, unrelated):
            shutil.rmtree(d, ignore_errors=True)


def test_file_lock_is_exclusive():
    lock = UPLOADS_DIR / ".test.lock"
    lock.unlink(missing_ok=True)
    with file_lock(lock):
        try:
            with file_lock(lock, timeout=0.2):
                raise AssertionError("lock deveria estar ocupado")
        except TimeoutError:
            pass
    assert not lock.exists()


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"[OK] {test.__name__}")
        except pytest.skip.Exception as e:
            print(f"[SKIP] {test.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test.__name__}: {e!r}")
    print(f"\n{'=' * 40}\nResults: {len(tests) - failed} passed, {failed} failed out of {len(tests)} tests")
    sys.exit(1 if failed else 0)
