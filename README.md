# Game CDN Archive / 二游官方 CDN 索引

这是一个非官方的游戏 CDN 元数据归档项目，用来保存官方启动器清单、文件 URL、校验值、镜像 URL、APK 记录和下载辅助列表。

项目目标是数字保存、版本研究和技术复现。仓库只保存索引和元数据，不镜像、不重新打包、不分发任何游戏本体文件。

English summary: this repository is an unofficial index of official game CDN
manifests, file URLs, checksums, and download helper scripts. It does not host
or redistribute game binaries.

## 当前覆盖范围

<!-- README_VERSION_SUMMARY_START -->
<!-- 此区块由 scripts/update_readme_summary.py 生成，请勿手改。 -->

| 游戏 | 平台 | 状态 | 版本更新时间 |
| --- | --- | --- | --- |
| Neverness to Everness / 异环 | Windows PC | 已解码并索引到 `1.2.12`（可用 `41` 个 / 已探测 `75` 个） | `2026-07-07 05:00:01 北京时间` |
| Tower of Fantasy / 幻塔 | Windows PC | 官方 PatcherSDK ResList 已解码并索引到 `6.2.2`（`1` 个版本） | `2026-07-04 06:47:22 北京时间` |
| Arknights: Endfield / 明日方舟：终末地 | Windows PC | 官方启动器 API 历史与归档镜像已索引到 `1.3.3`（`7` 个版本） | `2026-06-05 06:15:27 北京时间` |
| Arknights / 明日方舟 | Windows PC | 官方启动器包元数据已索引到 `74.0.0`（`1` 个版本） | `未知` |
| Wuthering Waves / 鸣潮 | Windows PC | 官方启动器资源索引与 CDN 镜像已索引到 `3.4.1`（`41` 个版本） | `2026-06-16 17:38:52 北京时间` |
| Genshin Impact / 原神 | Windows PC | HoyoFiles 版本元数据已迁移到 `6.7.0`（`55` 个版本） | `2026-06-18 23:01:33 北京时间` |
| Honkai: Star Rail / 崩坏：星穹铁道 | Windows PC | HoyoFiles 版本元数据已迁移到 `4.3.0`（`28` 个版本） | `2026-05-23 15:56:03 北京时间` |
| Zenless Zone Zero / 绝区零 | Windows PC | HoyoFiles 版本元数据已迁移到 `3.0.0`（`19` 个版本） | `2026-05-29 12:15:38 北京时间` |
| Honkai Impact 3 / 崩坏3 | Windows PC | HoyoFiles 版本元数据已迁移到 `8.9.0`（`53` 个版本） | `2026-05-22 11:08:32 北京时间` |

_整个项目的数据刷新时间：`2026-07-08 14:44:28 北京时间`。_
<!-- README_VERSION_SUMMARY_END -->

## 当前进度快照

<!-- README_PROGRESS_SNAPSHOT_START -->
<!-- 此区块由 scripts/update_readme_summary.py 生成，请勿手改。 -->

当前仓库快照来自生成数据，检查时间：`2026-07-08 14:37:49 北京时间`。

| 范围 | 当前进度 |
| --- | --- |
| NTE / 异环 PC | 已索引官方 Windows 清单 `1.0.0` 到 `1.2.12`；`75` 个已探测条目中有 `41` 个可用版本 |
| Tower of Fantasy / 幻塔 PC | 已索引官方 Windows ResList `6.2.2` 到 `6.2.2`；最新清单包含 `91` 个完整文件与 `2047` 个补丁对象 |
| Endfield / 终末地 PC | 已导入 `7` 个 CN 启动器历史快照，最新 `1.3.3`；官方签名包 URL 与归档镜像 URL 均已保留 |
| Arknights / 明日方舟 PC | 官方启动器包元数据已索引到 `74.0.0`；最新快照包含 `19` 个包条目 |
| Wuthering Waves / 鸣潮 PC | 已索引 `41` 个 CN 启动器 / resource-index 快照，最新 `3.4.1`；官方索引暴露的文件 URL、CDN 镜像与补丁路由均已保留 |
| HoYo CN PC 目录 | 已迁移公开 HoyoFiles 元数据：原神 `1.0.0-6.7.0`（`55` 个版本），崩坏：星穹铁道 `1.0.5-4.3.0`（`28` 个版本），绝区零 `0.2.0-3.0.0`（`19` 个版本），崩坏3 `3.7.0-8.9.0`（`53` 个版本） |
| Android APK 归档 | 保留 `15` 个游戏的 `212` 条已确认或历史验证过的官方 APK CDN 记录 |
<!-- README_PROGRESS_SNAPSHOT_END -->

