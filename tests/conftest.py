"""Shared test fixtures."""

import fitz
import pytest

from piim.models import TextBlock


@pytest.fixture
def native_text_pdf(tmp_path) -> str:
    """Create a simple PDF with selectable text containing PII."""
    path = tmp_path / "native.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "John Smith", fontsize=12)
    page.insert_text((72, 100), "john@example.com", fontsize=12)
    page.insert_text((72, 128), "555-123-4567", fontsize=12)
    page.insert_text((72, 156), "123 Main Street, Springfield", fontsize=12)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def empty_pdf(tmp_path) -> str:
    """Create a PDF with no text (blank page)."""
    path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def scanned_pdf(tmp_path) -> str:
    """Create a PDF with text rendered as an image (simulates scanned doc)."""
    path = tmp_path / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Insert text then convert to image to simulate a scanned page
    page.insert_text((72, 72), "Jane Doe", fontsize=14)
    page.insert_text((72, 100), "jane@test.com", fontsize=14)
    # Render to image and create new page from it
    pix = page.get_pixmap(dpi=150)
    doc2 = fitz.open()
    img_page = doc2.new_page(width=612, height=792)
    img_page.insert_image(fitz.Rect(0, 0, 612, 792), pixmap=pix)
    doc2.save(str(path))
    doc2.close()
    doc.close()
    return str(path)
