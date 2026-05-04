"""Validation tests for PDF Toolbox"""
import io
from fastapi.testclient import TestClient
from PyPDF2 import PdfWriter
from PIL import Image

from app.main import app

client = TestClient(app)


def make_pdf(pages=2):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf


def make_image():
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 200), color="red")
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_page_routes():
    pages = ["/", "/merge", "/split", "/compress", "/extract",
             "/pdf-to-images", "/images-to-pdf", "/office-to-pdf",
             "/pdf-to-office", "/detailed-merge"]
    for p in pages:
        r = client.get(p)
        assert r.status_code == 200, f"GET {p} returned {r.status_code}"
    print("[OK] All 10 page routes")


def test_merge():
    r = client.post("/api/merge", files=[
        ("files", ("a.pdf", make_pdf(2), "application/pdf")),
        ("files", ("b.pdf", make_pdf(1), "application/pdf")),
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    print("[OK] Merge PDFs")


def test_split():
    r = client.post("/api/split", files=[
        ("file", ("test.pdf", make_pdf(3), "application/pdf"))
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    print("[OK] Split PDF")


def test_compress_light():
    r = client.post("/api/compress", data={"level": "light"}, files=[
        ("file", ("test.pdf", make_pdf(2), "application/pdf"))
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    print("[OK] Compress - Light")


def test_compress_normal():
    r = client.post("/api/compress", data={"level": "normal"}, files=[
        ("file", ("test.pdf", make_pdf(2), "application/pdf"))
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    print("[OK] Compress - Normal")


def test_compress_extreme():
    r = client.post("/api/compress", data={"level": "extreme"}, files=[
        ("file", ("test.pdf", make_pdf(2), "application/pdf"))
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    print("[OK] Compress - Extreme")


def test_compress_default():
    r = client.post("/api/compress", files=[
        ("file", ("test.pdf", make_pdf(1), "application/pdf"))
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "test_compressed" in r.headers["content-disposition"]
    print("[OK] Compress - Default (Normal)")


def test_extract():
    r = client.post("/api/extract", data={"pages": "1-2"}, files=[
        ("file", ("test.pdf", make_pdf(3), "application/pdf"))
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    print("[OK] Extract pages")


def test_extract_preview():
    r = client.post("/api/extract/preview", data={"pages": "1,3"}, files=[
        ("file", ("test.pdf", make_pdf(3), "application/pdf"))
    ])
    assert r.status_code == 200
    data = r.json()
    assert data["total_selected"] == 2
    assert data["pages"][0]["page_number"] == 1
    assert data["pages"][1]["page_number"] == 3
    print("[OK] Extract preview")


def test_pdf_to_images():
    r = client.post("/api/pdf-to-images", data={"format": "png"}, files=[
        ("file", ("test.pdf", make_pdf(1), "application/pdf"))
    ])
    assert r.status_code == 200
    print("[OK] PDF to images")


def test_images_to_pdf():
    img = make_image()
    r = client.post("/api/images-to-pdf", files=[
        ("files", ("test.png", img, "image/png"))
    ])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    print("[OK] Images to PDF")


def test_detailed_merge():
    r = client.post("/api/detailed-merge/create-session")
    assert r.status_code == 200
    sid = r.json()["session_id"]

    r = client.post("/api/detailed-merge/add-pdf", data={"session_id": sid}, files=[
        ("files", ("test.pdf", make_pdf(3), "application/pdf"))
    ])
    assert r.json()["total_pages"] == 3

    r = client.post("/api/detailed-merge/reorder", data={
        "session_id": sid, "index": 0, "direction": "down"
    })
    assert r.json()["success"] is True
    assert "pages" in r.json()

    r = client.post("/api/detailed-merge/delete", data={
        "session_id": sid, "index": 1
    })
    assert r.json()["success"] is True
    assert len(r.json()["pages"]) == 2

    r = client.post("/api/detailed-merge/clear", data={"session_id": sid})
    assert r.json()["success"] is True
    assert len(r.json()["pages"]) == 0

    r = client.post("/api/detailed-merge/add-pdf", data={"session_id": sid}, files=[
        ("files", ("test.pdf", make_pdf(2), "application/pdf"))
    ])

    r = client.post("/api/detailed-merge/save", data={"session_id": sid})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    print("[OK] Detailed merge")


def test_pdf_to_office():
    r = client.post("/api/pdf-to-office", files=[
        ("file", ("test.pdf", make_pdf(1), "application/pdf"))
    ])
    assert r.status_code == 200
    print("[OK] PDF to Office")


def test_office_to_pdf_route():
    r = client.post("/api/office-to-pdf", files=[
        ("file", ("test.docx", b"dummy",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
    ])
    assert r.status_code == 500
    assert "LibreOffice" in r.json()["error"]
    print("[OK] Office to PDF (expected error - no LibreOffice)")


if __name__ == "__main__":
    tests = [
        test_page_routes,
        test_merge,
        test_split,
        test_compress_light,
        test_compress_normal,
        test_compress_extreme,
        test_compress_default,
        test_extract,
        test_extract_preview,
        test_pdf_to_images,
        test_images_to_pdf,
        test_detailed_merge,
        test_pdf_to_office,
        test_office_to_pdf_route,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test.__name__}: {e}")

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
