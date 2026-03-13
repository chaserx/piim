"""Tests for the Presidio PII detector."""

from piim.detector.presidio import PresidioDetector
from piim.models import TextBlock


class TestPresidioDetector:
    def setup_method(self):
        self.detector = PresidioDetector()

    def test_detects_person_name(self):
        blocks = [
            TextBlock(
                text="Contact John Smith for details",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        person_entities = [e for e in entities if e.entity_type == "PERSON"]
        assert len(person_entities) >= 1
        assert any("John Smith" in e.text for e in person_entities)

    def test_detects_email(self):
        blocks = [
            TextBlock(
                text="Email: john@example.com",
                bbox=(72.0, 100.0, 300.0, 114.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        email_entities = [e for e in entities if e.entity_type == "EMAIL_ADDRESS"]
        assert len(email_entities) == 1
        assert "john@example.com" in email_entities[0].text

    def test_detects_phone_number(self):
        blocks = [
            TextBlock(
                text="Phone: 555-123-4567",
                bbox=(72.0, 128.0, 300.0, 142.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        phone_entities = [e for e in entities if e.entity_type == "PHONE_NUMBER"]
        assert len(phone_entities) >= 1

    def test_detects_credit_card(self):
        blocks = [
            TextBlock(
                text="Card: 4111 1111 1111 1111",
                bbox=(72.0, 156.0, 300.0, 170.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        cc_entities = [e for e in entities if e.entity_type == "CREDIT_CARD"]
        assert len(cc_entities) >= 1

    def test_returns_empty_for_no_pii(self):
        blocks = [
            TextBlock(
                text="The weather is sunny today",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        assert len(entities) == 0

    def test_respects_min_confidence(self):
        blocks = [
            TextBlock(
                text="Email: john@example.com",
                bbox=(72.0, 100.0, 300.0, 114.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        # High threshold should filter out lower-confidence detections
        detector = PresidioDetector(min_confidence=0.99)
        entities = detector.detect(blocks)
        # Email patterns are typically very high confidence, so may still pass
        for e in entities:
            assert e.score >= 0.99

    def test_handles_multiple_pages(self):
        blocks = [
            TextBlock(
                text="Email: page0@example.com",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
            TextBlock(
                text="Email: page1@example.com",
                bbox=(72.0, 72.0, 300.0, 86.0),
                page_number=1,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        pages = {e.page_number for e in entities}
        assert 0 in pages
        assert 1 in pages

    def test_entity_has_bboxes(self):
        blocks = [
            TextBlock(
                text="Contact john@example.com today",
                bbox=(72.0, 100.0, 350.0, 114.0),
                page_number=0,
                source="native",
                confidence=1.0,
            ),
        ]
        entities = self.detector.detect(blocks)
        for entity in entities:
            assert len(entity.bboxes) >= 1
            for bbox in entity.bboxes:
                assert len(bbox) == 4
