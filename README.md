# Game CDN Archive

Unofficial index of official game CDN manifests, file URLs, checksums, and
download helper scripts.

This project is built for digital preservation, version research, and technical
reproduction. It does not mirror, repackage, or redistribute game binaries.

## Current Coverage

| Game | Platform | Status |
| --- | --- | --- |
| Neverness to Everness / 异环 | Windows PC | Version manifests decoded and indexed |
| Arknights: Endfield / 明日方舟：终末地 | Windows PC | Official launcher API history and archive mirrors indexed |
| Genshin Impact / 原神 | Windows PC | HoyoFiles version metadata migrated |
| Honkai: Star Rail / 崩坏：星穹铁道 | Windows PC | HoyoFiles version metadata migrated |
| Zenless Zone Zero / 绝区零 | Windows PC | HoyoFiles version metadata migrated |
| Honkai Impact 3 / 崩坏3 | Windows PC | HoyoFiles version metadata migrated |

More games can be added later as long as their official launcher manifests or
CDN metadata can be reproduced.

## Static Site

The static UI lives in `docs/` and is ready for GitHub Pages or Cloudflare
Pages.

Run it locally:

```bash
python -m http.server 8765
```

Then open:

```text
http://127.0.0.1:8765/docs/
```

Deploy with Wrangler:

```bash
npx wrangler pages deploy docs --project-name game-cdn-archive --branch main
```

## Repository Layout

```text
docs/
  index.html                Static file-index UI
  app.js
  styles.css
  data/
    catalog.json            Version summary used by the static UI
    url_lists/              Per-version URL, aria2, and JSON indexes
    hoyo/
      games.json            Migrated HoyoFiles game/version summary
      *_versions.json       Per-game package/update/chunk metadata
      chunk/                Per-version Chunk manifest summaries
    endfield/
      index.json            Compact game/version summary
      versions.json         Official URLs, checksums, status, and mirror URLs
      lists/                Preferred URL and aria2 download lists
scripts/
  archive_reslist_versions.py
                             Fetch, decode, and index versioned ResList archives
  build_urls_from_reslist.py
                             Build URL/aria2 indexes from decoded ResList XML
  decode_patcherxml0.py     Decode protected PatcherXML0 XML files
  nte_downloader.py         Prepare, download, verify, and pack client files
  import_endfield_archive.py
                             Import compact Endfield indexes from the upstream archive
```

## NTE Manifest Notes

The current public launcher uses packed resource lists. They are stored as
`ResList.bin.zip` and contain protected `ResList.bin` and `lastdiff.bin` files.

The protection layer has been identified as:

```text
PatcherXML0 header
AES-128-CBC decrypt
zlib inflate
```

For app `1289`, the observed key seed is `1289@Patcher`; the IV seed is
`PatcherSDK`. Both are padded to 16 bytes with ASCII `0`.

Versioned ResList entry:

```text
https://yhcdn1.wmupd.com/clientRes/publish_PC/Version/Windows/version/{version}/ResList.bin.zip
```

Observed available versions include `1.0.0`, `1.0.1`, `1.0.3`, `1.0.5` through
`1.0.9`, `1.0.11`, `1.0.13` through `1.0.15`, and `1.1.0` through `1.1.5`.

## HoyoFiles Migration

The HoYo game data shown in the static UI is migrated from public HoyoFiles
metadata:

```text
https://hoyo-files.amarea.cn
https://autopatch.amarea.cn/pkg_version
```

The migrated data includes version lists, direct package/update URLs, checksums,
sizes, decompressed-path capability flags, and Chunk manifest summaries. It does
not mirror game files or expanded chunk contents.

## Endfield Archive Import

The Endfield view is generated from the public
[`daydreamer-json/ak-endfield-api-archive`](https://github.com/daydreamer-json/ak-endfield-api-archive)
history for the CN official channel:

```bash
python scripts/import_endfield_archive.py path/to/ak-endfield-api-archive
```

Official historical download URLs use expiring signatures. When the upstream
archive records an official URL as unavailable, the UI separately exposes its
public archive mirror and uses that mirror in generated URL/aria2 lists. This
repository only indexes those external URLs and does not host game files.

The Endfield navigation icon is sourced from
[`Yue-plus/endfield_icons`](https://github.com/Yue-plus/endfield_icons) under
the MIT License.

## Downloader

Install dependency:

```bash
pip install -r requirements.txt
```

Probe available versioned resource lists:

```bash
python scripts/nte_downloader.py list --start 1.0.0 --end 1.1.5 --out outputs/nte_versions.json
```

Generate file indexes without downloading the full client:

```bash
python scripts/nte_downloader.py prepare 1.1.5 --work-dir outputs/nte_downloader
```

Download a full version:

```bash
python scripts/nte_downloader.py download 1.1.5 --download-root downloads --workers 4
```

Download and then pack it:

```bash
python scripts/nte_downloader.py download 1.1.5 --download-root downloads --workers 4 --pack --pack-dir packages
```

Pack an already downloaded version:

```bash
python scripts/nte_downloader.py pack 1.1.5 --download-root downloads --output-dir packages
```

## Disclaimer

This project is an unofficial digital preservation index. URLs point to official
distribution infrastructure or clearly labeled public archive mirrors. No game
binaries are redistributed from this repository.
