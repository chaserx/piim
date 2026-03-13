# PIIM Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that detects and masks PII (names, addresses, phones, emails, credit cards, account numbers) in PDF files, supporting both selectable-text and scanned PDFs.

**Architecture:** Four-stage pipeline (extract → detect → mask → export) with PyMuPDF as the PDF engine, EasyOCR for scanned pages, and Microsoft Presidio for PII detection. Each stage is a separate module communicating through shared dataclasses in `models.py`.

**Tech Stack:** Python 3.13, PyMuPDF, EasyOCR, presidio-analyzer, spacy (en_core_web_lg), Faker, argparse, pytest

**Spec:** `docs/superpowers/specs/2026-03-13-piim-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `piim/__init__.py` | Package marker |
| `piim/__main__.py` | Enables `python -m piim` |
| `piim/models.py` | `TextBlock` and `PiiEntity` dataclasses |
| `piim/extractor.py` | Extract text from PDF pages (native + OCR fallback) |
| `piim/detector/__init__.py` | Package marker |
| `piim/detector/base.py` | `PiiDetector` abstract base class |
| `piim/detector/presidio.py` | Presidio-based PII detection with offset→bbox mapping |
| `piim/masker.py` | Apply redactions (blackbox or fake data) with deduplication |
| `piim/exporter.py` | Strip metadata, save flattened PDF, handle `--in-place` |
| `piim/cli.py` | argparse CLI, pipeline orchestration, logging setup |
| `tests/conftest.py` | Shared fixtures (sample PDFs, text blocks, etc.) |
| `tests/test_models.py` | Tests for dataclass construction |
| `tests/test_extractor.py` | Tests for text extraction (native + OCR paths) |
| `tests/test_detector.py` | Tests for Presidio detector |
| `tests/test_masker.py` | Tests for both masking modes |
| `tests/test_exporter.py` | Tests for export and metadata stripping |
| `tests/test_cli.py` | Tests for CLI argument parsing and pipeline |
| `tests/test_integration.py` | End-to-end tests with fixture PDFs |
| `tests/fixtures/` | Directory for test PDF fixtures |
| `pyproject.toml` | Updated with dependencies and entry point |

---

## Chunk 1: Project Setup and Data Models

### Task 1: Project scaffolding and dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `piim/__init__.py`
- Create: `piim/__main__.py`
- Delete: `main.py` (replaced by package structure)

- [ ] **Step 1: Create the piim package directory**

```bash
mkdir -p piim
```

- [ ] **Step 2: Create `piim/__init__.py`**

```python
"""PIIM — PII Masker for PDFs."""
```

- [ ] **Step 3: Create `piim/__main__.py` (stub — cli.py created in Task 10)**

```python
"""Enable `python -m piim`."""


def main():
    """Placeholder until cli.py is implemented."""
    print("piim CLI not yet implemented")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update `pyproject.toml` with dependencies and entry point**

```toml
[project]
name = "piim"
version = "0.1.0"
description = "Detect and mask PII in PDF files"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "PyMuPDF>=1.25.0",
    "easyocr>=1.7.0",
    "presidio-analyzer>=2.2.0",
    "presidio-anonymizer>=2.2.0",
    "spacy>=3.7.0",
    "Faker>=33.0.0",
]

[project.scripts]
piim = "piim.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
]
```

- [ ] **Step 5: Install dependencies**

```bash
uv sync
uv run python -m spacy download en_core_web_lg
```

Expected: All packages install successfully. spaCy model downloads.

- [ ] **Step 6: Delete old `main.py`**

```bash
rm main.py
```

- [ ] **Step 7: Commit**

```bash
git add piim/__init__.py piim/__main__.py pyproject.toml uv.lock .python-version
git rm main.py
git commit -m "scaffold piim package with dependencies and entry point"
```

---

### Task 2: Data models

**Files:**
- Create: `piim/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for data models**

Create `tests/test_models.py`:

```python
"""Tests for shared data models."""

from piim.models import PiiEntity, TextBlock


class TestTextBlock:
    def test_create_native_text_block(self):
        block = TextBlock(
            text="John Smith",
            bbox=(100.0, 200.0, 200.0, 220.0),
            page_number=0,
            source="native",
            confidence=1.0,
        )
        assert block.text == "John Smith"
        assert block.bbox == (100.0, 200.0, 200.0, 220.0)
        assert block.page_number == 0
        assert block.source == "native"
        assert block.confidence == 1.0

    def test_create_ocr_text_block(self):
        block = TextBlock(
            text="555-1234",
            bbox=(50.0, 100.0, 150.0, 115.0),
            page_number=1,
            source="ocr",
            confidence=0.85,
        )
        assert block.source == "ocr"
        assert block.confidence == 0.85


