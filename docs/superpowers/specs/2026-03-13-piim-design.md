# PIIM — PII Masker for PDFs

## Overview

PIIM is a lightweight Python CLI tool that detects and masks personally identifiable information (PII) in PDF files. It handles both selectable-text and scanned/image-based PDFs through a four-stage pipeline: extract, detect, mask, export.

**Primary use case:** Personal/small-batch CLI usage — process a few PDFs at a time.

## Architecture

### Pipeline

```
PDF Input
  → Extractor (text extraction / OCR)
    → Detector (PII detection via pluggable interface)
      → Masker (black box or fake data replacement)
        → Exporter (flattened PDF output)
```

### Module Structure

```
piim/
├── __init__.py
├── __main__.py       # Enables `python -m piim` (calls cli.main())
├── cli.py            # CLI entry point (argparse)
├── extractor.py      # Text extraction: direct text via PyMuPDF, OCR via EasyOCR
├── detector/
│   ├── __init__.py
│   ├── base.py       # Abstract detector interface (pluggable)
│   └── presidio.py   # Presidio-based detector implementation
├── masker.py         # Applies redactions: black box or fake data
├── exporter.py       # Saves flattened PDF output
└── models.py         # Shared data types (PiiEntity, TextBlock, etc.)
```

Each module depends only on `models.py` for shared types, keeping them independently testable.

### Entry Point

In `pyproject.toml`:

```toml
[project.scripts]
piim = "piim.cli:main"
```

This allows invocation via `piim` after install, or `python -m piim` during development.

## Dependencies

| Package | Purpose |
|---------|---------|
| PyMuPDF (fitz) | PDF text extraction, coordinate lookup, redaction, flattened export |
| EasyOCR | OCR for scanned/image-based pages |
| presidio-analyzer | PII detection engine |
| presidio-anonymizer | PII anonymization operators |
| spacy + en_core_web_lg | NLP model backing Presidio |
| Faker | Fake data generation for replacement mode |
| pytest | Testing |

## Stage 1: Text Extraction (`extractor.py`)

### Strategy

For each page in the PDF:

1. **Try native extraction first** — call `page.get_text("dict")` which returns text blocks with bounding box coordinates. If the page yields meaningful text (50 or more characters), use it.
2. **Fall back to OCR** — if the page has little/no selectable text (likely scanned), render to pixmap via `page.get_pixmap(dpi=300)`, pass image bytes to EasyOCR, which returns `(bbox, text, confidence)` tuples.

**Known limitation:** Mixed pages (partially native text, partially scanned images) are handled with a binary native-or-OCR decision per page. If the page passes the native text threshold, embedded images with text will not be OCR'd. This is an acceptable tradeoff for v1 — most receipt PDFs are consistently one type or the other.

### EasyOCR Configuration

The EasyOCR `Reader` is initialized with `['en']` (English only) by default. Multi-language support is out of scope for v1 but could be added via a `--languages` CLI flag later.

### Coordinate Mapping

EasyOCR returns pixel coordinates relative to the rendered image. These are scaled back to PDF points using the pixmap's known DPI resolution: `pdf_coord = pixel_coord * 72 / dpi`.

### Output Model

```python
@dataclass
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points
    page_number: int
    source: Literal["native", "ocr"]
    confidence: float  # 1.0 for native text, EasyOCR's score for OCR
```

The extractor returns `list[TextBlock]` for the entire document. Each block carries its `page_number` so downstream modules can group by page.

### OCR Confidence Pre-filter

Text blocks with OCR confidence below 0.3 are discarded before reaching the detector. This prevents garbled OCR text from producing false-positive PII detections.

## Stage 2: PII Detection (`detector/`)

### Pluggable Interface

```python
class PiiDetector(ABC):
    @abstractmethod
    def detect(self, text_blocks: list[TextBlock]) -> list[PiiEntity]:
        ...
```

### Presidio Implementation

#### Offset-to-BBox Mapping Algorithm

