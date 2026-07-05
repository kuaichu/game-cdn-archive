"""Shared game availability adapter protocol."""

from __future__ import annotations

from typing import Protocol

from scripts.availability_schema import Interpretation, ProbeResult


class GameAvailabilityAdapter(Protocol):
    game: str

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        ...