class TestPiiEntity:
    def test_create_pii_entity(self):
        entity = PiiEntity(
            entity_type="PERSON",
            text="John Smith",
            score=0.95,
            bboxes=[(100.0, 200.0, 200.0, 220.0)],
            page_number=0,
        )
        assert entity.entity_type == "PERSON"
        assert entity.text == "John Smith"
        assert entity.score == 0.95
        assert len(entity.bboxes) == 1
        assert entity.page_number == 0

    def test_pii_entity_multiple_bboxes(self):
        entity = PiiEntity(
            entity_type="LOCATION",
            text="123 Main St Springfield",
            score=0.8,
            bboxes=[
                (50.0, 100.0, 200.0, 115.0),
                (50.0, 120.0, 200.0, 135.0),
            ],
            page_number=0,
        )
        assert len(entity.bboxes) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'piim.models'`

- [ ] **Step 3: Implement data models**

Create `piim/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add piim/models.py tests/test_models.py
git commit -m "add TextBlock and PiiEntity data models with tests"
```

---

## Chunk 2: Text Extraction

### Task 3: Native text extraction

**Files:**
- Create: `piim/extractor.py`
- Create: `tests/test_extractor.py`
- Create: `tests/conftest.py`

This task implements native (selectable) text extraction only. OCR fallback is added in Task 4.

- [ ] **Step 1: Write failing tests for native extraction**

Create `tests/conftest.py`:

```python
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
```

Create `tests/test_extractor.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_extractor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'piim.extractor'`

- [ ] **Step 3: Implement native text extraction**

Create `piim/extractor.py`:

```python
"""Text extraction from PDF pages — native text and OCR fallback."""

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
    """Extract text blocks using EasyOCR. Stub — implemented in Task 4."""
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_extractor.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add piim/extractor.py tests/test_extractor.py tests/conftest.py
git commit -m "add native text extraction from PDF pages"
```

---

### Task 4: OCR text extraction

**Files:**
- Modify: `piim/extractor.py`
- Modify: `tests/test_extractor.py`
- Modify: `tests/conftest.py`

This task implements OCR fallback. EasyOCR is slow/heavy in tests so we mock `_run_ocr` directly (dependency injection via patching the internal function).

- [ ] **Step 1: Write failing tests for OCR extraction**

Add to `tests/conftest.py`:

```python
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
```

Add to `tests/test_extractor.py`:

```python
from unittest.mock import patch

from piim.models import TextBlock


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_extractor.py::TestOcrExtraction -v
```

Expected: FAIL — `_run_ocr` returns `[]` (stub from Task 3), `_scale_ocr_bbox` does not exist.

- [ ] **Step 3: Implement OCR extraction**

Replace `_extract_ocr` in `piim/extractor.py`:

```python
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


def _scale_ocr_bbox(bbox_raw: list, dpi: int = 300) -> tuple[float, float, float, float]:
    """Convert EasyOCR pixel coordinates to PDF points."""
    scale = 72.0 / dpi
    xs = [pt[0] for pt in bbox_raw]
    ys = [pt[1] for pt in bbox_raw]
    return (min(xs) * scale, min(ys) * scale, max(xs) * scale, max(ys) * scale)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_extractor.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add piim/extractor.py tests/test_extractor.py tests/conftest.py
