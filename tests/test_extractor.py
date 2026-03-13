"""Tests for text extraction."""

from unittest.mock import patch

import fitz
import pytest

from piim.extractor import extract_text_blocks
from piim.models import TextBlock


class TestNativeExtraction:
    def test_extracts_text_from_native_pdf(self, native_text_pdf):
        doc = fitz.open(native_text_pdf)
        blocks = extract_text_blocks(doc)
        doc.close()

        assert len(blocks) > 0
        all_text = " ".join(b.text for b in blocks)
        assert "John Smith" in all_text
        assert "john@example.com" in all_text

    def test_native_blocks_have_correct_metadata(self, native_text_pdf):
        doc = fitz.open(native_text_pdf)
        blocks = extract_text_blocks(doc)
        doc.close()

        for block in blocks:
            assert block.source == "native"
            assert block.confidence == 1.0
            assert block.page_number == 0
            assert all(coord >= 0 for coord in block.bbox)

    def test_empty_pdf_returns_empty_list(self, empty_pdf):
        doc = fitz.open(empty_pdf)
        blocks = extract_text_blocks(doc)
        doc.close()

        assert blocks == []

    def test_multi_page_pdf(self, tmp_path):
        path = tmp_path / "multi.pdf"
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 72), f"Page {i} content", fontsize=12)
        doc.save(str(path))
        doc.close()

        doc = fitz.open(str(path))
        blocks = extract_text_blocks(doc)
        doc.close()

        page_numbers = {b.page_number for b in blocks}
        assert page_numbers == {0, 1, 2}


class TestOcrExtraction:
    def test_falls_back_to_ocr_for_image_pdf(self, scanned_pdf):
        fake_blocks = [
            TextBlock("Jane Doe", (24.0, 24.0, 48.0, 31.2), 0, "ocr", 0.92),
            TextBlock("jane@test.com", (24.0, 36.0, 60.0, 43.2), 0, "ocr", 0.88),
        ]

        with patch("piim.extractor._run_ocr", return_value=fake_blocks):
            doc = fitz.open(scanned_pdf)
            blocks = extract_text_blocks(doc)
            doc.close()

        assert len(blocks) == 2
        assert blocks[0].text == "Jane Doe"
        assert blocks[0].source == "ocr"
        assert blocks[0].confidence == 0.92

    def test_ocr_filters_low_confidence(self, scanned_pdf):
        fake_blocks = [
            TextBlock("Good text", (24.0, 24.0, 48.0, 31.2), 0, "ocr", 0.9),
            TextBlock("garbled", (24.0, 36.0, 48.0, 43.2), 0, "ocr", 0.15),
        ]

        with patch("piim.extractor._run_ocr", return_value=fake_blocks):
            doc = fitz.open(scanned_pdf)
            blocks = extract_text_blocks(doc)
            doc.close()

        # Low-confidence block should be filtered by _extract_ocr
        assert all(b.confidence >= 0.3 for b in blocks)

    def test_ocr_coordinate_scaling(self):
        """Verify _scale_ocr_bbox converts pixel coords to PDF points."""
        from piim.extractor import _scale_ocr_bbox

        # At 300 DPI, pixel (300, 300, 600, 360) -> PDF (72, 72, 144, 86.4)
        bbox = _scale_ocr_bbox(
            [[300, 300], [600, 300], [600, 360], [300, 360]], dpi=300
        )
        scale = 72.0 / 300
        assert bbox[0] == pytest.approx(300 * scale)
        assert bbox[1] == pytest.approx(300 * scale)
        assert bbox[2] == pytest.approx(600 * scale)
        assert bbox[3] == pytest.approx(360 * scale)