## Android APK 进度

Android 侧已经不只是“最新链接索引”。现在会保留历史渠道漂移和死链证据。当前已索引版本范围如下：

<!-- README_ANDROID_PROGRESS_START -->
<!-- 此区块由 scripts/update_readme_summary.py 生成，请勿手改。 -->

| 游戏 | 已索引版本 | 记录 | 备注 |
| --- | --- | --- | --- |
| 深空之眼 / Aether Gazer | `0.285.0` -> `0.305.3` | `4` 个版本桶 / `4` 条记录 | `2` 条可用；`2` 条不可用或历史死链记录 |
| 明日方舟 / Arknights | `1150.0.0` -> `2741.0.0` | `20` 个版本桶 / `20` 条记录 | `1` 条可用；`19` 条不可用或历史死链记录 |
| 崩坏3 / Honkai Impact 3rd | `0.9.9` -> `8.9.0` | `39` 个版本桶 / `39` 条记录 | `13` 条可用；`26` 条不可用或历史死链记录 |
| 碧蓝档案 / Blue Archive | `1.8.2` -> `2.1.2` | `3` 个版本桶 / `3` 条记录 | `1` 条可用；`2` 条不可用或历史死链记录 |
| 卡拉比丘 / Calabiyau | `1.1.6.4` | `1` 个版本桶 / `1` 条记录 | `0` 条可用；`1` 条不可用或历史死链记录 |
| 明日方舟：终末地 / Arknights: Endfield | `1.3.4` | `1` 个版本桶 / `1` 条记录 | `1` 条可用；`0` 条不可用或历史死链记录 |
| 少女前线2：追放 / Girls' Frontline 2: Exilium | `3.0.0` | `1` 个版本桶 / `1` 条记录 | `1` 条可用；`0` 条不可用或历史死链记录 |
| 原神 / Genshin Impact | `0.9.3` -> `6.7.0` | `54` 个版本桶 / `54` 条记录 | `44` 条可用；`10` 条不可用或历史死链记录 |
| 崩坏：星穹铁道 / Honkai: Star Rail | `0.90.0` -> `4.3.0` | `29` 个版本桶 / `33` 条记录 | `30` 条可用；`3` 条不可用或历史死链记录 |
| 绝区零 / Zenless Zone Zero | `1.0.0` -> `3.0.0` | `10` 个版本桶 / `10` 条记录 | `10` 条可用；`0` 条不可用或历史死链记录 |
| 异环 / Neverness to Everness | `1.0.2` -> `1.2.0` | `2` 个版本桶 / `2` 条记录 | `2` 条可用；`0` 条不可用或历史死链记录 |
| 战双帕弥什 / Punishing: Gray Raven | `4.5.0` | `1` 个版本桶 / `2` 条记录 | `2` 条可用；`0` 条不可用或历史死链记录 |
| 重返未来：1999 / Reverse: 1999 | `1.0.3` -> `3.8.0` | `2` 个版本桶 / `2` 条记录 | `1` 条可用；`1` 条不可用或历史死链记录 |
| 尘白禁区 / Snowbreak: Containment Zone | `1.6.0.99` -> `3.6.0.122` | `9` 个版本桶 / `9` 条记录 | `4` 条可用；`5` 条不可用或历史死链记录 |
| 鸣潮 / Wuthering Waves | `0.7.0` -> `3.4.1` | `31` 个版本桶 / `31` 条记录 | `24` 条可用；`7` 条不可用或历史死链记录 |
<!-- README_ANDROID_PROGRESS_END -->

后续只要能稳定复现官方启动器清单或 CDN 元数据，就可以继续扩展更多游戏。

## 静态站点

静态页面位于 `docs/`，可直接部署到 GitHub Pages 或 Cloudflare Pages。

本地运行：

```bash
python -m http.server 8765
```

然后打开：

```text
http://127.0.0.1:8765/docs/
```

使用 Wrangler 部署：

```bash
npx wrangler pages deploy docs --project-name game-cdn-archive --branch main
```

## 自动同步

定时同步目前每天运行两次：