git commit -m "add OCR text extraction with EasyOCR fallback"
```

---

## Chunk 3: PII Detection

### Task 5: Detector interface

**Files:**
- Create: `piim/detector/__init__.py`
- Create: `piim/detector/base.py`

- [ ] **Step 1: Create the detector package**

Create `piim/detector/__init__.py`:

```python
"""PII detection module with pluggable detector interface."""
```

- [ ] **Step 2: Create the abstract detector interface**

Create `piim/detector/base.py`:

```python
"""Abstract base class for PII detectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

import fitz

from piim.models import PiiEntity, TextBlock


class PiiDetector(ABC):
    """Interface for PII detection implementations."""

    @abstractmethod
    def detect(
        self, text_blocks: list[TextBlock], doc: fitz.Document | None = None
    ) -> list[PiiEntity]:
        """Detect PII entities in the given text blocks.

        Args:
            text_blocks: Text blocks extracted from a PDF document.
            doc: Optional PyMuPDF document for precise bbox refinement
                 via page.search_for().

        Returns:
            List of detected PII entities with their bounding boxes.
        """
        ...
```

- [ ] **Step 3: Commit**

```bash
git add piim/detector/__init__.py piim/detector/base.py
git commit -m "add PiiDetector abstract interface"
```

---

### Task 6: Presidio detector

**Files:**
- Create: `piim/detector/presidio.py`
- Create: `tests/test_detector.py`

- [ ] **Step 1: Write failing tests for Presidio detector**

Create `tests/test_detector.py`:

```python
"""Tests for the Presidio PII detector."""

from piim.detector.presidio import PresidioDetector
from piim.models import TextBlock


class TestPresidioDetector:
    def setup_method(self):
        self.detector = PresidioDetector()

    def test_detects_person_name(self):
        blocks = [
            TextBlock(
                text="Contact John Smith for details",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        person_entities = [e for e in entities if e.entity_type == "PERSON"]
        assert len(person_entities) >= 1
        assert any("John Smith" in e.text for e in person_entities)

    def test_detects_email(self):
        blocks = [
            TextBlock(
                text="Email: john@example.com",
                bbox=(72.0, 100.0, 300.0, 114.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        email_entities = [e for e in entities if e.entity_type == "EMAIL_ADDRESS"]
        assert len(email_entities) == 1
        assert "john@example.com" in email_entities[0].text

    def test_detects_phone_number(self):
        blocks = [
            TextBlock(
                text="Phone: 555-123-4567",
                bbox=(72.0, 128.0, 300.0, 142.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        phone_entities = [e for e in entities if e.entity_type == "PHONE_NUMBER"]
        assert len(phone_entities) >= 1

    def test_detects_credit_card(self):
        blocks = [
            TextBlock(
                text="Card: 4111 1111 1111 1111",
                bbox=(72.0, 156.0, 300.0, 170.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        cc_entities = [e for e in entities if e.entity_type == "CREDIT_CARD"]
        assert len(cc_entities) >= 1

    def test_returns_empty_for_no_pii(self):
        blocks = [
            TextBlock(
                text="The weather is sunny today",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        assert len(entities) == 0

    def test_respects_min_confidence(self):
        blocks = [
            TextBlock(
                text="Email: john@example.com",
                bbox=(72.0, 100.0, 300.0, 114.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        # High threshold should filter out lower-confidence detections
        detector = PresidioDetector(min_confidence=0.99)
        entities = detector.detect(blocks)
        # Email patterns are typically very high confidence, so may still pass
        for e in entities:
            assert e.score >= 0.99

    def test_handles_multiple_pages(self):
        blocks = [
            TextBlock(
                text="Email: page0@example.com",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
            TextBlock(
                text="Email: page1@example.com",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=1,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        pages = {e.page_number for e in entities}
        assert 0 in pages
        assert 1 in pages

    def test_entity_has_bboxes(self):
        blocks = [
            TextBlock(
                text="Contact john@example.com today",
                bbox=(72.0, 100.0, 350.0, 114.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        for entity in entities:
            assert len(entity.bboxes) >= 1
            for bbox in entity.bboxes:
                assert len(bbox) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_detector.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'piim.detector.presidio'`

- [ ] **Step 3: Implement the Presidio detector**

Create `piim/detector/presidio.py`:

```python
"""Presidio-based PII detector implementation."""

from __future__ import annotations

import logging
import math
from itertools import groupby
from operator import attrgetter

import fitz
from presidio_analyzer import AnalyzerEngine

from piim.detector.base import PiiDetector
from piim.models import Bbox, PiiEntity, TextBlock

logger = logging.getLogger(__name__)

DEFAULT_ENTITIES = [
    "PERSON",
    "LOCATION",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "US_BANK_NUMBER",
]


class PresidioDetector(PiiDetector):
    """Detect PII using Microsoft Presidio's AnalyzerEngine."""

    def __init__(
        self,
        min_confidence: float = 0.5,
        entities: list[str] | None = None,
    ):
        self.min_confidence = min_confidence
        self.entities = entities or DEFAULT_ENTITIES
        self._analyzer = AnalyzerEngine()

    def detect(
        self, text_blocks: list[TextBlock], doc: fitz.Document | None = None
    ) -> list[PiiEntity]:
        if not text_blocks:
            return []

        results: list[PiiEntity] = []

        # Group blocks by page
        sorted_blocks = sorted(text_blocks, key=attrgetter("page_number"))
        for page_num, page_blocks_iter in groupby(
            sorted_blocks, key=attrgetter("page_number")
        ):
            page_blocks = list(page_blocks_iter)
            page = doc[page_num] if doc else None
            page_results = self._detect_page(page_num, page_blocks, page)
            results.extend(page_results)

        return results

    def _detect_page(
        self,
        page_num: int,
        blocks: list[TextBlock],
        page: fitz.Page | None,
    ) -> list[PiiEntity]:
        """Run detection on a single page's text blocks."""
        # Build concatenated text with offset map
        concatenated = ""
        offset_map: list[tuple[int, int, TextBlock]] = []

        for block in blocks:
            start = len(concatenated)
            concatenated += block.text
            end = len(concatenated)
            offset_map.append((start, end, block))
            concatenated += "\n"

        if not concatenated.strip():
            return []

        # Run Presidio analysis
        analyzer_results = self._analyzer.analyze(
            text=concatenated,
            entities=self.entities,
            language="en",
        )

        # Convert results to PiiEntity objects
        entities: list[PiiEntity] = []
        for result in analyzer_results:
            if result.score < self.min_confidence:
                continue

            entity_text = concatenated[result.start : result.end]
            # Replace delimiter newlines with spaces for search_for compatibility
            entity_text_clean = entity_text.replace("\n", " ")

            # Find overlapping text blocks for fallback bbox
            parent_blocks = self._find_parent_blocks(
                result.start, result.end, offset_map
            )
            if not parent_blocks:
                continue  # Skip entities with no matching blocks

            # Try precise bbox via search_for, fall back to block-level
            bboxes = self._refine_bboxes(
                entity_text_clean, parent_blocks, page
            )
            if not bboxes:
                continue  # Skip entities we can't locate

            entities.append(
                PiiEntity(
                    entity_type=result.entity_type,
                    text=entity_text_clean,
                    score=result.score,
                    bboxes=bboxes,
                    page_number=page_num,
                )
            )

        return entities

    def _find_parent_blocks(
        self,
        start: int,
        end: int,
        offset_map: list[tuple[int, int, TextBlock]],
    ) -> list[TextBlock]:
        """Find text blocks that overlap with a character range."""
        parents: list[TextBlock] = []
        for block_start, block_end, block in offset_map:
            if block_start < end and block_end > start:
                parents.append(block)
        return parents

    def _refine_bboxes(
        self,
        entity_text: str,
        parent_blocks: list[TextBlock],
        page: fitz.Page | None,
    ) -> list[Bbox]:
        """Get precise bboxes using page.search_for(), falling back to block bboxes."""
        if page is None:
            return [b.bbox for b in parent_blocks]

        search_results = page.search_for(entity_text)
        if not search_results:
            return [b.bbox for b in parent_blocks]

        if len(search_results) == 1:
            r = search_results[0]
            return [(r.x0, r.y0, r.x1, r.y1)]

        # Disambiguate: pick the result nearest to the parent block centroid
        parent_cx = sum(
            (b.bbox[0] + b.bbox[2]) / 2 for b in parent_blocks
        ) / len(parent_blocks)
        parent_cy = sum(
            (b.bbox[1] + b.bbox[3]) / 2 for b in parent_blocks
        ) / len(parent_blocks)

        best = min(
            search_results,
            key=lambda r: math.hypot(
                (r.x0 + r.x1) / 2 - parent_cx,
                (r.y0 + r.y1) / 2 - parent_cy,
            ),
        )
        return [(best.x0, best.y0, best.x1, best.y1)]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_detector.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add piim/detector/presidio.py tests/test_detector.py
