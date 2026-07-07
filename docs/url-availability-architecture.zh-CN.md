# URL 可用性架构

英文版本：`docs/url-availability-architecture.md`。

本文档记录当前项目中 URL 可用性是如何实现的，以及下一次重写前应该先统一哪些概念。当前系统可以工作，但它是多轮独立补丁累积出来的。后续动代码前，先把这里当作地图。

## 当前状态

现在没有一个统一的、唯一的可用性判断引擎。

仓库里目前至少有三种含义，都会在页面或数据里被显示成“可用”“不可用”“过期”或“未知”：

- HTTP 探测结果：本仓库用 `HEAD` 或带 `Range` 的 `GET` 检查过某个 URL。
- 上游归档状态：外部归档或镜像源记录了它当时看到的原始 URL 是否可用。
- 元数据推断状态：源数据里有 size、时间、mirror 或其他字段，因此推断这个 URL 大概率可用。

这些含义本身都合理，但不能继续静默混用。

## 跨数据集 URL 健康索引

跨数据集健康索引由下面的脚本生成：

```bash
python scripts/probe_url_status.py
```

输出文件是：

```text
outputs/url_status.json
```

输出文件会放在发布目录 `docs/` 之外。脚本会扫描 `docs/data/` 下的 JSON 文件，但会排除：

- `docs/data/android/lists/`

它递归收集字段名为下面两种的 HTTP 链接：

- `url`
- `archive_url`

它会跳过字段名为 `urls` 的数组。这一点对 WuWa 很重要，因为 WuWa 文件记录里可能同时有主 `url` 和多 CDN 的 `urls` 数组。当前健康索引只检查主 URL，不会逐个检查所有备用 CDN URL。

WuWa 的多 CDN 可用性现在由 WuWa 自己的 availability 构建步骤处理，而不是由 `url_status.json` 处理。`scripts/build_wuwa_availability.py --live-probe` 会通过 `probe_scheduler.py` 调用共享的 `url_probe.py` 探测原语，按有界 fallback 策略探测候选 URL，并把探测事实写回 WuWa 的 version/list JSON。跨数据集的 `url_status.json` 仍然只是离线审计索引，不能被当成 WuWa CDN 择优的前端数据源。

每个被选中的 URL 会按下面流程探测：

1. 先尝试 `HEAD`。
2. 如果 `HEAD` 被拦截、返回空大小，或者结果可疑，再尝试 `GET` 并带上 `Range: bytes=0-0`。
3. 记录 status、final URL、content type、size、last modified、ETag、error 和 `ok`。

当响应状态码位于 `200..399`，并且不像空 HTML 错误页时，结果会被视为 `ok`。

这个探测默认是增量的：

- 新 URL 一定会探测。
- 之前不可用的 URL 会更快重测。
- 旧的健康 URL 会分批轮换重测。
- `URL_STATUS_FORCE_FULL=1` 可以强制全量扫描。

重要限制：`url_status.json` 不是前端的数据源。页面不会直接读取它。它目前是不会发布的离线审计索引。

## Android APK 可用性

Android APK 可用性实现在：

```text
scripts/sync_android_apks.py
```

这条流水线有自己的可用性规则，因为 APK 端点经常和普通 CDN 文件表现不同。

Android 逻辑可以：

- 用 `HEAD` 探测；
- 回退到 curl；
- 回退到大小检查；
- 对已知 CDN 的浏览器挑战响应做特殊处理；
- 在没有到全量重测时间时保留旧记录。

一般来说，只有当远端对象看起来像 APK，并且大小大于一个较小阈值时，才会被当作可用 APK。历史记录即使当前 URL 已死，也可能继续保留。

Android 有单独的 TTL：

```text
ANDROID_APK_REPROBE_TTL_HOURS
```

这意味着 Android 可用性的新旧程度可能和 `url_status.json` 不一致。

## HoYo PC 可用性

HoYo PC 元数据由下面脚本生成：

```text
scripts/sync_hoyofiles.py
```

HoYo 当前使用这些数据文件：

```text
docs/data/hoyo/games.json
docs/data/hoyo/versions/{game}/{version}.json
docs/data/hoyo/chunk/{game}_{version}.json
```

前端显示 HoYo 可用性红标时，主要依赖 `games.json` 里的 `unavailable_items`。

当前 `unavailable_items` 是根据版本元数据统计出来的：下载项 size 为 `0` 或缺失，就计入不可用项。它不是对每一个 package URL 做实时 HTTP 探测。

这个字段适合作为“源数据元信息提醒”，但不应该被解释成“本站刚刚探测服务器并返回 404”。

HoYo 也有 `fetch_head_metadata()` 辅助逻辑，用于读取 `Last-Modified` 和 `Content-Length` 等 header。但这个 helper 和跨数据集 URL 健康探测不是同一套逻辑。

