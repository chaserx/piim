"""Shared data types for the PIIM pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Bbox = tuple[float, float, float, float]


@dataclass
class TextBlock:
    """A block of text extracted from a PDF page with its position."""

    text: str
    bbox: Bbox  # x0, y0, x1, y1 in PDF points
    page_number: int
    source: Literal["native", "ocr"]
    confidence: float  # 1.0 for native text, EasyOCR's score for OCR


@dataclass
class PiiEntity:
    """A detected PII entity with its location in the PDF."""

    entity_type: str  # e.g., "PERSON", "EMAIL_ADDRESS"
    text: str
    score: float  # confidence 0.0-1.0
    bboxes: list[Bbox]  # PDF coordinates
    page_number: int
