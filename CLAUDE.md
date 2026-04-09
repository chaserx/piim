# CLAUDE.md

## What This Is

piim is a CLI tool that detects and masks PII in PDFs. It processes documents through a four-stage pipeline: Extract → Detect → Mask → Export. Handles both native-text and scanned/image PDFs via OCR fallback.

## Build/Test/Lint Commands
- Install deps: `uv sync`
- Run all tests: `uv run pytest --cache-clear -vv tests`
  - Download required spaCy model (needed before running tests or the piim script): `uv run -- spacy download en_core_web_lg`
  - Tests use PyMuPDF (formerly known as fitz) to generate fixture PDFs in-memory (see `conftest.py`). The `native_text_pdf`, `empty_pdf`, and `scanned_pdf` fixtures create temporary PDFs with known content for deterministic testing. Tests run against real Presidio/spaCy — no mocked detection.
- Run specific test: `uv run pytest tests/path/to/test_file.py::test_function_name -v`
- Lint code: `uv run ruff check`
- Lint with autofix and sorting: `uv run ruff check --select I --fix`
- Format check: `uv run ruff format --check`
- Format with autofix: `uv run ruff format`
- Type check: `uv run ty check`
- Run piim: `uv run piim document.pdf`

## Code Style Guidelines
- Python 3.9+ compatible code
- Type hints are required for all functions and methods
- Classes: PascalCase with descriptive names
- Functions/Variables: snake_case
- Constants: UPPERCASE_WITH_UNDERSCORES
- Imports organization with Ruff
- Error handling: Use specific exception types
- Logging: Use the logging module with appropriate levels
- Use dataclasses for structured data when applicable

## Project Conventions
- Use uv for dependency management
- Add tests for all new functionality
- Maintain >80% test coverage
- Follow pre-commit hooks guidelines
- Document public APIs with docstrings

## Architecture

Read @docs/agent_docs/architecture.md for project architecture.
