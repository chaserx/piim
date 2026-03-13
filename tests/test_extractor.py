"""Tests for text extraction."""

import fitz

from piim.extractor import extract_text_blocks


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
