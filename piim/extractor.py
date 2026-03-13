"""Text extraction from PDF pages -- native text and OCR fallback."""

from __future__ import annotations

import logging

import fitz

from piim.models import TextBlock

logger = logging.getLogger(__name__)

NATIVE_TEXT_THRESHOLD = 50  # minimum characters for native extraction
OCR_CONFIDENCE_THRESHOLD = 0.3


def extract_text_blocks(doc: fitz.Document) -> list[TextBlock]:
    """Extract text blocks from all pages of a PDF document.

    For each page, tries native text extraction first. If the page has
    fewer than NATIVE_TEXT_THRESHOLD characters of native text, falls
    back to OCR (if available).
    """
    blocks: list[TextBlock] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_blocks = _extract_native(page, page_num)

        total_chars = sum(len(b.text) for b in page_blocks)
        if total_chars >= NATIVE_TEXT_THRESHOLD:
            blocks.extend(page_blocks)
        else:
            ocr_blocks = _extract_ocr(page, page_num)
            if ocr_blocks:
                blocks.extend(ocr_blocks)
            else:
                # Fall back to whatever native text we got
                blocks.extend(page_blocks)

    return blocks


def _extract_native(page: fitz.Page, page_num: int) -> list[TextBlock]:
    """Extract text blocks using PyMuPDF's native text extraction."""
    text_dict = page.get_text("dict")
    result: list[TextBlock] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:  # type 0 = text block
            continue
        for line in block.get("lines", []):
            line_text = ""
            x0, y0, x1, y1 = float("inf"), float("inf"), 0.0, 0.0
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                line_text += (" " if line_text else "") + text
                bbox = span["bbox"]
                x0 = min(x0, bbox[0])
                y0 = min(y0, bbox[1])
                x1 = max(x1, bbox[2])
                y1 = max(y1, bbox[3])

            if line_text.strip():
                result.append(
                    TextBlock(
                        text=line_text.strip(),
                        bbox=(x0, y0, x1, y1),
                        page_number=page_num,
                        source="native",
                        confidence=1.0,
                    )
                )

    return result


def _extract_ocr(page: fitz.Page, page_num: int) -> list[TextBlock]:
    """Extract text blocks using EasyOCR. Stub -- implemented in Task 4."""
    return []