## WuWa PC 可用性

WuWa PC 元数据由这些脚本生成：

```text
scripts/sync_wuwa.py
scripts/import_tomyjan_wuwa.py
```

WuWa 的数据结构是：

```text
docs/data/wuwa/index.json
docs/data/wuwa/versions/{version}.json
docs/data/wuwa/lists/
```

WuWa 文件记录里可能包含：

- 主 `url`；
- 包含多个 CDN 候选的 `urls` 数组。

当前跨数据集健康探测会看到主 `url`，但不会检查 `urls` 里的每一个 URL。

迁移后的 WuWa availability 路径会把每个候选都写进标准的 `availability.candidates` 数组。结构化阶段使用 `source.kind=metadata_inference`；live canary 阶段会对选中的版本使用 `source.kind=live_probe`。实时探测是有界的：先探主 URL，主 URL 可用就立刻停止；只有主 URL 失败时，才按顺序探备用 CDN。全版本放开保留为 canary 复核后的独立步骤。

WuWa 也有自己的 `fetch_head_metadata()` helper，用于读取 header 元数据。它和 HoYo 的 helper 名字相似，但不是共享实现。

## Endfield PC 可用性

Endfield 元数据由下面脚本导入：

```text
scripts/import_endfield_archive.py
```

Endfield 记录使用这些字段：

```text
official_url
official_available
mirror_url
preferred_url
```

`official_available` 来自上游归档或镜像元数据。它不一定代表本仓库在页面加载时做过实时探测。

前端会使用 `official_available` 来标记官方链接是否已知可用、已过期，或者是否由镜像兜底。

## Arknights PC 可用性

Arknights PC 当前是一个很小的聚合数据集：

```text
docs/data/arknights/index.json
docs/data/arknights/versions.json
```

它的 package URL 会进入跨数据集健康索引，但页面不会读取 `url_status.json` 来决定是否展示 package 记录。

## NTE 可用性

NTE 有单独的 ResList 解码和下载工具：

```text
scripts/archive_reslist_versions.py
scripts/build_urls_from_reslist.py
scripts/nte_downloader.py
```

这些脚本负责探测或解码带版本号的资源列表归档，并生成每个版本的 URL 列表。它们的可用性模型早于后来的 split validator 架构。

NTE 生成出来的 JSON 文件也会被跨数据集健康索引扫描。

## 前端可用性展示

前端目前从各游戏自己的字段里读取可用性：

- Android：`unavailable_count`
- HoYo：`unavailable_items`
- Endfield：`official_available`
- 旧候选线索：`current.status_code` 和 `archive.status_code`

前端不会读取 `outputs/url_status.json`。

这也是为什么同一个 UI 标签在不同游戏里可能代表不同含义。这是目前最大的架构风险。

## 当前风险

当前系统有这些漂移风险：

- 类似的 helper 名字隐藏了不同实现，尤其是 `fetch_head_metadata()`。
- 有些字段代表本站实时 HTTP 探测，有些字段代表上游归档状态，有些只是元数据推断。
- 数据结构变化后，`url_status.json` 可能变旧。
- WuWa `urls` 这类多 CDN 数组没有完整进入跨数据集健康索引。
- 前端用“失效”“不可用”这类短标签压缩了不同含义。
- 现有 validator 检查游戏数据结构，但不检查可用性语义。

## 重写方向

下一次重写应该使用一套共享可用性模型。

这里最重要的区分是：规则内容不必完全一样，但流水线和契约必须完全一样。Android 确实需要 APK 专属的 size 和 content-type 判断；Endfield 确实需要 official 和 mirror 的优先级规则；WuWa 确实需要多 CDN 择优规则。强行让这些规则字面一致，反而会制造新的坑。

真正需要统一的是形状：

- 每个游戏都进入同一条 probe 流水线；
- 每个游戏都接收同一种 probe 事实；
- 每个游戏都输出同一种 interpretation 字段；
- 每个前端视图都读取同一份 availability 契约。

目标流程应该是：

```text
原始 URL 候选集合（1..N 个 URL）
  -> 标准探测结果集合
  -> 游戏/来源专属解释
  -> 前端展示标签
```

换句话说：

1. 先对 URL 对象本身做一个整体判断。
2. 再根据游戏或数据来源规则做次级判断。
3. 把这两层判断都显式存下来。

不要再让每个游戏给同一个字段名发明自己的含义。

第一层是唯一允许执行网络 I/O 的层。它只回答：“这个 URL 对象现在观测到的状态是什么？”它不能知道 APK 规则、mirror 规则、HoYo package 语义或前端中文标签。