git commit -m "add Presidio PII detector with offset-to-bbox mapping"
```

---

## Chunk 4: Masking

### Task 7: Black box masking

**Files:**
- Create: `piim/masker.py`
- Create: `tests/test_masker.py`

- [ ] **Step 1: Write failing tests for black box masking**

Create `tests/test_masker.py`:

```python
"""Tests for PII masking."""

from unittest.mock import MagicMock, call

import pytest

from piim.masker import apply_masks, deduplicate_entities
from piim.models import PiiEntity


class TestDeduplicateEntities:
    def test_no_overlap_keeps_all(self):
        entities = [
            PiiEntity("PERSON", "John", 0.9, [(10, 10, 50, 20)], 0),
            PiiEntity("EMAIL_ADDRESS", "j@x.com", 0.95, [(10, 30, 100, 40)], 0),
        ]
        result = deduplicate_entities(entities)
        assert len(result) == 2

    def test_overlapping_keeps_higher_confidence(self):
        entities = [
            PiiEntity("PERSON", "John Smith", 0.7, [(10, 10, 100, 20)], 0),
            PiiEntity("LOCATION", "Smith", 0.9, [(50, 10, 100, 20)], 0),
        ]
        result = deduplicate_entities(entities)
        assert len(result) == 1
        assert result[0].entity_type == "LOCATION"

    def test_equal_confidence_keeps_larger_span(self):
        entities = [
            PiiEntity("PERSON", "John Smith", 0.9, [(10, 10, 100, 20)], 0),
            PiiEntity("LOCATION", "Smith", 0.9, [(50, 10, 100, 20)], 0),
        ]
        result = deduplicate_entities(entities)
        assert len(result) == 1
        assert result[0].text == "John Smith"

    def test_same_bbox_different_pages_keeps_both(self):
        entities = [
            PiiEntity("PERSON", "John", 0.9, [(10, 10, 50, 20)], 0),
            PiiEntity("PERSON", "John", 0.9, [(10, 10, 50, 20)], 1),
        ]
        result = deduplicate_entities(entities)
        assert len(result) == 2


