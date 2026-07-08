"""Tower of Fantasy ResList and object availability interpretation."""

from __future__ import annotations

from adapters.nte import NteAvailabilityAdapter


class TofAvailabilityAdapter(NteAvailabilityAdapter):
    game = "tof"