第二层是游戏 adapter。它回答：“基于共享 probe 事实和这个游戏的源记录，本项目应该如何解释这个 URL？”它可以应用游戏规则，但绝对不能自己发 HTTP 请求。

probe 契约必须接收候选集合，而不是只能接收单个 URL。普通 package 可能只有一个候选；WuWa 可能有主 `url`，再加上 `urls` 里的多个 CDN 候选。probe 层必须返回每个候选 URL 的事实，这样 WuWa adapter 才能在不执行网络 I/O 的情况下选择 `preferred_url`。

adapter 在数据生成或同步阶段运行，不在浏览器运行。adapter 输出会写入 JSON。前端不应该再保留游戏专属可用性逻辑，只负责渲染预计算好的 interpretation。

## 建议的标准字段

未来记录应该把探测事实和解释分开：

```json
{
  "url": "https://example.invalid/file.apk",
  "availability": {
    "candidates": [
      {
        "url": "https://example.invalid/file.apk",
        "probe": {
          "ok": false,
          "status": 404,
          "method": "HEAD",
          "checked_at": "2026-07-06T00:00:00Z",
          "size": 0,
          "content_type": "",
          "error": "HTTP 404"
        }
      }
    ],
    "source": {
      "kind": "live_probe",
      "confidence": "high"
    },
    "interpretation": {
      "state": "unavailable",
      "reason": "http_404",
      "preferred_url": "",
      "retained": false,
      "display_label": "链接失效"
    }
  }
}
```

具体 schema 可以调整，但这些概念需要保持分离：

- 探测事实；
- 事实来源；
- 可信度；
- 游戏专属解释；
- 前端展示标签。

`state` 和 `display_label` 必须分开。`state` 是机器语义，例如 `available`、`unavailable`、`mirror_only`、`unknown`。`display_label` 是给人看的文字，例如 `链接失效`。脚本和 validator 应该读取 `state`，前端负责渲染 `display_label`。

历史死链必须是一等公民。如果某条记录当前已不可用，但因为归档价值需要继续保留，应设置 `interpretation.retained=true`，并使用类似 `retained_historical` 的 reason。

## 封闭可用性词表

这些词表应该是封闭集合。adapter 不能随意发明新值；如果确实要新增，必须先更新本文档和可用性 validator。

`source.kind`：

- `live_probe`：本仓库探测过该 URL。
- `upstream_archive`：外部归档或镜像提供了状态。
- `metadata_inference`：可用性来自源元数据推断。
- `manual_seed`：人工维护的记录被保留。

`confidence`：

- `high`：新鲜 live probe，或高度可靠的上游状态。
- `medium`：过期但尚近的 probe、镜像兜底状态，或较强元数据。
- `low`：旧 probe、弱元数据，或手动保留的历史记录。

`interpretation.state`：

- `available`：首选 URL 当前可用。
- `unavailable`：没有已知可用 URL。
- `mirror_only`：原始 URL 不可用，但镜像可用。
- `unknown`：没有足够新鲜的证据判断。

历史死链不是单独的 state。它应该使用 `state=unavailable`、`retained=true` 和 `reason=retained_historical`。

`interpretation.reason`：

- `http_2xx`
- `http_3xx`
- `http_403`
- `http_404`
- `http_5xx`
- `http_timeout`
- `dns_error`
- `tls_error`
- `range_probe_ok`
- `bot_challenge`
- `size_zero`
- `content_type_mismatch`
- `metadata_size_missing`
- `mirror_fallback`
- `multi_cdn_preferred`
- `upstream_marked_unavailable`
- `retained_historical`
- `not_probed`

## 建议的共享探测模块

新增一个共享模块，例如：

```text
scripts/url_probe.py
```

它应该是无状态模块，只负责探测原语：

- 请求 header；
- URL 编码；
- `HEAD` 探测；
- 带 `Range` 的 `GET` 回退；
- 必要时的 curl 回退；
- 状态码归一化；
- content length 提取；
- 浏览器挑战分类；
- timeout 处理；
- 稳定输出 schema。

它应该接收 `1..N` 个 URL 候选，并返回 `1..N` 个候选探测结果。它不应该决定 TTL、轮换、批次或 force-full 行为。

各游戏同步脚本应该调用这个模块，而不是复制探测逻辑。
游戏 adapter 不允许调用 curl、`urllib`、`fetch` 或任何 HTTP 客户端。如果 adapter 需要更多事实，应该扩展共享 probe result schema，而不是在 adapter 里偷偷补请求。

## 建议的探测调度层

调度和缓存应该从 `scripts/url_probe.py` 里拆出来。

新增一个调度/缓存层，例如：

```text
scripts/probe_scheduler.py
```

它应该负责：

