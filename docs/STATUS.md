# Project Status

Status levels:

- `done`: implemented and verified.
- `partial`: implemented in part, but not fully migrated or verified.
- `stubbed`: placeholder exists and must not be treated as production-ready.
- `todo`: not started.

## URL Availability Rewrite

| Area | Status | Notes |
| --- | --- | --- |
| Shared `ProbeResult` / `Interpretation` schema | partial | Implemented in `scripts/availability_schema.py`; first consumers are Arknights, Android, and HoYo. |
| Stateless URL probe primitive | partial | Implemented in `scripts/url_probe.py`; used by Arknights and Android availability builds; HoYo uses the same schema with metadata inference and no live probe. |
| Probe scheduler/cache layer | partial | Implemented in `scripts/probe_scheduler.py`; URL-granular TTL and reuse path exists for migrated consumers. |
| Arknights adapter | done | `adapters/arknights.py` interprets probe facts only and does not perform HTTP. Verified by `scripts/validate_availability.py`. |
| Arknights baked availability data | done | Package records in `docs/data/arknights/versions.json` carry precomputed availability while old fields remain. |
| Availability negative-path checks | done | `scripts/test_availability_negative.py` verifies Arknights and Android failed probes, Android retained historical records, and validator closed-vocabulary rejection. |
| Android adapter | done | `adapters/android.py` interprets shared probe facts only. APK size/content-type rules and retained historical dead links are verified by negative tests. |
| Android baked availability data | done | APK records in `docs/data/android/index.json` carry precomputed availability while old fields remain. |
| Android frontend compatibility | done | Android mode reads `availability.interpretation` first and falls back to legacy `status` / `error` fields. |
| Android fake-200 APK handling | done | APK URLs returning tiny text/XML/HTML placeholder payloads are tightened to `unavailable` instead of `unknown`. |
| HoYo adapter | done | `adapters/hoyo.py` interprets package/update size metadata only, using `metadata_inference` and non-high confidence. Version shard items and `games.json` summaries carry precomputed availability while old `unavailable_items` remains. |
| Endfield adapter | done | `adapters/endfield.py` interprets upstream archive `official_available` / mirror metadata only, using `upstream_archive` and non-high confidence. Index summaries, package records, and patch parts carry precomputed availability while old fields remain. |
| NTE adapter | done | `adapters/nte.py` interprets ResList entry status as `live_probe` and parsed object records as `metadata_inference`. Catalog versions and URL-list shards carry precomputed availability while old fields remain. |
| Tower of Fantasy adapter | done | `adapters/tof.py` reuses the PatcherSDK ResList interpretation pattern. ResList archive fetches are `live_probe`; decoded full/patch object URLs are `metadata_inference`. |
| WuWa multi-CDN adapter | done | Structural metadata availability and live multi-CDN probing are done for primary `url` + `urls` candidates. Full-version live probe facts are baked from the persistent build-time cache while old fields remain. |
