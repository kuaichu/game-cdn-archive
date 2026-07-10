# AI Onboarding Guide

This repository is an unofficial static archive of official game CDN metadata.
It indexes launcher manifests, package URLs, file URLs, checksums, mirrors, and
download helper lists. It does not host or redistribute game binaries.

This file is the first document a new AI agent should read before changing the
project.

## First Read Order

Read these files in order. Do not infer the current architecture from old chat
state.

1. `README.md`
   - Project purpose, coverage, automation, repository layout, and common
     commands.
2. `docs/archive-data-architecture.md`
   - Current per-game data shapes, split status, source scripts, validators,
     and risk notes.
3. `docs/url-availability-architecture.md`
   - Canonical URL availability contract, probe/adapters split, closed
     vocabulary, and source semantics.
4. `docs/STATUS.md`
   - Current migration status. Treat `partial`, `stubbed`, and `todo` as not
     production-complete.
5. `docs/wuwa-archive-architecture.md`
   - WuWa split architecture, TomyJan import, staging/promotion workflow, and
     common failure modes.
6. Relevant scripts and frontend branch for the one game you are touching.
   - Never work from memory. Read the current code and generated JSON first.

## Project Map

Static site:

```text
docs/
  index.html
  app.js
  styles.css
  data/
```

Generated data lives under `docs/data/` because Cloudflare Pages deploys
`docs/` directly. Do not put large offline audit files under `docs/`.

Temporary or offline build outputs belong under `outputs/`, which is gitignored.
The cross-cutting URL health audit is `outputs/url_status.json`; it is not a
frontend source of truth and must not be published.

## Game Data Matrix

| Area | Data path | Main scripts | Validator / build checks | Notes |
| --- | --- | --- | --- | --- |
| NTE / 异环 PC | `docs/data/catalog.json`, `docs/data/url_lists/` | `archive_reslist_versions.py`, `build_urls_from_reslist.py`, `update_nte_static.py`, `nte_downloader.py` | No dedicated staging validator yet; `validate_availability.py` covers migrated availability fields | Older catalog/list model. Legacy root `data/` captures were removed; use git history if the original 2026-06-04 NTE capture is needed. |
| NTE / 异环 Android resources | `docs/data/nte/android/catalog.json`, `docs/data/nte/android/url_lists/` | `update_nte_android_static.py`, `build_urls_from_reslist.py` | `validate_availability.py` | Post-install Android resources, not APK installers. Intentional NTE-only legacy sibling until NTE PC is migrated. |
| Tower of Fantasy / 幻塔 PC | `docs/data/tof/catalog.json`, `docs/data/tof/url_lists/` | `update_tof_static.py`, `build_urls_from_reslist.py` | `build_tof_availability.py`, `validate_availability.py` | PatcherSDK ResList family, separate from NTE; current key seed is `1256@Patcher`. |
| P5X / 女神异闻录：夜幕魅影 PC | `docs/data/p5x/catalog.json`, `docs/data/p5x/url_lists/` | `update_p5x_static.py`, `build_urls_from_reslist.py` | `build_p5x_availability.py`, `validate_availability.py` | PatcherSDK ResList family, same format as Tower of Fantasy; current key seed is `1264@Patcher`. |
| Endfield / 终末地 PC | `docs/data/endfield/index.json`, `versions.json`, `lists/` | `import_endfield_archive.py`, `promote_endfield_staging.py` | `validate_endfield_archive.py`, `build_endfield_availability.py` | Upstream archive + mirror metadata; still has aggregate `versions.json`. |
| Arknights / 明日方舟 PC | `docs/data/arknights/index.json`, `versions.json`, `lists/` | `sync_arknights_pc.py`, `promote_arknights_pc_staging.py` | `validate_arknights_pc.py`, `build_arknights_availability.py` | Smallest validated pipeline. |
| WuWa / 鸣潮 PC | `docs/data/wuwa/index.json`, `versions/`, `lists/` | `sync_wuwa.py`, `import_tomyjan_wuwa.py`, `merge_tomyjan_wuwa_staging.py`, `probe_wuwa_availability.py` | `validate_wuwa_split.py`, `build_wuwa_availability.py` | Reference split model; multi-CDN availability is precomputed, not frontend-probed. |
| HoYo PC | `docs/data/hoyo/games.json`, `versions/{game}/{version}.json`, `chunk/` | `sync_hoyofiles.py` | `validate_hoyo_split.py`, `build_hoyo_availability.py` | Split selected-version loading; availability is metadata inference. |
| Android APK archive | `docs/data/android/index.json`, `docs/data/android/lists/` | `sync_android_apks.py` | `build_android_availability.py`, `validate_availability.py` | Cross-game APK archive. Retains historical dead-link evidence. |
| Shared URL health audit | `outputs/url_status.json` | `probe_url_status.py` | `check_docs_file_sizes.py` prevents large published files | Offline audit only; not read by frontend. |

