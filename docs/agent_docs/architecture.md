---
name: project architecture
description: details on the piim project architecture
---

## Architecture

The pipeline is orchestrated in `cli.py:_process_file` and flows through four stages, each in its own module. All stages communicate via shared dataclasses in `models.py` (`TextBlock` and `PiiEntity`).

- **`extractor.py`** — Extracts text with bounding boxes from each page. Uses PyMuPDF native extraction first; falls back to EasyOCR (lazy-loaded, module-level singleton) if a page has fewer than 50 characters of native text.
- **`detector/`** — Pluggable PII detection behind the `PiiDetector` ABC in `base.py`. The only implementation is `PresidioDetector` in `presidio.py`, which concatenates page text blocks, runs Presidio, then maps character offsets back to PDF bounding boxes using `page.search_for()` for precision.
- **`masker.py`** — Two modes: `blackbox` (black rectangles via PyMuPDF redact annotations) and `fake` (white redaction + Faker-generated replacement text). Deduplicates overlapping entities before masking. Fake values use a shared `value_map` so the same PII string gets the same replacement across pages.
- **`exporter.py`** — Saves with metadata stripping and compression. In-place mode uses atomic temp-file-then-replace.

### Key Types

- `Bbox = tuple[float, float, float, float]` — PDF coordinates (x0, y0, x1, y1) in points
- `TextBlock` — extracted text with position, page number, source (native/ocr), confidence
- `PiiEntity` — detected entity with type, text, score, bounding boxes, page number

### Key Dependencies

- **PyMuPDF (fitz)** — PDF reading, text extraction, redaction, image rendering.
- **Presidio** — Microsoft's PII detection engine (analyzer + anonymizer)
- **spaCy (en_core_web_lg)** — NLP model required by Presidio. Must be downloaded separately.
- **EasyOCR** — OCR fallback for scanned pages. Lazy-loaded only when needed.
- **Faker** — Generates replacement fake data in `fake` mask mode.
