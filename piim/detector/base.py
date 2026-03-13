"""Abstract base class for PII detectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

import fitz

from piim.models import PiiEntity, TextBlock


class PiiDetector(ABC):
    """Interface for PII detection implementations."""

    @abstractmethod
    def detect(
        self, text_blocks: list[TextBlock], doc: fitz.Document | None = None
    ) -> list[PiiEntity]:
        """Detect PII entities in the given text blocks.

        Args:
            text_blocks: Text blocks extracted from a PDF document.
            doc: Optional PyMuPDF document for precise bbox refinement
                 via page.search_for().

        Returns:
            List of detected PII entities with their bounding boxes.
        """
        ...