class TestBlackBoxMasking:
    def test_adds_redaction_annotations(self):
        page = MagicMock()
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        doc.__getitem__ = MagicMock(return_value=page)

        entities = [
            PiiEntity("PERSON", "John", 0.9, [(10, 10, 50, 20)], 0),
            PiiEntity("EMAIL_ADDRESS", "j@x.com", 0.95, [(10, 30, 100, 40)], 0),
        ]

        apply_masks(doc, entities, mask_type="blackbox")

        assert page.add_redact_annot.call_count == 2
        page.apply_redactions.assert_called_once()

    def test_black_fill_color(self):
        page = MagicMock()
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        doc.__getitem__ = MagicMock(return_value=page)

        entities = [
            PiiEntity("PERSON", "John", 0.9, [(10, 10, 50, 20)], 0),
        ]

        apply_masks(doc, entities, mask_type="blackbox")

        page.add_redact_annot.assert_called_once()
        _, kwargs = page.add_redact_annot.call_args
        assert kwargs.get("fill") == (0, 0, 0)

    def test_no_entities_skips_page(self):
        page = MagicMock()
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        doc.__getitem__ = MagicMock(return_value=page)

        apply_masks(doc, [], mask_type="blackbox")

        page.add_redact_annot.assert_not_called()
        page.apply_redactions.assert_not_called()

    def test_multi_page_entities(self):
        page0, page1 = MagicMock(), MagicMock()
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=2)
        doc.__getitem__ = MagicMock(side_effect=lambda i: [page0, page1][i])

        entities = [
            PiiEntity("PERSON", "John", 0.9, [(10, 10, 50, 20)], 0),
            PiiEntity("EMAIL_ADDRESS", "j@x.com", 0.95, [(10, 30, 100, 40)], 1),
        ]

        apply_masks(doc, entities, mask_type="blackbox")

        page0.add_redact_annot.assert_called_once()
        page0.apply_redactions.assert_called_once()
        page1.add_redact_annot.assert_called_once()
        page1.apply_redactions.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_masker.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'piim.masker'`

- [ ] **Step 3: Implement black box masking and deduplication**

Create `piim/masker.py`:

```python
"""Apply PII redactions to PDF documents."""

from __future__ import annotations

import logging
from itertools import groupby
from operator import attrgetter

import fitz

from piim.models import Bbox, PiiEntity

logger = logging.getLogger(__name__)


def deduplicate_entities(entities: list[PiiEntity]) -> list[PiiEntity]:
    """Remove overlapping PII entities, keeping the highest-confidence one.

    If scores are equal, the entity with the larger bbox span is preferred.
    """
    if len(entities) <= 1:
        return list(entities)

    # Sort by score descending, then by total bbox area descending
    sorted_entities = sorted(
        entities,
        key=lambda e: (e.score, _total_bbox_area(e.bboxes)),
        reverse=True,
    )

    kept: list[PiiEntity] = []
    for entity in sorted_entities:
        if not any(
            entity.page_number == k.page_number
            and _bboxes_overlap(entity.bboxes, k.bboxes)
            for k in kept
        ):
            kept.append(entity)

    return kept


def apply_masks(
    doc: fitz.Document,
    entities: list[PiiEntity],
    mask_type: str = "blackbox",
    seed: int = 0,
) -> None:
    """Apply redaction masks to the document in place.

    Args:
        doc: PyMuPDF document to modify.
        entities: Detected PII entities to mask.
        mask_type: "blackbox" or "fake".
        seed: Faker seed for reproducible fake data.
    """
    entities = deduplicate_entities(entities)

    # For fake mode: seed Faker once and share value_map across all pages
    value_map: dict[str, str] = {}
    fake = None
    if mask_type == "fake":
        from faker import Faker

        fake = Faker()
        Faker.seed(seed)

    # Group entities by page
    sorted_entities = sorted(entities, key=attrgetter("page_number"))
    for page_num, page_entities_iter in groupby(
        sorted_entities, key=attrgetter("page_number")
    ):
        page_entities = list(page_entities_iter)
        page = doc[page_num]

        if mask_type == "blackbox":
            _apply_blackbox(page, page_entities)
        elif mask_type == "fake":
            _apply_fake(page, page_entities, fake, value_map)


def _apply_blackbox(page: fitz.Page, entities: list[PiiEntity]) -> None:
    """Apply black box redactions to a page."""
    for entity in entities:
        for bbox in entity.bboxes:
            page.add_redact_annot(fitz.Rect(bbox), fill=(0, 0, 0))

    page.apply_redactions()


def _apply_fake(
    page: fitz.Page,
    entities: list[PiiEntity],
    fake,
    value_map: dict[str, str],
) -> None:
    """Apply fake data replacement to a page. Implemented in Task 8."""
    raise NotImplementedError("Fake data mode not yet implemented")


def _bboxes_overlap(a_bboxes: list[Bbox], b_bboxes: list[Bbox]) -> bool:
    """Check if any bbox in list a overlaps with any bbox in list b."""
    for a in a_bboxes:
        for b in b_bboxes:
            if a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]:
                return True
    return False


def _total_bbox_area(bboxes: list[Bbox]) -> float:
    """Calculate total area of all bounding boxes."""
    return sum((b[2] - b[0]) * (b[3] - b[1]) for b in bboxes)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_masker.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add piim/masker.py tests/test_masker.py