1. Group text blocks by page.
2. For each page, concatenate text blocks with `"\n"` as delimiter, building an offset map: a list of `(start_offset, end_offset, TextBlock)` tuples.
3. Run `AnalyzerEngine.analyze()` on the concatenated string.
4. For each Presidio result, find the overlapping TextBlock(s) via the offset map.
5. Use `page.search_for(entity_text)` to get precise bounding boxes for the detected PII substring within the page. This gives character-level precision rather than block-level — avoiding over-redaction of surrounding text.
6. **Disambiguation for repeated text:** `search_for()` returns all occurrences on the page. Select the result whose bbox overlaps or is nearest to the parent TextBlock's bbox (by centroid distance). Each detected PII entity maps to exactly one `search_for()` result.
7. If `search_for()` returns no results (e.g., OCR text doesn't exactly match), fall back to the TextBlock's full bbox.

### Supported PII Types (Initial Version)

| Entity Type | Presidio Entity |
|-------------|----------------|
| Names | `PERSON` |
| Addresses | `LOCATION` |
| Phone numbers | `PHONE_NUMBER` |
| Email addresses | `EMAIL_ADDRESS` |
| Credit card numbers | `CREDIT_CARD` |
| Account numbers | `US_BANK_NUMBER` |

Architecture supports adding more types by extending the entity list. SSNs (`US_SSN`) are a natural addition but excluded from v1 since the primary use case is receipts, which typically don't contain SSNs.

### Extensibility

New detectors implement `PiiDetector`. A future `--detector` CLI flag can select between implementations. Multiple detectors can be composed — run both and merge/deduplicate results.

### Output Model

```python
@dataclass
class PiiEntity:
    entity_type: str          # e.g., "PERSON", "EMAIL_ADDRESS"
    text: str                 # the detected value
    score: float              # confidence 0.0-1.0
    bboxes: list[tuple[float, float, float, float]]  # PDF coordinates
    page_number: int
```

A `--min-confidence` CLI flag (default 0.5) filters out low-confidence detections. This filters on the Presidio detection score, not the OCR confidence (which is handled separately via the pre-filter in Stage 1).

## Stage 3: Masking (`masker.py`)

Two modes, selected via `--mask-type` CLI flag.

### Redaction Ordering

**Critical implementation constraint:** For each page, the masker must:

1. Add all `add_redact_annot()` calls first (for every entity on the page).
2. Call `page.apply_redactions()` exactly once per page.
3. Only then (in fake mode) perform all `insert_text()` calls.

This ordering is required because `apply_redactions()` mutates the page content, which would invalidate subsequent bounding box coordinates if called per-entity.

### Black Box Mode (`blackbox`)

- For each `PiiEntity`, iterate its bounding boxes
- Call `page.add_redact_annot(bbox, fill=(0, 0, 0))` — black rectangle
- After all entities on the page are annotated, call `page.apply_redactions()` once

### Fake Data Mode (`fake`)

- Use `Faker` to generate replacement values based on entity type:
  - `PERSON` → `faker.name()`
  - `LOCATION` → `faker.address()`
  - `PHONE_NUMBER` → `faker.phone_number()`
  - `EMAIL_ADDRESS` → `faker.email()`
  - `CREDIT_CARD` → `faker.credit_card_number()`
  - `US_BANK_NUMBER` → `faker.bban()`
- Apply white-filled redaction to erase original: `page.add_redact_annot(bbox, fill=(1, 1, 1))`
- Call `page.apply_redactions()` once per page
- Insert fake text at the same position: `page.insert_text(point, fake_value, fontsize=estimated_size)`

#### Text Overflow and Font Handling

- **Font size:** Estimated from bounding box height (`bbox_height * 0.8` as a starting approximation).
- **Font family:** Uses PyMuPDF's default font (Helvetica). Visual consistency with the original document is not a goal — the purpose is readability and data replacement, not pixel-perfect reproduction.
- **Overflow:** If the fake text is wider than the original bounding box, the font size is scaled down proportionally to fit within the bbox width. This prevents overlapping adjacent content.
- **Multi-line entities:** Addresses may span multiple bounding boxes. Each bbox is treated independently. The fake address (from `faker.address()`) is split by newline. If the fake address has fewer lines than bboxes, extra bboxes are left empty. If more lines, excess lines are joined into the last bbox.

### Consistency

For fake data mode, `Faker` is seeded with a fixed default seed (`0`) for reproducibility. A `--seed` CLI flag can optionally override it. A mapping of `original_value → fake_value` is maintained across the document so the same real value always maps to the same fake value.

## Stage 4: Export (`exporter.py`)

- Strip document metadata (author, creator, producer, title) via `doc.set_metadata({})` to prevent PII leaking through metadata
- Save with `doc.save(output_path, garbage=4, deflate=True)` — `garbage=4` removes unused objects, `deflate` compresses
- For `--in-place` mode, save to a temp file first, then atomically replace the original

## CLI Interface (`cli.py`)

```
piim [OPTIONS] INPUT [INPUT...]

Arguments:
  INPUT                 One or more PDF files to process

Options:
  --mask-type           blackbox | fake (default: blackbox)
  --output-dir DIR      Directory for output files (default: same as input)
  --suffix TEXT         Suffix for output files (default: "_redacted")
  --in-place            Overwrite original files
  --min-confidence      Detection threshold 0.0-1.0 (default: 0.5)
  --seed INT            Faker seed for reproducible fake data (default: 0)
  --verbose             Show detected entities and processing details
```

**Mutual exclusivity:** `--in-place` is mutually exclusive with `--output-dir` and `--suffix`. The CLI rejects the combination with an error message.

**Output naming:** `receipt.pdf` → `receipt_redacted.pdf` by default. Customizable via `--suffix`.

**Multiple file support:** Accepts multiple paths, processes sequentially.

**Output directory creation:** If `--output-dir` does not exist, it is created (including intermediate directories).

### Logging

Uses Python's `logging` module. Default level: WARNING. `--verbose` sets level to INFO and prints detected entities per page with their types and confidence scores.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid/corrupted PDF | Catch `fitz.FileDataError`, log error with filename, skip file, continue |
| OCR failure on a page | Log warning with page number, continue with native text if available |
| No PII detected | Log "no PII detected in {filename}" at INFO level, skip file (no output). Clearly distinct from error messages. |
| Unsupported file type | Validate `.pdf` extension upfront, reject with error |
| `--in-place` + `--output-dir` | Reject with error: "cannot use --in-place with --output-dir" |

## Testing Strategy

### Unit Tests

- **extractor:** Mock PyMuPDF page objects, verify TextBlock output for both native and OCR paths
- **detector/presidio:** Feed known text blocks, assert correct PiiEntity results (known names, emails, phone numbers)
- **masker:** Mock PyMuPDF document, verify correct redaction calls for both modes, verify redaction ordering (annotate all → apply once → insert text)
- **exporter:** Verify metadata stripping and save options

### Integration Tests

- Text-based PDF with known PII → verify redacted output has no PII in extracted text
- Scanned PDF (image-based) → verify OCR + detection + redaction pipeline end-to-end

### Framework

pytest
