"""Persona 5: The Phantom X ResList and object availability interpretation."""

from __future__ import annotations

from adapters.nte import NteAvailabilityAdapter


class P5xAvailabilityAdapter(NteAvailabilityAdapter):
    game = "p5x"
