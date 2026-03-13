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
