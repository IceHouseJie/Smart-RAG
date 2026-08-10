"""扫描件视觉提取（_extract_document_text 回退到 llm.vision_extract_text）测试。"""

import io

import main
import llm
import parsers


def _make_scanned_pdf() -> bytes:
    """构造无文字层的图片型 PDF，模拟扫描件。"""
    import pymupdf
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 120), "white")
    ImageDraw.Draw(img).text((20, 40), "SCANNED DOC 888", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    doc = pymupdf.open()
    page = doc.new_page(width=400, height=120)
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc.tobytes()


def _make_text_pdf() -> bytes:
    """带文字层的最小 PDF，pypdf 可直接提取。"""
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "TEXT PDF 123")
    return doc.tobytes()


def test_scanned_pdf_falls_back_to_vision(monkeypatch):
    monkeypatch.setattr(llm, "vision_extract_text", lambda pages: "SCANNED DOC 888")
    text = main._extract_document_text("scan.pdf", _make_scanned_pdf())
    assert "SCANNED DOC 888" in text


def test_text_pdf_does_not_call_vision(monkeypatch):
    called = []

    def fake_vision(pages):
        called.append(True)
        return "不应被调用"

    monkeypatch.setattr(llm, "vision_extract_text", fake_vision)
    text = main._extract_document_text("doc.pdf", _make_text_pdf())
    assert text.strip() == "TEXT PDF 123"
    assert not called  # 有文字层，不该触发视觉


def test_non_pdf_empty_stays_empty(monkeypatch):
    monkeypatch.setattr(llm, "vision_extract_text", lambda pages: "X")
    text = main._extract_document_text("empty.txt", b"   ")
    assert text.strip() == ""  # 非 PDF 且无文字 → 保持空，不由视觉兜底


def test_render_pdf_pages_returns_pngs():
    pages = parsers.render_pdf_pages(_make_scanned_pdf())
    assert len(pages) >= 1
    assert all(p.startswith(b"\x89PNG") for p in pages)  # PNG 魔数
