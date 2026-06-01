from __future__ import annotations

from datetime import date
from typing import Protocol

from ..models import AdapterResult, CalendarConfig


class SourceAdapter(Protocol):
    name: str

    def fetch(self, config: CalendarConfig, today: date | None = None) -> AdapterResult | None:
        """Fetch and normalize source data into standard bond events."""

