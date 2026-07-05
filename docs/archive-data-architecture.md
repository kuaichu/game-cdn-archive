# Archive Data Architecture

This document records the current static-data architecture after the WuWa split
work and the first validation-tool ports. It is meant to answer two practical
questions before future changes:

- Which games already use separated data and explicit validators?
- Which games still use older aggregate formats that need extra caution?

## Current Status

| Area | Current data shape | Validation/promote status | Notes |
| --- | --- | --- | --- |
| WuWa / 鸣潮 PC | Split: compact `index.json`, per-version shards, generated lists | Has split validator, staging import, batch promotion, release-date updater | Most mature separated model. |
| Endfield / 终末地 PC | Semi-split: compact `index.json`, aggregate `versions.json`, generated lists | Has validator and staging promotion tool | Validated, but version payload is still aggregate. |
| Arknights / 明日方舟 PC | Semi-split: compact `index.json`, aggregate `versions.json`, generated lists | Has validator and staging promotion tool | Smallest pipeline; used as low-risk proof of the workflow. |
| NTE / 异环 PC | Legacy/generated catalog plus per-version URL lists | No dedicated staging/promote validator yet | Existing downloader/reslist tools are separate from the new validator pattern. |
| HoYo PC catalog | Aggregate per-game `*_versions.json`, plus chunk shards | No dedicated staging/promote validator yet | Chunk data is already separated, but package metadata remains aggregate. |
| Android APK archive | Aggregate `index.json`, per-version list files | No dedicated staging/promote validator yet | Covers many games in one data set; should be split by game/source before major changes. |
| URL health index | Aggregate `url_status.json` | Probe script only | Cross-cutting health metadata, not a game archive source. |

## Shared Static-Site Loading Model

The frontend starts by reading compact top-level indexes:

```text
docs/data/catalog.json
docs/data/hoyo/games.json
docs/data/endfield/index.json
docs/data/endfield/versions.json
docs/data/wuwa/index.json
docs/data/arknights/index.json
docs/data/arknights/versions.json
docs/data/android/index.json
```

This means `index.json` files are part of the first page load path. Large file
trees should not be moved back into those startup payloads.

The preferred direction is:

```text
compact index -> selected version metadata -> selected file/download list
```

WuWa follows this most closely today.

## WuWa PC

WuWa is the separated reference architecture.

```text
docs/data/wuwa/
  index.json
  versions/
    3.4.1.json
    3.3.0.json
    ...
  lists/
    3.4.1-files.json
    3.4.1-files.urls.txt
    3.4.1-files.aria2.txt
    ...
```

The current WuWa archive has `41` versions:

- `10` self-collected or recovered official resource indexes
- `31` TomyJan imported historical versions

Important scripts:

- `scripts/sync_wuwa.py`
- `scripts/import_tomyjan_wuwa.py`
- `scripts/merge_tomyjan_wuwa_staging.py`
- `scripts/update_wuwa_release_dates.py`
- `scripts/validate_wuwa_split.py`

Important architecture points:

- `index.json` is a summary only. It drives the version list and startup view.
- `versions/{version}.json` is the full per-version metadata record.
- `lists/*` contains browser/download helper lists.
- `source` separates `self-collected` from `tomyjan-import`.
- `sync_wuwa.py` preserves imported TomyJan shards instead of rebuilding the
  data set from only the current launcher.
- `release_date` is separate from `last_modified`.
- `last_modified` means an HTTP `Last-Modified` header from an official CDN
  resource.
- TomyJan `release_date` values are archival timestamps from git history, not
  official announcement dates.

Validation expectations:

```bash
python scripts/validate_wuwa_split.py
node --check docs/app.js
```

Also verify locally that every game entry still renders.

## Endfield PC

Endfield is validated but not fully split into per-version shards.

```text
docs/data/endfield/
  index.json
  versions.json
  manual_versions.json
  lists/
    1.3.3_packages.urls.txt
    1.3.3_packages.aria2.txt
    1.3.3_patches.urls.txt
    1.3.3_patches.aria2.txt
```

The current archive has `7` versions.

Important scripts:

- `scripts/import_endfield_archive.py`
- `scripts/validate_endfield_archive.py`
- `scripts/promote_endfield_staging.py`

Important architecture points:

- Source data comes from `daydreamer-json/ak-endfield-api-archive`.
- `manual_versions.json` preserves historical manual records such as `0.5.27`.
- Official signed URLs may expire.
- Archive mirror URLs are preserved separately and often become the preferred
  download URL.
- `versions.json` is still an aggregate payload loaded at startup.

Current status:

- Has staging-aware output paths.
- Has a validator.
- Has a promote tool.
- Still uses aggregate `versions.json`; future split work should be separate
  from validation-tool work.

Validation expectations:

```bash
python scripts/validate_endfield_archive.py
node --check docs/app.js
```

## Arknights PC

Arknights PC is the smallest validated pipeline.

```text
docs/data/arknights/
  index.json
  versions.json
  lists/
    74.0.0_packages.json
    74.0.0_packages.urls.txt
    74.0.0_packages.aria2.txt
```

