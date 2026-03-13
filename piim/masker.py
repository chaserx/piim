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
