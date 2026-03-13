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
├── cli.py            # CLI entry point (argparse)
├── extractor.py      # Text extraction: direct text via PyMuPDF, OCR via EasyOCR
├── detector/
│   ├── base.py       # Abstract detector interface (pluggable)
│   ├── presidio.py   # Presidio-based detector implementation
│   └── __init__.py
├── masker.py         # Applies redactions: black box or fake data
├── exporter.py       # Saves flattened PDF output
└── models.py         # Shared data types (PiiEntity, TextBlock, etc.)
```

Each module depends only on `models.py` for shared types, keeping them independently testable.

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

1. **Try native extraction first** — call `page.get_text("dict")` which returns text blocks with bounding box coordinates. If the page yields meaningful text (above a character count threshold), use it.
2. **Fall back to OCR** — if the page has little/no selectable text (likely scanned), render to pixmap via `page.get_pixmap(dpi=300)`, pass image bytes to EasyOCR, which returns `(bbox, text, confidence)` tuples.

### Coordinate Mapping

EasyOCR returns pixel coordinates relative to the rendered image. These are scaled back to PDF points using the pixmap's known DPI resolution.

### Output Model

```python
@dataclass
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points
    source: Literal["native", "ocr"]
    confidence: float  # 1.0 for native text, EasyOCR's score for OCR
```

The extractor returns `list[TextBlock]` per page. Downstream modules don't need to know whether text came from native extraction or OCR.

## Stage 2: PII Detection (`detector/`)

### Pluggable Interface

```python
class PiiDetector(ABC):
    @abstractmethod
    def detect(self, text_blocks: list[TextBlock]) -> list[PiiEntity]:
        ...
```

### Presidio Implementation

- Concatenates text blocks into a single string, tracking character offset → TextBlock mapping
- Runs `AnalyzerEngine.analyze()` with configured entity types
- Maps Presidio's character-offset results back to originating TextBlock(s) and their bounding boxes

### Supported PII Types (Initial Version)

| Entity Type | Presidio Entity |
|-------------|----------------|
| Names | `PERSON` |
| Addresses | `LOCATION` |
| Phone numbers | `PHONE_NUMBER` |
| Email addresses | `EMAIL_ADDRESS` |
| Credit card numbers | `CREDIT_CARD` |
| Account numbers | `US_BANK_NUMBER` |

Architecture supports adding more types by extending the entity list.

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

A `--min-confidence` CLI flag (default 0.5) filters out low-confidence detections.

## Stage 3: Masking (`masker.py`)

Two modes, selected via `--mask-type` CLI flag:

### Black Box Mode (`blackbox`)

- For each `PiiEntity`, iterate its bounding boxes
- Call `page.add_redact_annot(bbox, fill=(0, 0, 0))` — black rectangle
- Call `page.apply_redactions()` — permanently removes underlying text

### Fake Data Mode (`fake`)

- Use `Faker` to generate replacement values based on entity type:
  - `PERSON` → `faker.name()`
  - `LOCATION` → `faker.address()`
  - `PHONE_NUMBER` → `faker.phone_number()`
  - `EMAIL_ADDRESS` → `faker.email()`
  - `CREDIT_CARD` → `faker.credit_card_number()`
  - `US_BANK_NUMBER` → `faker.bban()`
- Apply white-filled redaction to erase original: `page.add_redact_annot(bbox, fill=(1, 1, 1))`
- Call `page.apply_redactions()`
- Insert fake text at the same position: `page.insert_text(point, fake_value, fontsize=estimated_size)`
- Font size estimated from bounding box height

### Consistency

For fake data mode, `Faker` is seeded and a mapping of `original_value → fake_value` is maintained across the document so the same real value always maps to the same fake value.

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
  --verbose             Show detected entities and processing details
```

**Output naming:** `receipt.pdf` → `receipt_redacted.pdf` by default. Customizable via `--suffix`.

**Multiple file support:** Accepts multiple paths, processes sequentially.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid/corrupted PDF | Catch `fitz.FileDataError`, log message, skip file, continue |
| OCR failure on a page | Log warning, continue with native text if available |
| No PII detected | Log "no PII detected", skip file (no output produced) |
| Unsupported file type | Validate `.pdf` extension upfront, reject with error |

## Testing Strategy

### Unit Tests

- **extractor:** Mock PyMuPDF page objects, verify TextBlock output for both native and OCR paths
- **detector/presidio:** Feed known text blocks, assert correct PiiEntity results
- **masker:** Mock PyMuPDF document, verify correct redaction calls for both modes
- **exporter:** Verify metadata stripping and save options

### Integration Tests

- Text-based PDF with known PII → verify redacted output contains no PII in extracted text
- Scanned PDF (image-based) → verify OCR + detection + redaction pipeline end-to-end

### Framework

pytest
