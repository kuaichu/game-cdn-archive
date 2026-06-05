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
| Wuthering Waves / 鸣潮 | Windows PC | Official launcher resource index and CDN mirrors indexed |
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
    wuwa/
      index.json            Current launcher/resource-index summary
      versions.json         File URLs, MD5 values, CDN mirrors, and patch routes
      lists/                URL, aria2, and JSON file lists
scripts/
  archive_reslist_versions.py
                             Fetch, decode, and index versioned ResList archives
  build_urls_from_reslist.py
                             Build URL/aria2 indexes from decoded ResList XML
  decode_patcherxml0.py     Decode protected PatcherXML0 XML files
  nte_downloader.py         Prepare, download, verify, and pack client files
  import_endfield_archive.py
                             Import compact Endfield indexes from the upstream archive
  sync_wuwa.py               Sync Wuthering Waves launcher and resource indexes
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

## Genshin CDN Evolution

The Genshin Impact CN PC distribution history exposes several distinct official
CDN architectures. The site detects these states from actual package,
`decompressed_path`, and Chunk metadata rather than relying only on version
number ranges.

| Stage | Observed versions | Typical path | Distribution characteristics |
| --- | --- | --- | --- |
| Packed client | 1.0 - 1.3 | `client_app/pc_mihoyo/{build}/YuanShen_x.x.x.zip` | Primarily complete ZIP packages; no stable expanded-file root was observed |
| Experimental direct files | 1.4 | `client_app/pc_test/{build}/1.4.0cnrel/{path}` | Expanded files appeared under a separate `pc_test` build |
| Direct-file gap | 1.5 | No confirmed expanded-file root | Package distribution remained, while the experimental direct-file path disappeared |
| Official file-tree dual distribution | 1.6 - 2.2 | `client_app/pc_mihoyo/{build}/{version}/{path}` | Complete packages and an expanded official file tree coexisted |
| ScatteredFiles dual distribution | 2.3 - 4.1 | `client_app/download/pc_zip/{release_id}/ScatteredFiles/{path}` | Packages and expanded files shared a normalized release directory |
| Three-track distribution | 4.2 - 5.5 | Packages + `ScatteredFiles` + Chunk Manifest | Complete packages, direct files, and Chunk downloads coexisted |
| Chunk-only distribution | 5.6 onward | Manifest files and content-addressed chunks | Traditional packages and expanded-file roots disappeared from the public version metadata |

Representative direct-file URLs for the root `YuanShen.exe`:

```text
1.4.0
https://autopatchcn.yuanshen.com/client_app/pc_test/20210331_f0cd161954d6ed7e/1.4.0cnrel/YuanShen.exe

2.2.0
https://autopatchcn.yuanshen.com/client_app/pc_mihoyo/20211013_a336065295309dbe/2.2.0/YuanShen.exe

2.3.0
https://autopatchcn.yuanshen.com/client_app/download/pc_zip/20211117173857_8JkfDHNPmqKi67qR/ScatteredFiles/YuanShen.exe
```

Chunk metadata is present from version `4.2.0`. Version `5.6.0` is the observed
transition point where public package and `decompressed_path` metadata stopped,
leaving Chunk Manifest distribution as the only indexed full-file source.

## Star Rail CDN Pattern

Honkai: Star Rail CN PC distribution is more regular than Genshin Impact. Early
versions used complete ZIP packages. Version `1.4.0` exposes a root-level ZIP
and a root-level `unzip` tree. Version `1.5.0` moves both the package and
expanded file tree under `PC/`. From that point onward, the same release build
usually exposes both package files and an expanded `PC/unzip` file tree. Later
package format changes did not remove this direct-file root.

| Stage | Observed versions | Package path | Expanded file path |
| --- | --- | --- | --- |
| Packed client | 1.0.x - 1.3.x | `client/cn/{build}/StarRail_x.x.x.zip` | No stable `unzip` root observed in current metadata |
| Root ZIP + unzip | 1.4 | `client/cn/{build}/StarRail_1.4.0.zip` | `client/cn/{build}/unzip/{path}` |
| PC ZIP + unzip | 1.5 - 2.x | `client/cn/{build}/PC/StarRail_x.x.x.zip` | `client/cn/{build}/PC/unzip/{path}` |
| 7z volumes + unzip | 3.0 onward | `client/cn/{build}/PC/download/StarRail_x.x.x.7z.001` | `client/cn/{build}/PC/unzip/{path}` |
| Three-track distribution | 3.3 onward | 7z volumes + `unzip` + Chunk Manifest | Chunk metadata appears while package and unzip routes remain available |

Representative direct-file URLs for the root `StarRail.exe`:

```text
1.4.0
https://autopatchcn.bhsr.com/client/cn/20230926141222_ZKWHBONxYlx8PGYQ/unzip/StarRail.exe

2.0.0
https://autopatchcn.bhsr.com/client/cn/20240126110214_QvLzGdvYfGBEq4M4/PC/unzip/StarRail.exe

4.3.0
https://autopatchcn.bhsr.com/client/cn/20260523104353_kjwMxQcpFWHse2S2/PC/unzip/StarRail.exe
```

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

Official historical download URLs use signed parameters. Their actual
availability can change over time, and the upstream archive's `origStatus`
field only represents a past probe result. When that result is unavailable,
the UI labels the official link as status unknown, separately exposes its
public archive mirror, and uses the mirror in generated URL/aria2 lists. This
repository only indexes those external URLs and does not host game files.

The Endfield navigation icon is sourced from
[`Yue-plus/endfield_icons`](https://github.com/Yue-plus/endfield_icons) under
the MIT License.

## Wuthering Waves Sync

The Wuthering Waves view is generated from the launcher discovery metadata
documented by [`yuhkix/wuwa-downloader`](https://github.com/yuhkix/wuwa-downloader).
The sync script follows the CN live launcher index, reads the official resource
index, and preserves each file's official CDN URLs, size, and MD5:

```bash
python scripts/sync_wuwa.py
```

The generated file list includes all CDN mirrors exposed by the launcher. The
site uses the first CDN as `CDN1` and exposes the remaining mirrors as alternate
download buttons. Patch routes are shown as launcher-provided update index
entries; they are indexed for research and are not repackaged by this
repository.

## Automated Updates

The repository includes a GitHub Actions workflow at
`.github/workflows/update-data.yml`.

It can run manually from the Actions tab, and also runs once per day. The job:

1. Probes the current NTE launcher config and refreshes versioned ResList
   indexes up to the current official version.
2. Syncs HoYo game package and chunk indexes from the public HoyoFiles API.
3. Clones `daydreamer-json/ak-endfield-api-archive` and regenerates the
   compact Endfield indexes.
4. Refreshes Wuthering Waves launcher/resource-index data.
5. Commits and pushes only when generated data actually changes.
6. Deploys to Cloudflare Pages when a repository secret named
   `CLOUDFLARE_API_TOKEN` is available.

The separate `.github/workflows/deploy-pages.yml` workflow deploys the static
site on every push to `main` and can also be run manually.

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