git commit -m "add black box masking with entity deduplication"
```

---

### Task 8: Fake data masking

**Files:**
- Modify: `piim/masker.py`
- Modify: `tests/test_masker.py`

- [ ] **Step 1: Write failing tests for fake data masking**

Add to `tests/test_masker.py`:

```python
class TestFakeDataMasking:
    def test_applies_white_redaction_then_inserts_text(self):
        page = MagicMock()
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        doc.__getitem__ = MagicMock(return_value=page)

        entities = [
            PiiEntity("PERSON", "John Smith", 0.9, [(10, 10, 100, 24)], 0),
        ]

        apply_masks(doc, entities, mask_type="fake", seed=42)

        # Should add white-filled redaction
        page.add_redact_annot.assert_called_once()
        _, kwargs = page.add_redact_annot.call_args
        assert kwargs.get("fill") == (1, 1, 1)

        # Should apply redactions before inserting text
        page.apply_redactions.assert_called_once()

        # Should insert replacement text
        page.insert_text.assert_called_once()

    def test_consistent_fake_data_same_seed(self):
        """Same seed + same input should produce same fake output."""
        page1 = MagicMock()
        doc1 = MagicMock()
        doc1.__len__ = MagicMock(return_value=1)
        doc1.__getitem__ = MagicMock(return_value=page1)

        page2 = MagicMock()
        doc2 = MagicMock()
        doc2.__len__ = MagicMock(return_value=1)
        doc2.__getitem__ = MagicMock(return_value=page2)

        entities = [
            PiiEntity("PERSON", "John Smith", 0.9, [(10, 10, 100, 24)], 0),
        ]

        apply_masks(doc1, entities, mask_type="fake", seed=42)
        apply_masks(doc2, entities, mask_type="fake", seed=42)

        # Both should insert the same fake text
        text1 = page1.insert_text.call_args[0][1]
        text2 = page2.insert_text.call_args[0][1]
        assert text1 == text2

    def test_fake_maps_entity_types_correctly(self):
        page = MagicMock()
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        doc.__getitem__ = MagicMock(return_value=page)

        entities = [
            PiiEntity("EMAIL_ADDRESS", "john@x.com", 0.9, [(10, 10, 150, 24)], 0),
        ]

        apply_masks(doc, entities, mask_type="fake", seed=42)

        inserted_text = page.insert_text.call_args[0][1]
        # Fake email should contain @ sign
        assert "@" in inserted_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_masker.py::TestFakeDataMasking -v
```

Expected: FAIL — `NotImplementedError: Fake data mode not yet implemented`

- [ ] **Step 3: Implement fake data masking**

Replace the `_apply_fake` function in `piim/masker.py`:

```python
def _apply_fake(
    page: fitz.Page,
    entities: list[PiiEntity],
    fake,
    value_map: dict[str, str],
) -> None:
    """Apply fake data replacement to a page.

    Args:
        page: PyMuPDF page to modify.
        entities: PII entities on this page.
        fake: Shared Faker instance (seeded once in apply_masks).
        value_map: Shared mapping of original->fake values across pages.
    """
    # Phase 1: Add white redactions for all entities
    entity_fakes: list[tuple[PiiEntity, str]] = []
    for entity in entities:
        if entity.text not in value_map:
            value_map[entity.text] = _generate_fake(fake, entity.entity_type)
        fake_text = value_map[entity.text]
        entity_fakes.append((entity, fake_text))

        for bbox in entity.bboxes:
            page.add_redact_annot(fitz.Rect(bbox), fill=(1, 1, 1))

    # Phase 2: Apply all redactions at once
    page.apply_redactions()

    # Phase 3: Insert fake text
    for entity, fake_text in entity_fakes:
        fake_lines = fake_text.split("\n") if "\n" in fake_text else [fake_text]

        for i, bbox in enumerate(entity.bboxes):
            if i < len(fake_lines):
                line_text = fake_lines[i]
            elif i == len(entity.bboxes) - 1 and len(fake_lines) > len(
                entity.bboxes
            ):
                # Join excess lines into last bbox
                line_text = " ".join(fake_lines[i:])
            else:
                continue

            bbox_height = bbox[3] - bbox[1]
            bbox_width = bbox[2] - bbox[0]
            fontsize = bbox_height * 0.8

            # Scale down font if text overflows
            text_width = fitz.get_text_length(line_text, fontsize=fontsize)
            if text_width > bbox_width and text_width > 0:
                fontsize *= bbox_width / text_width

            point = fitz.Point(bbox[0], bbox[3] - bbox_height * 0.15)
            page.insert_text(point, line_text, fontsize=fontsize)


def _generate_fake(fake, entity_type: str) -> str:
    """Generate a fake value for the given entity type."""
    generators = {
        "PERSON": fake.name,
        "LOCATION": fake.address,
        "PHONE_NUMBER": fake.phone_number,
        "EMAIL_ADDRESS": fake.email,
        "CREDIT_CARD": fake.credit_card_number,
        "US_BANK_NUMBER": fake.bban,
    }
    generator = generators.get(entity_type, fake.name)
    return generator()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_masker.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add piim/masker.py tests/test_masker.py
