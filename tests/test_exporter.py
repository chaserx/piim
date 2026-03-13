"""Tests for PDF export."""

import os

import fitz
import pytest

from piim.exporter import export_pdf


class TestExporter:
    def _make_doc_with_metadata(self):
        doc = fitz.open()
        doc.new_page()
        doc.set_metadata(
            {
                "author": "John Smith",
                "title": "Secret Document",
                "creator": "SomeApp",
                "producer": "SomeLib",
            }
        )
        return doc

    def test_strips_metadata(self, tmp_path):
        doc = self._make_doc_with_metadata()
        output = str(tmp_path / "output.pdf")

        export_pdf(doc, output)
        doc.close()

        result = fitz.open(output)
        meta = result.metadata
        assert meta.get("author", "") == ""
        assert meta.get("title", "") == ""
        assert meta.get("creator", "") == ""
        result.close()

    def test_creates_output_file(self, tmp_path):
        doc = fitz.open()
        doc.new_page()
        output = str(tmp_path / "output.pdf")

        export_pdf(doc, output)
        doc.close()

        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_in_place_atomic_replace(self, tmp_path):
        # Create an original file
        original = str(tmp_path / "original.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.save(original)
        doc.close()

        original_size = os.path.getsize(original)

        # Open, modify, and export in-place
        doc = self._make_doc_with_metadata()
        export_pdf(doc, original, in_place=True)
        doc.close()

        # File should still exist and be valid
        assert os.path.exists(original)
        result = fitz.open(original)
        assert result.metadata.get("author", "") == ""
        result.close()

    def test_creates_output_dir_if_needed(self, tmp_path):
        doc = fitz.open()
        doc.new_page()
        output = str(tmp_path / "subdir" / "deep" / "output.pdf")

        export_pdf(doc, output)
        doc.close()

        assert os.path.exists(output)
