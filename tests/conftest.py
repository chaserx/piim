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
