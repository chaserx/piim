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
