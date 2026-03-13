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
    """Extract text blocks using EasyOCR. Returns empty list if unavailable."""
    raw_blocks = _run_ocr(page, page_num)
    # Filter low-confidence OCR results
    return [b for b in raw_blocks if b.confidence >= OCR_CONFIDENCE_THRESHOLD]


# Module-level cached EasyOCR reader (lazy-initialized)
_ocr_reader = None


def _get_ocr_reader():
    """Get or create the cached EasyOCR Reader instance."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
        except ImportError:
            return None
        _ocr_reader = easyocr.Reader(["en"], verbose=False)
    return _ocr_reader


def _run_ocr(page: fitz.Page, page_num: int) -> list[TextBlock]:
    """Run EasyOCR on a rendered page image."""
    reader = _get_ocr_reader()
    if reader is None:
        logger.warning("EasyOCR not available, skipping OCR for page %d", page_num)
        return []

    dpi = 300
    pix = page.get_pixmap(dpi=dpi)
    img_bytes = pix.tobytes("png")

    results = reader.readtext(img_bytes)

    blocks: list[TextBlock] = []
    for bbox_raw, text, confidence in results:
        bbox = _scale_ocr_bbox(bbox_raw, dpi)
        blocks.append(
            TextBlock(
                text=text,
                bbox=bbox,
                page_number=page_num,
                source="ocr",
                confidence=confidence,
            )
        )

    return blocks


def _scale_ocr_bbox(
    bbox_raw: list, dpi: int = 300
) -> tuple[float, float, float, float]:
    """Convert EasyOCR pixel coordinates to PDF points."""
    scale = 72.0 / dpi
    xs = [pt[0] for pt in bbox_raw]
    ys = [pt[1] for pt in bbox_raw]
    return (min(xs) * scale, min(ys) * scale, max(xs) * scale, max(ys) * scale)
