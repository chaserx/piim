"""End-to-end integration tests."""

import os

import fitz
import pytest

from piim.cli import main


@pytest.fixture
def pii_pdf(tmp_path) -> str:
    """Create a PDF containing various PII types."""
    path = str(tmp_path / "pii_receipt.pdf")
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    y = 72
    lines = [
        "RECEIPT",
        "",
        "Customer: John Smith",
        "Email: john.smith@example.com",
        "Phone: 555-123-4567",
        "Card ending: 4111 1111 1111 1111",
        "",
        "Item: Widget x2     $19.99",
        "Total:              $19.99",
    ]
    for line in lines:
        if line:
            page.insert_text((72, y), line, fontsize=11)
        y += 18

    doc.save(path)
    doc.close()
    return path


class TestBlackboxIntegration:
    def test_redacts_pii_from_text_pdf(self, pii_pdf, tmp_path):
        output_dir = str(tmp_path / "output")

        exit_code = main(
            [
                "--output-dir",
                output_dir,
                "--mask-type",
                "blackbox",
                "--verbose",
                pii_pdf,
            ]
        )

        assert exit_code == 0

        # Check output file exists
        output_file = os.path.join(output_dir, "pii_receipt_redacted.pdf")
        assert os.path.exists(output_file)

        # Verify PII is removed from text layer
        doc = fitz.open(output_file)
        text = doc[0].get_text()
        doc.close()

        # These PII values should NOT appear in redacted output
        assert "john.smith@example.com" not in text.lower()
        assert "4111 1111 1111 1111" not in text

        # Non-PII content should remain
        assert "RECEIPT" in text
        assert "Widget" in text


class TestFakeDataIntegration:
    def test_replaces_pii_with_fake_data(self, pii_pdf, tmp_path):
        output_dir = str(tmp_path / "output")

        exit_code = main(
            [
                "--output-dir",
                output_dir,
                "--mask-type",
                "fake",
                "--seed",
                "42",
                "--verbose",
                pii_pdf,
            ]
        )

        assert exit_code == 0

        output_file = os.path.join(output_dir, "pii_receipt_redacted.pdf")
        assert os.path.exists(output_file)

        doc = fitz.open(output_file)
        text = doc[0].get_text()
        doc.close()

        # Original PII should be gone
        assert "john.smith@example.com" not in text.lower()

        # Non-PII content should remain
        assert "RECEIPT" in text


class TestInPlace:
    def test_in_place_modifies_original(self, pii_pdf):
        # Read original text
        doc = fitz.open(pii_pdf)
        original_text = doc[0].get_text()
        doc.close()
        assert "john.smith@example.com" in original_text.lower()

        # Run in-place
        exit_code = main(["--in-place", pii_pdf])
        assert exit_code == 0

        # Verify PII removed
        doc = fitz.open(pii_pdf)
        redacted_text = doc[0].get_text()
        doc.close()
        assert "john.smith@example.com" not in redacted_text.lower()


class TestNoPii:
    def test_skips_file_with_no_pii(self, tmp_path):
        path = str(tmp_path / "clean.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "The weather is sunny today", fontsize=12)
        doc.save(path)
        doc.close()

        output_dir = str(tmp_path / "output")
        exit_code = main(["--output-dir", output_dir, "--verbose", path])

        assert exit_code == 0
        # No output file should be created
        output_file = os.path.join(output_dir, "clean_redacted.pdf")
        assert not os.path.exists(output_file)


class TestMetadataStripping:
    def test_output_has_no_metadata(self, pii_pdf, tmp_path):
        # Add metadata to source
        doc = fitz.open(pii_pdf)
        doc.set_metadata({"author": "Secret Author", "title": "Secret Title"})
        doc.save(pii_pdf, incremental=True, encryption=0)
        doc.close()

        output_dir = str(tmp_path / "output")
        main(["--output-dir", output_dir, pii_pdf])

        output_file = os.path.join(output_dir, "pii_receipt_redacted.pdf")
        if os.path.exists(output_file):
            doc = fitz.open(output_file)
            meta = doc.metadata
            assert meta is not None
            assert meta.get("author", "") == ""
            assert meta.get("title", "") == ""
            doc.close()