## URL Availability Model

The canonical availability model is:

```text
raw URL candidate(s)
  -> scripts/url_probe.py          # only layer allowed to do network probe I/O
  -> scripts/probe_scheduler.py    # TTL/cache/batching/force-full
  -> adapters/*.py                 # game-specific interpretation, no HTTP
  -> precomputed availability JSON
  -> docs/app.js                   # render display_label, do not decide facts
```

Hard rules:

- Only `scripts/url_probe.py` may perform canonical live URL probing.
- `adapters/` must not import or call `requests`, `urllib`, `subprocess`,
  `curl`, browser fetch APIs, or any other network path.
- Adapters consume facts and metadata only.
- `state` is machine semantics; `display_label` is human-facing text. Do not
  collapse them into one field.
- `source.kind`, `state`, `reason`, and `confidence` must stay inside the
  closed vocabulary defined by `scripts/availability_schema.py` and
  `docs/url-availability-architecture.md`.
- If data is stale, missing, or not probed, do not pretend it is fresh
  `live_probe`. Use the appropriate lower-confidence source.

Current migrated adapters:

```text
adapters/
  arknights.py
  android.py
  hoyo.py
  endfield.py
  nte.py
  p5x.py
  tof.py
  wuwa.py
```

## Frontend Boundaries

`docs/app.js` is one large static frontend file. Be careful with shared state
and shared render paths.

Before touching frontend code:

1. Find the game predicate, such as `isWuwa()`, `isAndroidOnly()`, `isHoyo()`,
   `isEndfield()`, `isArknights()`, or `isNte()`.
2. Keep game-specific behavior inside that branch.
3. Do not alter shared render/loading paths unless the task explicitly requires
   a cross-game change.
4. After any frontend change, verify that all 15 game entries still render.

The previous high-risk failure mode was changing one game's file browser or
availability path in a way that made other game entries disappear. Treat
all-game smoke testing as mandatory.

## Standard Validation Commands

For any code or data change:

```bash
node --check docs/app.js
python scripts/validate_availability.py
python scripts/check_docs_file_sizes.py
git diff --check
```

Add game-specific checks when relevant:

```bash
python scripts/validate_wuwa_split.py
python scripts/validate_arknights_pc.py
python scripts/validate_endfield_archive.py
python scripts/validate_hoyo_split.py
python scripts/test_availability_negative.py
```

For UI-impacting changes, run the static site locally:

```bash
python -m http.server 8765 -d docs
```

Then verify in a browser:

- 15 game entries render.
- Android / Arknights / WuWa / HoYo / Endfield / NTE are present.
- The touched game's version selector and file list still load.
- Console has no new errors.
- `favicon.ico` 404 is harmless.

## Automation And Deployment

Scheduled sync is defined in `.github/workflows/sync-archive.yml`.

Deploy is defined in `.github/workflows/deploy-pages.yml`.

Important automation rules:

- Cloudflare Pages deploys `docs/` directly.
- Any file under `docs/` larger than 20 MiB should fail the file-size guard.
- `outputs/` is ignored and must not be committed.
- `probe_url_status.py` writes `outputs/url_status.json`; do not move it back
  to `docs/data/`.
- If a sync workflow creates data changes, inspect the generated diff before
  assuming it is safe.

## Change Discipline

Use small commits. One feature or one game per commit.

Do not mix:

- shared infrastructure changes,
- game adapter migrations,
- frontend behavior changes,
- generated data rewrites,
- documentation-only updates.

Before a risky migration:

1. Read current scripts and JSON.
2. Write down the current behavior and source of truth.
3. Build the new path in parallel.
4. Preserve legacy fields as fallback until explicitly removed.
5. Compare old vs new semantics and list every intentional migration.
6. Run validators and browser smoke checks.

If a branch is unfinished, mark it honestly in `docs/STATUS.md` as `partial`,
`stubbed`, or `todo`. Do not label unverified work as `done`.

## New AI Handoff Procedure

When a new AI session starts, do this:

1. Run `git status --short --branch`.
2. Read this file, then the first-read documents listed above.
3. Identify the exact scope requested by the user.
4. Inspect the current code and data for that scope.
5. State the current behavior and the files likely affected.
6. If code/data changes are requested, make the smallest safe change.
7. Run the standard validation commands plus game-specific checks.
8. For frontend or data-loading changes, run the local site and browser smoke.
9. Summarize changed files, validation results, and any remaining risk.
10. Commit and push only when the user asked for it or the workflow requires it.

Do not trust old conversation context over the repository. The repository is
the source of truth.
