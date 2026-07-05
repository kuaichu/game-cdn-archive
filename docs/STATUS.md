# Project Status

Status levels:

- `done`: implemented and verified.
- `partial`: implemented in part, but not fully migrated or verified.
- `stubbed`: placeholder exists and must not be treated as production-ready.
- `todo`: not started.

## URL Availability Rewrite

| Area | Status | Notes |
| --- | --- | --- |
| Shared `ProbeResult` / `Interpretation` schema | partial | Implemented in `scripts/availability_schema.py`; first consumer is Arknights. |
| Stateless URL probe primitive | partial | Implemented in `scripts/url_probe.py`; used by Arknights availability build only. |
| Probe scheduler/cache layer | partial | Implemented in `scripts/probe_scheduler.py`; URL-granular TTL and reuse path exists for first consumer. |
| Arknights adapter | done | `adapters/arknights.py` interprets probe facts only and does not perform HTTP. Verified by `scripts/validate_availability.py`. |
| Arknights baked availability data | done | Package records in `docs/data/arknights/versions.json` carry precomputed availability while old fields remain. |
| Availability negative-path checks | done | `scripts/test_availability_negative.py` verifies Arknights failed probes and validator closed-vocabulary rejection. |
| Android adapter | todo | Recommended next slice. |
| Android baked availability data | todo | Not started. |
| Android frontend compatibility | todo | Not started. |
| Android fake-200 APK handling | todo | Not started. |
| HoYo adapter | todo | Recommended after Android. |
| Endfield adapter | todo | Needs official-vs-mirror interpretation. |
| NTE adapter | todo | Needs ResList/object interpretation. |
| WuWa multi-CDN adapter | todo | Defer until multi-CDN candidate selection is designed explicitly. |