- `07:18` Asia/Shanghai
- `12:18` Asia/Shanghai

配置以下仓库 secrets 后，GitHub Actions 还可以发送 Telegram 通知：

| Secret | 用途 |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | 发送通知用的 Bot token |
| `TELEGRAM_CHAT_ID` | 一个 chat ID，或用 `,` / `;` 分隔的多个 chat ID |

如果 Telegram 返回“旧群组已升级为 supergroup”，workflow 会自动用迁移后的 chat ID 重试，并在 Actions 日志里打印 warning，方便之后更新 secret。

网络较重的同步步骤和 Cloudflare 部署最多会自动重试 `3` 次。如果仍然失败，最终 Telegram 消息会包含失败步骤、退出码，以及从最后一次日志中提取的简短错误摘要。

## 仓库结构

```text
docs/
  index.html                静态文件索引页面
  app.js
  styles.css
  data/
    catalog.json            静态页面使用的版本摘要
    url_lists/              按版本生成的 URL / aria2 / JSON 索引
    tof/
      catalog.json          幻塔 PatcherSDK ResList 版本摘要
      url_lists/            幻塔按版本生成的 URL / aria2 / JSON 索引
    hoyo/
      games.json            从 HoyoFiles 迁移的游戏 / 版本摘要
      versions/             按游戏、按版本拆分的包和更新元数据
      chunk/                按版本拆分的 Chunk manifest 摘要
    endfield/
      index.json            精简游戏 / 版本摘要
      versions.json         官方 URL、校验值、状态和镜像 URL
      lists/                Preferred URL 和 aria2 列表
    wuwa/
      index.json            启动器 / resource-index 摘要
      versions/             按版本拆分的文件 URL、MD5、CDN 镜像和补丁路由
      lists/                URL / aria2 / JSON 文件列表
scripts/
  archive_reslist_versions.py
                             拉取、解码并索引版本化 ResList 归档
  build_urls_from_reslist.py
                             从解码后的 ResList XML 生成 URL / aria2 索引
  decode_patcherxml0.py     解码受保护的 PatcherXML0 XML 文件
  update_tof_static.py       刷新幻塔静态 ResList 索引
  nte_downloader.py         准备、下载、校验和打包客户端文件
  import_endfield_archive.py
                             从上游归档导入 Endfield 精简索引
  sync_wuwa.py               同步鸣潮启动器和资源索引
  sync_android_apks.py       刷新已知官方 Android APK URL 元数据
  probe_url_status.py        重新探测归档直链的可用性
```

各游戏当前数据结构、分片状态、校验和 promote 覆盖情况见 [`docs/archive-data-architecture.md`](docs/archive-data-architecture.md)。
新的 AI / 代码代理接手前请先读 [`AGENTS.md`](AGENTS.md)。

## NTE 清单说明

当前公开启动器使用打包资源列表。资源列表存储为 `ResList.bin.zip`，其中包含受保护的 `ResList.bin` 和 `lastdiff.bin` 文件。

已确认保护层为：

```text
PatcherXML0 header
AES-128-CBC decrypt
zlib inflate
```

对 app `1289`，观察到的 key seed 是 `1289@Patcher`，IV seed 是 `PatcherSDK`。两者都会用 ASCII `0` 补齐到 16 字节。