The current archive has `1` version.

Important scripts:

- `scripts/sync_arknights_pc.py`
- `scripts/validate_arknights_pc.py`
- `scripts/promote_arknights_pc_staging.py`

Important architecture points:

- Source data comes from Hypergryph launcher `get_latest`.
- `versions.json` is aggregate, but small.
- The validator checks index/version consistency, package counts, sizes,
  required package fields, and generated list links.
- The sync script can write to staging with `--output`.

Current status:

- Has staging-aware output.
- Has a validator.
- Has a promote tool.
- Still aggregate, but low-risk because the data volume is small.

Validation expectations:

```bash
python scripts/validate_arknights_pc.py
node --check docs/app.js
```

## NTE PC

NTE still uses the older catalog/list model.

```text
docs/data/
  catalog.json
  url_lists/
    1.2.11-full.json
    1.2.11-full.urls.txt
    1.2.11-full.files.aria2.txt
    1.2.11-patches.json
    ...
```

The current catalog has `74` probed entries, with `40` available versions.

Important scripts:

- `scripts/archive_reslist_versions.py`
- `scripts/build_urls_from_reslist.py`
- `scripts/probe_reslists.py`
- `scripts/update_nte_static.py`
- `scripts/nte_downloader.py`

Important architecture points:

- `catalog.json` is loaded at startup.
- Per-version full and patch lists already live outside the catalog.
- The current tooling is based on ResList probing/decoding rather than the new
  staging/promote validator pattern.

Current status:

- Partially separated because URL lists are external.
- Does not yet have a dedicated structural validator like WuWa/Endfield/AK.
- Any future refactor should first add a validator before changing format.

## HoYo PC Catalog

HoYo uses aggregate per-game metadata plus chunk shards.

```text
docs/data/hoyo/
  games.json
  hk4e_versions.json
  hkrpg_versions.json
  nap_versions.json
  bh3_versions.json
  chunk/
    hk4e_6.7.0.json
    hkrpg_4.3.0.json
    nap_3.0.0.json
    bh3_8.9.0.json
    ...
```

Current version counts:

- Genshin / `hk4e`: `55`
- Star Rail / `hkrpg`: `28`
- ZZZ / `nap`: `19`
- Honkai Impact 3 / `bh3`: `53`

Important script:

- `scripts/sync_hoyofiles.py`

Important architecture points:

- `games.json` is the compact game/version summary.
- Per-game `*_versions.json` files are aggregate payloads.
- Chunk metadata is already separated into `chunk/{game}_{version}.json`.
- The frontend can also query the HoyoFiles file-list API on demand.

Current status:

- Partly separated due to chunk shards.
- No structural validator/promote pipeline yet.
- Future work should be per game, not all HoYo games at once.
- A safe first target would be one game, one validator, no format migration.

## Android APK Archive

Android is a cross-game archive, not a single-game PC pipeline.

```text
docs/data/android/
  index.json
  lists/
    hk4e_6.7.0_android.json
    hk4e_6.7.0_android.urls.txt
    hk4e_6.7.0_android.aria2.txt
    ...
```

The current Android archive covers `15` games and `219` records.

Important script:

- `scripts/sync_android_apks.py`

Important architecture points:

- `index.json` is aggregate and includes all Android games.
- Per-version download helper lists are separated.
- The sync combines manual seeds, official latest endpoints, redirect
  discovery, JSON endpoint discovery, and webpage scraping.
- WuWa Android also includes selected TomyJan `WW/Android/Game/CN` archive
  seeds for missing version buckets.
- Existing records are re-probed and preserved even when old URLs expire.

Current status:

- Partly separated due to per-version list files.
- No dedicated validator/promote pipeline yet.
- Because it spans many games, future changes should be scoped to one game or
  one discovery source at a time.

## URL Health Index

`docs/data/url_status.json` is produced by:

```bash
python scripts/probe_url_status.py
```

It is not the source of game metadata. It is a cross-cutting health index for
archived URLs across APKs, HoYo packages, NTE files, WuWa files, Arknights
packages, and Endfield packages/patches.

Treat URL health changes as probe-output changes, not as archive-structure
changes.

## Workflow Rules For Future Changes

Use this sequence for any data-architecture work:

1. Change one game or one source at a time.
2. Generate to staging or a temporary output first.
3. Validate staging before touching formal data.
4. Promote explicitly.
5. Run all relevant validators.
6. Run `node --check docs/app.js`.
7. Start a local static server and verify all game entries render.
8. Confirm Android / Arknights / WuWa / Hoyo / Endfield are present.
9. Inspect the diff for unrelated files or unexpected deletions.
10. Commit the single step.
11. Push and verify online only after local checks pass.

Minimum checks after any frontend or data-shape change:

```bash
node --check docs/app.js
python scripts/validate_wuwa_split.py
python scripts/validate_endfield_archive.py
python scripts/validate_arknights_pc.py
```

For games without validators yet, perform a local page check and inspect the
generated JSON manually before committing.