- TTL 策略；
- 失败记录重试窗口；
- 轮换批次；
- `URL_STATUS_FORCE_FULL`；
- Android APK 重测 TTL 这类按来源覆盖的参数；
- 复用旧 probe 事实；
- 根据新鲜度降低 confidence。

Android 的 `ANDROID_APK_REPROBE_TTL_HOURS` 应该变成调度层参数，而不是另一套探测实现。

新鲜度必须影响 interpretation。一个很旧的成功 probe 不应该永远保持 `confidence=high`。建议默认规则：

- 在 TTL 内：保持 `confidence=high`；
- 超过 TTL 但仍在较长宽限期内：降级为 `confidence=medium`；
- 超过宽限期：降级为 `confidence=low`，或允许 adapter 返回 `state=unknown`。

## 建议的游戏适配层

有了共享 probe result 后，每个游戏只应该提供 adapter：

```python
class GameAvailabilityAdapter(Protocol):
    game: str

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        ...
```

每个 adapter 的输入都一样：

- 所有 URL 候选的标准 probe 事实；
- 原始游戏/来源记录。

每个 adapter 的输出也必须是同一种 `Interpretation` 形状：

- `state`；
- `reason`；
- `preferred_url`；
- `confidence`；
- `retained`；
- `display_label`。

- Android adapter：APK 专属 size/content-type 规则。
- HoYo adapter：package/update 项解释，以及 size 元数据回退。
- WuWa adapter：主 URL 和可选 CDN 备用 URL。
- Endfield adapter：official URL 和 mirror URL 的优先级。
- Arknights adapter：package URL 解释。
- NTE adapter：ResList/object URL 解释。

adapter 不应该执行彼此无关的 HTTP 逻辑。它只负责解释共享探测结果。

前端最终应该只读取统一 availability 契约。`unavailable_count`、`unavailable_items`、`official_available`、`status_code` 这些旧字段，要么通过兼容层翻译，要么在迁移完成后删除。

## 安全迁移计划

不要一次性重写全部内容。

建议按这个顺序：

1. 记录当前行为。本文档就是这一步。
2. 增加一个只读的可用性 validator。
3. 定义 `source.kind`、`confidence`、`state`、`reason` 的封闭词表。
4. 定义 `ProbeResult` 和 `Interpretation` schema，包括多 URL 候选集合。
5. 定义 adapter 接口。
6. HoYo 分片后刷新 `url_status.json`。
7. 新增无状态的 `scripts/url_probe.py`，但先不改变现有同步行为。
8. 新增调度/缓存层，但先不改变现有同步行为。
9. 选择一个低风险流水线接入共享模块。
10. 把旧输出和新输出并排比较。
11. 确认一致后，再切换正式数据输出。
12. 按游戏或来源逐个迁移。

建议第一个 adapter 目标：

- 如果想先做最小数据面，选 Arknights PC。
- 如果想先解决最乱、最影响用户感知的逻辑，选 Android。

更稳的迁移顺序是：

1. Arknights PC，因为数据面最小。
2. Android，因为它最乱，也最影响用户感知。
3. HoYo。
4. Endfield。
5. NTE。
6. WuWa 多 CDN 可用性最后处理。

除非目标就是重新设计多 CDN 可用性，否则不要从 WuWa 文件列表开始。WuWa 的 `urls` 择优应该作为单独设计步骤，而不是顺手混在 probe 重构里。

## 可用性改动的最低检查

只读可用性 validator 应该检查：

- 每条已迁移记录都有 `availability` 块；
- 每个 availability 块都有 `candidates`、`source`、`interpretation`；
- 每个 candidate 都有 `url` 和 `probe`；
- `source.kind`、`confidence`、`interpretation.state`、`interpretation.reason` 都在封闭词表内；
- 只要存在 `state`，就必须存在 `interpretation.display_label`；
- `interpretation.preferred_url` 为空，或匹配候选 URL，或匹配显式声明的 mirror URL；
- `interpretation.retained` 是布尔值；
- retained 记录必须使用明确的 retained reason；
- 过期 probe 必须降级 confidence，或变成 `state=unknown`；
- URL health 的 source file 必须指向实际存在的文件。

未来任何可用性重写都应该运行：

```bash
node --check docs/app.js
python scripts/validate_wuwa_split.py
python scripts/validate_hoyo_split.py
python scripts/validate_endfield_archive.py
python scripts/validate_arknights_pc.py
```

还应该本地验证：

- 15 个游戏入口都能显示；
- Android / Arknights / WuWa / HoYo / Endfield 入口仍然存在；
- HoYo 版本 shard 仍然能加载；
- 可用性标签仍然符合预期语义；
- 生成的 URL health source file 仍然指向实际存在的文件。
