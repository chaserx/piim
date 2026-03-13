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
    fake: object,
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