本项目的 PatcherXML0 解码流程为独立逆向复现。社区中也存在同类实现，例如 [`Tobiichi-Origuchi/nte_patcher`](https://github.com/Tobiichi-Origuchi/nte_patcher)；该实现使用不同的 appId 样本，但同样指向 `appId@Patcher` 这一 key seed 构造规律，可作为交叉验证参考。本项目的重点不是提供运行时下载器，而是将解码后的 ResList 用于历史版本归档、URL 索引、可用性记录和数字保存。

版本化 ResList 入口：

```text
https://yhcdn1.wmupd.com/clientRes/publish_PC/Version/Windows/version/{version}/ResList.bin.zip
```

已观察到的可用版本包括 `1.0.0`、`1.0.1`、`1.0.3`、`1.0.5` 到 `1.0.9`、`1.0.11`、`1.0.13` 到 `1.0.15`，以及 `1.1.0` 到 `1.1.5`。

## 幻塔清单说明

幻塔 Windows 客户端同样使用 PatcherSDK 风格的 `ResList.bin.zip`。当前观察到的版本入口为：

```text
https://htcdn1.wmupd.com/clientRes/Windows55/Version/Windows/version/{version}/ResList.bin.zip
```

当前样本 `6.2.2` 已确认与异环相同的保护层：

```text
PatcherXML0 header
AES-128-CBC decrypt
zlib inflate
```

幻塔当前观察到的 key seed 是 `1256@Patcher`，IV seed 仍是 `PatcherSDK`，两者同样用 ASCII `0` 补齐到 16 字节。解码后的对象 URL 形如：

```text
https://htcdn1.wmupd.com/clientRes/Windows55/Res/{首字符}/{md5}.{size}
```

## 原神 CDN 演进

原神 CN PC 分发历史里出现过几种不同的官方 CDN 架构。站点会根据真实 package、`decompressed_path` 和 Chunk 元数据判断分发状态，而不是只按版本号硬编码。

| 阶段 | 观察版本 | 典型路径 | 分发特征 |
| --- | --- | --- | --- |
| 打包客户端 | 1.0 - 1.3 | `client_app/pc_mihoyo/{build}/YuanShen_x.x.x.zip` | 主要是完整 ZIP 包，未观察到稳定展开文件根目录 |
| 实验性直链文件 | 1.4 | `client_app/pc_test/{build}/1.4.0cnrel/{path}` | 展开文件出现在单独的 `pc_test` build 下 |
| 直链空窗 | 1.5 | 未确认展开文件根目录 | 包分发仍在，但实验性直链路径消失 |
| 官方文件树双轨 | 1.6 - 2.2 | `client_app/pc_mihoyo/{build}/{version}/{path}` | 完整包和官方展开文件树并存 |
| ScatteredFiles 双轨 | 2.3 - 4.1 | `client_app/download/pc_zip/{release_id}/ScatteredFiles/{path}` | 包和展开文件共用规范化 release 目录 |
| 三轨分发 | 4.2 - 5.5 | Packages + `ScatteredFiles` + Chunk Manifest | 完整包、直链文件和 Chunk 下载并存 |
| Chunk-only | 5.6 起 | Manifest 文件和内容寻址 chunk | 公开版本元数据中不再出现传统包和展开文件根目录 |

根目录 `YuanShen.exe` 的代表性直链：

```text
1.4.0
https://autopatchcn.yuanshen.com/client_app/pc_test/20210331_f0cd161954d6ed7e/1.4.0cnrel/YuanShen.exe

2.2.0
https://autopatchcn.yuanshen.com/client_app/pc_mihoyo/20211013_a336065295309dbe/2.2.0/YuanShen.exe

2.3.0
https://autopatchcn.yuanshen.com/client_app/download/pc_zip/20211117173857_8JkfDHNPmqKi67qR/ScatteredFiles/YuanShen.exe
```

Chunk 元数据从 `4.2.0` 开始出现。`5.6.0` 是观察到的转折点：公开 package 和 `decompressed_path` 元数据停止出现，只剩 Chunk Manifest 作为已索引的完整文件来源。

## 星穹铁道 CDN 模式

崩坏：星穹铁道 CN PC 分发比原神更规整。早期版本使用完整 ZIP 包。`1.4.0` 同时暴露根目录 ZIP 和根目录 `unzip` 文件树。`1.5.0` 起，包和展开文件树都移动到 `PC/` 下。之后同一 release build 通常同时暴露包文件和 `PC/unzip` 展开文件树；后续包格式变化并没有移除这个直链根目录。

| 阶段 | 观察版本 | 包路径 | 展开文件路径 |
| --- | --- | --- | --- |
| 打包客户端 | 1.0.x - 1.3.x | `client/cn/{build}/StarRail_x.x.x.zip` | 当前元数据中未观察到稳定 `unzip` 根目录 |
| 根目录 ZIP + unzip | 1.4 | `client/cn/{build}/StarRail_1.4.0.zip` | `client/cn/{build}/unzip/{path}` |
| PC ZIP + unzip | 1.5 - 2.x | `client/cn/{build}/PC/StarRail_x.x.x.zip` | `client/cn/{build}/PC/unzip/{path}` |
| 7z 分卷 + unzip | 3.0 起 | `client/cn/{build}/PC/download/StarRail_x.x.x.7z.001` | `client/cn/{build}/PC/unzip/{path}` |
| 三轨分发 | 3.3 起 | 7z 分卷 + `unzip` + Chunk Manifest | Chunk 元数据出现，同时包和 unzip 路由仍可用 |

根目录 `StarRail.exe` 的代表性直链：

```text
1.4.0
https://autopatchcn.bhsr.com/client/cn/20230926141222_ZKWHBONxYlx8PGYQ/unzip/StarRail.exe

2.0.0
https://autopatchcn.bhsr.com/client/cn/20240126110214_QvLzGdvYfGBEq4M4/PC/unzip/StarRail.exe

4.3.0
https://autopatchcn.bhsr.com/client/cn/20260523104353_kjwMxQcpFWHse2S2/PC/unzip/StarRail.exe
```

## HoyoFiles 迁移

静态页面中的 HoYo 游戏数据迁移自公开 HoyoFiles 元数据：

```text
https://hoyo-files.amarea.cn
https://autopatch.amarea.cn/pkg_version
```

迁移后的数据包含版本列表、包 / 更新直链、校验值、大小、`decompressed_path` 能力标记和 Chunk manifest 摘要。仓库不镜像游戏文件，也不保存展开后的 chunk 内容。

## Endfield 归档导入

Endfield 页面生成自公开的
[`daydreamer-json/ak-endfield-api-archive`](https://github.com/daydreamer-json/ak-endfield-api-archive)
CN 官方频道历史记录：

```bash
python scripts/import_endfield_archive.py path/to/ak-endfield-api-archive
```

官方历史下载 URL 使用签名参数，实际可用性会随时间变化。上游归档的 `origStatus` 只代表当时的探测结果。当官方链接不可用时，页面会把官方链接标为状态未知，同时单独展示公开归档镜像，并在生成的 URL / aria2 列表中使用镜像。本仓库只索引这些外部 URL，不托管游戏文件。

Endfield 导航图标来自
[`Yue-plus/endfield_icons`](https://github.com/Yue-plus/endfield_icons) under
项目，遵循 MIT License。

## 鸣潮同步

鸣潮页面生成自 [`yuhkix/wuwa-downloader`](https://github.com/yuhkix/wuwa-downloader) 记录的启动器发现元数据。同步脚本会跟随当前 CN 正式服启动器索引，读取官方 resource index，并保留每个文件的官方 CDN URL、大小和 MD5：

```bash
python scripts/sync_wuwa.py
```

生成的文件列表包含启动器暴露的所有 CDN 镜像。站点把第一个 CDN 作为 `CDN1`，其余镜像作为备用下载按钮展示。补丁路由以启动器提供的 update index 条目形式展示；它们只用于研究索引，不会被本仓库重新打包。

部分历史 CN 正式服 resource index 在其版本专属官方 URL 可独立恢复和验证时也会被保留。目前已恢复集合包括 `2.3.1`、`2.6.2`、`2.8.0`、`3.2.2`，以及当前启动器版本。它们是完整 resource index，但不等于保证覆盖所有历史版本。

鸣潮导航图标来自 HK KURO GAMES LIMITED 发布的官方 App Store listing。

## Android APK 归档

Android APK 页面是增量归档。只有当官方 APK CDN URL 被捕获并验证后才会保留。定时同步也会解析已支持的官方下载入口，因此当 latest endpoint 指向新 APK 时可以自动加入：HoYo 游戏使用 Download Porter endpoint，Kuro 游戏使用官方 JSON 下载索引，NTE 读取官网 Android 下载配置，鹰角游戏跟随官方 latest-APK endpoint，并探测解析后的 CDN 目标以获取版本和文件元数据。同一个 package 首次解析到的 CDN URL 会作为归档记录保留，即使之后可能过期。

```bash
python scripts/sync_android_apks.py
```

生成的索引会记录 URL、文件名、渠道、HTTP 状态、大小、Last-Modified、ETag，以及 CDN 暴露的 MD5。已有条目会在每次同步时重新探测，因此过期的历史 APK URL 可以被标记为不可用，同时保留原始捕获时间。

当 APK URL 本身不包含版本号时，同步脚本会通过 HTTP range request 读取 APK 的 `AndroidManifest.xml` `versionName`，而不是从 PC 客户端版本猜测。

这不是完整历史 APK 镜像，而是一个从当前可确认官方 APK 链接开始滚动积累的归档。

归档直链也可以跨数据集重新探测。脚本会写入 `outputs/url_status.json`，这是不会发布的离线健康索引，覆盖 APK、HoYo 包、NTE 文件、鸣潮文件、明日方舟包和 Endfield 包 / 补丁。

```bash
python scripts/probe_url_status.py
```

URL 健康探测默认是增量式：新 URL 一定会探测，失败 URL 会周期性重试，旧的健康 URL 会分批轮换，避免每次例行同步都重探所有归档文件。设置 `URL_STATUS_FORCE_FULL=1` 可以立即强制全量扫描。Android APK 元数据也有类似的短 TTL：`ANDROID_APK_REPROBE_TTL_HOURS`；设为 `0` 可强制重新检查全部历史 APK。

### Kuro Android 兜底说明

当前鸣潮 Android 同步跟随 Kuro 公开 latest-download JSON 索引：

`https://download.kurogames.com/mc_.../official/cn/zh-Hans/android_app.json`

只要这个 JSON 路径保持稳定、只有内容变化，同步任务就能自动从一个 latest APK 滚动到下一个，同时保留旧 APK 归档记录（例如 `3.4.0` 出现后仍保留 `3.3.2`）。

如果未来官网更新导致 `mc_...` 前缀或 JSON 入口本身变化，推荐兜底顺序是：

1. 从 `https://mc.kurogames.com/` 官网 HTML 和最新 JS bundle 重新发现当前 JSON URL。
2. 如有必要，自动点击官方 Android 下载按钮，并捕获网络请求或重定向目标。
3. 只有当前两种发现路径都失败时，才手动记录新捕获的 CDN APK URL，并把它当作临时归档种子，直到自动入口恢复。

这段兜底流程是为了在修改 live sync 逻辑前先写清楚。如果下一次官方更新仍然通过现有 JSON endpoint 解析，就不需要改代码。

## 自动更新

仓库包含 GitHub Actions workflow：`.github/workflows/sync-archive.yml`。

它可以从 Actions 页面手动运行，也会在中国标准时间（UTC+8）每天 `07:18` 和 `12:18` 自动运行。任务流程：

1. 探测当前 NTE 启动器配置，并刷新到当前官方版本的版本化 ResList 索引。
2. 从公开 HoyoFiles API 同步 HoYo 游戏包和 chunk 索引。
3. 克隆 `daydreamer-json/ak-endfield-api-archive`，重新生成 Endfield 精简索引。
4. 刷新鸣潮启动器 / resource-index 数据。
5. 解析已支持的 Android latest-download endpoint，并索引新 APK URL。
6. 即使某个上游失败，也会继续执行后续同步源，最后报告 partial-failure workflow 结果。
7. 当数据更新步骤成功到足以产生有效输出时，提交并推送生成数据。
8. 如果配置了 `CLOUDFLARE_API_TOKEN` 仓库 secret，则部署到 Cloudflare Pages。
9. 如果配置了 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 仓库 secret，则可发送 Telegram 摘要。`TELEGRAM_CHAT_ID` 可以是一个 chat ID，也可以是用逗号或分号分隔的多个 ID。私聊需要先启动 bot 并使用数字用户 chat ID；群组需要把 bot 加入群，并使用负数群组或 supergroup chat ID，通常以 `-100` 开头。

单独的 `.github/workflows/deploy-pages.yml` 会在每次 push 到 `main` 时部署静态站点，也可以手动运行。

## 下载器

安装依赖：

```bash
pip install -r requirements.txt
```

探测可用的版本化资源列表：

```bash
python scripts/nte_downloader.py list --start 1.0.0 --end 1.1.5 --out outputs/nte_versions.json
```

不下载完整客户端，只生成文件索引：

```bash
python scripts/nte_downloader.py prepare 1.1.5 --work-dir outputs/nte_downloader
```

下载完整版本：

```bash
python scripts/nte_downloader.py download 1.1.5 --download-root downloads --workers 4
```

下载后打包：

```bash
python scripts/nte_downloader.py download 1.1.5 --download-root downloads --workers 4 --pack --pack-dir packages
```

打包已经下载好的版本：

```bash
python scripts/nte_downloader.py pack 1.1.5 --download-root downloads --output-dir packages
```

## 免责声明

本项目是非官方数字保存索引。仓库中的 URL 指向官方分发基础设施，或明确标注的公开归档镜像。本仓库不重新分发任何游戏二进制文件。
