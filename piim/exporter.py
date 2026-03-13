"""Export redacted PDF documents."""

from __future__ import annotations

import logging
import os
import tempfile

import fitz

logger = logging.getLogger(__name__)


def export_pdf(
    doc: fitz.Document,
    output_path: str,
    in_place: bool = False,
) -> None:
    """Save the document as a clean, flattened PDF.

    Strips all metadata and saves with compression. For in-place mode,
    uses atomic temp file + replace to prevent data loss on failure.

    Args:
        doc: The PyMuPDF document to save.
        output_path: Path for the output file.
        in_place: If True, atomically replaces the file at output_path.
    """
    # Strip metadata
    doc.set_metadata({})

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if in_place:
        _save_in_place(doc, output_path)
    else:
        doc.save(output_path, garbage=4, deflate=True)
        logger.info("Saved redacted PDF to %s", output_path)


def _save_in_place(doc: fitz.Document, output_path: str) -> None:
    """Save to a temp file, then atomically replace the original."""
    output_dir = os.path.dirname(output_path) or "."

    try:
        with tempfile.NamedTemporaryFile(
            dir=output_dir, suffix=".pdf", delete=False
        ) as tmp:
            tmp_path = tmp.name

        doc.save(tmp_path, garbage=4, deflate=True)
        os.replace(tmp_path, output_path)
        logger.info("Replaced %s in place", output_path)
    except OSError as e:
        logger.error(
            "Failed to replace %s. Redacted file preserved at %s: %s",
            output_path,
            tmp_path,
            e,
        )
        raise
