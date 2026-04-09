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
            bboxes = self._refine_bboxes(entity_text_clean, parent_blocks, page)
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
        parent_cx = sum((b.bbox[0] + b.bbox[2]) / 2 for b in parent_blocks) / len(
            parent_blocks
        )
        parent_cy = sum((b.bbox[1] + b.bbox[3]) / 2 for b in parent_blocks) / len(
            parent_blocks
        )

        best = min(
            search_results,
            key=lambda r: math.hypot(
                (r.x0 + r.x1) / 2 - parent_cx,
                (r.y0 + r.y1) / 2 - parent_cy,
            ),
        )
        return [(best.x0, best.y0, best.x1, best.y1)]