git commit -m "add fake data masking with consistent value mapping"
```

---

## Chunk 5: Export, CLI, and Integration

### Task 9: Exporter

**Files:**
- Create: `piim/exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: Write failing tests for exporter**

Create `tests/test_exporter.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_exporter.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'piim.exporter'`

- [ ] **Step 3: Implement exporter**

Create `piim/exporter.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_exporter.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add piim/exporter.py tests/test_exporter.py
git commit -m "add PDF exporter with metadata stripping and atomic in-place save"
```

---

### Task 10: CLI and pipeline orchestration

**Files:**
- Create: `piim/cli.py`
- Modify: `piim/__main__.py` (update to import from cli)
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for CLI argument parsing**

Create `tests/test_cli.py`:

```python
"""Tests for CLI argument parsing and pipeline."""

import os
from unittest.mock import MagicMock, patch

import fitz
import pytest

from piim.cli import build_parser, main


class TestArgParsing:
    def setup_method(self):
        self.parser = build_parser()

    def test_requires_input_files(self):
        with pytest.raises(SystemExit):
            self.parser.parse_args([])

    def test_accepts_single_file(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.input == ["file.pdf"]

    def test_accepts_multiple_files(self):
        args = self.parser.parse_args(["a.pdf", "b.pdf"])
        assert args.input == ["a.pdf", "b.pdf"]

    def test_default_mask_type(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.mask_type == "blackbox"

    def test_fake_mask_type(self):
        args = self.parser.parse_args(["--mask-type", "fake", "file.pdf"])
        assert args.mask_type == "fake"

    def test_default_suffix(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.suffix == "_redacted"

    def test_custom_suffix(self):
        args = self.parser.parse_args(["--suffix", "_clean", "file.pdf"])
        assert args.suffix == "_clean"

    def test_in_place_flag(self):
        args = self.parser.parse_args(["--in-place", "file.pdf"])
        assert args.in_place is True

    def test_default_min_confidence(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.min_confidence == 0.5

    def test_custom_min_confidence(self):
        args = self.parser.parse_args(["--min-confidence", "0.8", "file.pdf"])
        assert args.min_confidence == 0.8

    def test_seed_flag(self):
        args = self.parser.parse_args(["--seed", "42", "file.pdf"])
        assert args.seed == 42

    def test_verbose_flag(self):
        args = self.parser.parse_args(["--verbose", "file.pdf"])
        assert args.verbose is True


class TestMutualExclusivity:
    def test_in_place_with_output_dir_rejected(self):
        """Validation in main() calls parser.error() → SystemExit."""
        with pytest.raises(SystemExit):
            main(["--in-place", "--output-dir", "/tmp", "f.pdf"])

    def test_in_place_with_suffix_rejected(self):
        with pytest.raises(SystemExit):
            main(["--in-place", "--suffix", "_clean", "f.pdf"])


class TestPipeline:
    def test_processes_valid_pdf(self, native_text_pdf, tmp_path):
        output = str(tmp_path / "out")
        os.makedirs(output)

        exit_code = main(
            ["--output-dir", output, "--verbose", native_text_pdf]
        )

        assert exit_code == 0
        # Verify output file was created
        expected = os.path.join(output, "native_redacted.pdf")
        assert os.path.exists(expected)

    def test_rejects_non_pdf_file(self, tmp_path):
        non_pdf = str(tmp_path / "test.txt")
        with open(non_pdf, "w") as f:
            f.write("not a pdf")

        exit_code = main([non_pdf])
        assert exit_code == 1

    def test_skips_corrupted_pdf(self, tmp_path):
        bad_pdf = str(tmp_path / "bad.pdf")
        with open(bad_pdf, "w") as f:
            f.write("this is not a valid pdf")

        exit_code = main([bad_pdf])
        # Should not crash, should skip with error
        assert exit_code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'piim.cli'`

- [ ] **Step 3: Implement CLI and pipeline**

Create `piim/cli.py`:

