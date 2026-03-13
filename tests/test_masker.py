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