```python
"""CLI entry point for PIIM."""

from __future__ import annotations

import argparse
import logging
import os
import sys

import fitz

from piim.detector.presidio import PresidioDetector
from piim.exporter import export_pdf
from piim.extractor import extract_text_blocks
from piim.masker import apply_masks

logger = logging.getLogger("piim")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="piim",
        description="Detect and mask PII in PDF files.",
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="One or more PDF files to process",
    )

    # Mask type
    parser.add_argument(
        "--mask-type",
        choices=["blackbox", "fake"],
        default="blackbox",
        help="Masking mode (default: blackbox)",
    )

    # Output options — validated manually since argparse doesn't support
    # mutual exclusivity between one flag and a group of flags.
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite original files",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for output files (default: same as input)",
    )
    parser.add_argument(
        "--suffix",
        default="_redacted",
        help="Suffix for output files (default: _redacted)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="Detection confidence threshold 0.0-1.0 (default: 0.5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Faker seed for reproducible fake data (default: 0)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detected entities and processing details",
    )

    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Validate argument combinations. Calls parser.error() on failure."""
    if args.in_place and args.output_dir:
        parser.error("cannot use --in-place with --output-dir")
    if args.in_place and args.suffix != "_redacted":
        parser.error("cannot use --in-place with --suffix")


def _resolve_output_path(
    input_path: str, args: argparse.Namespace
) -> str:
    """Determine the output file path for a given input."""
    base, ext = os.path.splitext(os.path.basename(input_path))
    output_name = f"{base}{args.suffix}{ext}"

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        return os.path.join(args.output_dir, output_name)
    else:
        return os.path.join(os.path.dirname(input_path) or ".", output_name)


def _process_file(
    input_path: str,
    args: argparse.Namespace,
    detector: PresidioDetector,
) -> bool:
    """Process a single PDF file. Returns True on success."""
    try:
        doc = fitz.open(input_path)
    except (fitz.FileDataError, RuntimeError):
        logger.error("Failed to open %s — skipping", input_path)
        return False

    try:
        # Stage 1: Extract
        logger.info("Extracting text from %s", input_path)
        text_blocks = extract_text_blocks(doc)

        if not text_blocks:
            logger.info("No text found in %s — skipping", input_path)
            return True

        # Stage 2: Detect
        logger.info("Detecting PII in %s", input_path)
        entities = detector.detect(text_blocks, doc=doc)

        if not entities:
            logger.info("No PII detected in %s — skipping", input_path)
            return True

        if args.verbose:
            for entity in entities:
                logger.info(
                    "  [page %d] %s: %r (%.2f)",
                    entity.page_number,
                    entity.entity_type,
                    entity.text,
                    entity.score,
                )

        # Stage 3: Mask
        logger.info(
            "Masking %d entities in %s (%s mode)",
            len(entities),
            input_path,
            args.mask_type,
        )
        apply_masks(doc, entities, mask_type=args.mask_type, seed=args.seed)

        # Stage 4: Export
        if args.in_place:
            export_pdf(doc, input_path, in_place=True)
        else:
            output_path = _resolve_output_path(input_path, args)
            export_pdf(doc, output_path)

        return True
    finally:
        doc.close()


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Configure logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    _validate_args(parser, args)

    # Validate input files
    valid_files: list[str] = []
    for path in args.input:
        if not path.lower().endswith(".pdf"):
            logger.error("Not a PDF file: %s — skipping", path)
            continue
        if not os.path.isfile(path):
            logger.error("File not found: %s — skipping", path)
            continue
        valid_files.append(path)

    if not valid_files:
        logger.error("No valid PDF files to process")
        return 1

    # Initialize detector once (expensive — loads spaCy model)
    detector = PresidioDetector(min_confidence=args.min_confidence)

    success_count = 0
    for path in valid_files:
        if _process_file(path, args, detector):
            success_count += 1

    if success_count == 0:
        return 1

    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Update `piim/__main__.py` to use the real CLI**

```python
"""Enable `python -m piim`."""

from piim.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add piim/cli.py piim/__main__.py tests/test_cli.py
git commit -m "add CLI with argument parsing and pipeline orchestration"
```

---

### Task 11: Integration tests

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_integration.py`:

```python
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

        exit_code = main([
            "--output-dir", output_dir,
            "--mask-type", "blackbox",
            "--verbose",
            pii_pdf,
        ])

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

        exit_code = main([
            "--output-dir", output_dir,
            "--mask-type", "fake",
            "--seed", "42",
            "--verbose",
            pii_pdf,
        ])

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
            assert meta.get("author", "") == ""
            assert meta.get("title", "") == ""
            doc.close()
```

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: All tests PASS. If any fail, debug and fix the pipeline.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests across all modules PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "add end-to-end integration tests for full pipeline"
```

---

### Task 12: Final cleanup

**Files:**
- Modify: `pyproject.toml` (verify final state)

- [ ] **Step 1: Verify the CLI works end-to-end manually**

```bash
# Create a test PDF and run piim on it
uv run python -c "
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), 'John Smith', fontsize=12)
page.insert_text((72, 100), 'john@example.com', fontsize=12)
doc.save('/tmp/test_piim.pdf')
doc.close()
"

uv run piim --verbose /tmp/test_piim.pdf
ls -la /tmp/test_piim_redacted.pdf
```

Expected: CLI runs, detects PII, creates redacted PDF.

- [ ] **Step 2: Run full test suite one more time**

```bash
uv run pytest -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 3: Commit any final adjustments**

```bash
git add -A
git status
# Only commit if there are changes
git commit -m "final cleanup and verification"
```
