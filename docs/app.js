const state = {
  gameId: "nte",
  mode: "full",
  version: null,
  query: "",
  nteCatalog: null,
  hoyoIndex: null,
  hoyoVersions: new Map(),
  nteEntries: new Map(),
  chunkEntries: new Map(),
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const icons = {
  box: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 8-9-5-9 5 9 5 9-5Z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>',
  copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  down: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>',
};

const nteGame = {
  id: "nte",
  name: "异环",
  subName: "Neverness to Everness",
  shortName: "NTE",
  icon: "assets/icons/nte.ico",
  kind: "nte",
};

const audioLabels = {
  "zh-cn": "中文",
  "en-us": "英语",
  "ja-jp": "日语",
  "ko-kr": "韩语",
};

const nteModes = [
  ["full", "完整文件"],
  ["patches", "更新补丁"],
  ["reslist", "清单文件"],
];

const hoyoModes = [
  ["packages", "压缩包"],
  ["updates", "更新包"],
  ["chunk", "Chunk 信息"],
];

const fmtBytes = (bytes) => {
  if (!bytes && bytes !== 0) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 2)} ${units[unit]}`;
};

const fmtDateTime = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date).replace(/\//g, ".");
};

const compareVersions = (left, right) => {
  const leftParts = left.split(".").map(Number);
  const rightParts = right.split(".").map(Number);
  const length = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < length; index += 1) {
    const diff = (leftParts[index] || 0) - (rightParts[index] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const showToast = (text) => {
  const toast = $("#toast");
  toast.textContent = text;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 1600);
};

const copyText = async (text, label = "已复制") => {
  await navigator.clipboard.writeText(text);
  showToast(label);
};

const allGames = () => [
  nteGame,
  ...(state.hoyoIndex?.games || []).map((game) => ({
    ...game,
    subName: game.domain,
    icon: `assets/icons/${game.id}.png`,
    kind: "hoyo",
  })),
];

const currentGame = () => allGames().find((game) => game.id === state.gameId) || nteGame;
const isNte = () => currentGame().kind === "nte";
const modesForGame = () => (isNte() ? nteModes : hoyoModes);

const nteVersions = () => state.nteCatalog.versions.filter((item) => item.status === 200 && item.full);
const nteVersion = () => state.nteCatalog.versions.find((item) => item.version === state.version);
const nteFiles = () => nteVersion()?.[state.mode];

const hoyoSummary = () => state.hoyoIndex.games.find((game) => game.id === state.gameId);
const hoyoVersionMap = () => state.hoyoVersions.get(state.gameId);
const hoyoVersion = () => hoyoVersionMap()?.[state.version] || null;
const hoyoSummaries = () => hoyoSummary()?.versions || [];

const versionFamily = (version) => {
  const parts = version.split(".");
  return isNte() ? parts.slice(0, 2).join(".") : `${parts[0]}.x`;
};

const commandFor = () => {
  if (isNte()) {
    return `python scripts\\nte_downloader.py download ${state.version} --download-root downloads --workers 4 --pack --pack-dir packages`;
  }
  return `aria2c -c -x16 -s16 <从页面复制对应 URL 列表>`;
};

const bindStaticActions = () => {
  $("#selectButton").addEventListener("click", () => {
    const menu = $("#versionMenu");
    const next = menu.hidden;
    menu.hidden = !next;
    $("#selectButton").setAttribute("aria-expanded", String(next));
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".version-picker")) {
      $("#versionMenu").hidden = true;
      $("#selectButton").setAttribute("aria-expanded", "false");
    }
  });

  $("#fileSearch").addEventListener("input", (event) => {
    state.query = event.target.value.trim().toLowerCase();
    renderList();
  });

  $("#copyCommandBtn").addEventListener("click", () => copyText(commandFor(), "命令已复制"));
};

const renderGameRail = () => {
  $("#gameRail").innerHTML = allGames()
    .map((game) => `
      <button class="game-mark ${game.id === state.gameId ? "active" : ""}" type="button" data-game="${game.id}" title="${escapeHtml(game.name)}">
        <img src="${escapeHtml(game.icon || "")}" alt="${escapeHtml(game.name)}" loading="lazy" onerror="this.remove(); this.parentElement.dataset.fallback='${escapeHtml(game.shortName || game.id)}';" />
      </button>
    `)
    .join("");

  $$(".game-mark").forEach((button) => {
    button.addEventListener("click", async () => {
      state.gameId = button.dataset.game;
      state.mode = modesForGame()[0][0];
      state.query = "";
      $("#fileSearch").value = "";
      await ensureGameData();
      render();
    });
  });
};

const renderBrand = () => {
  const game = currentGame();
  $("#brandLogo").innerHTML = game.icon
    ? `<img src="${escapeHtml(game.icon)}" alt="${escapeHtml(game.name)}" onerror="this.remove(); this.parentElement.textContent='${escapeHtml((game.shortName || game.id).slice(0, 3))}';" />`
    : escapeHtml((game.shortName || game.id).slice(0, 3));
  $("#brandName").textContent = game.name;
  $("#brandSub").textContent = game.subName || "";
  $("#pageTitle").textContent = `${game.name}官方 CDN 文件索引`;
};

const renderModes = () => {
  $("#modeTabs").innerHTML = modesForGame()
    .map(([id, label]) => `<button class="mode-tab ${state.mode === id ? "active" : ""}" data-mode="${id}" type="button">${label}</button>`)
    .join("");
  $$(".mode-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      $$(".mode-tab").forEach((item) => item.classList.toggle("active", item === button));
      render();
    });
  });
};

const renderVersionMenu = () => {
  const versions = isNte()
    ? nteVersions()
    : hoyoSummaries().filter((item) => item.package_items || item.update_items || item.has_chunk);

  const groups = [...versions]
    .sort((a, b) => compareVersions(b.version, a.version))
    .reduce((result, item) => {
      const family = versionFamily(item.version);
      if (!result.has(family)) result.set(family, []);
      result.get(family).push(item);
      return result;
    }, new Map());

  $("#versionMenu").innerHTML = [...groups.entries()]
    .map(([family, items]) => `
      <div class="version-group">
        <div class="version-group-head">
          <strong>${family} ${isNte() ? "大版本" : "版本"}</strong>
          <span>${items.length} 个可用版本</span>
        </div>
        ${items.map((item) => versionButton(item)).join("")}
      </div>
    `)
    .join("");

  $$(".version-row").forEach((button) => {
    button.addEventListener("click", () => {
      state.version = button.dataset.version;
      $("#versionMenu").hidden = true;
      $("#selectButton").setAttribute("aria-expanded", "false");
      render();
    });
  });
};

const versionButton = (item) => {
  const family = item.version.split(".").slice(0, 2).join(".");
  const isBase = item.version === `${family}.0`;
  if (isNte()) {
    return `
      <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
        <span class="version-number">${item.version}</span>
        <span class="caps">
          <span class="cap ${isBase ? "green" : "amber"}">${isBase ? "大版本" : "补丁版"}</span>
          <span class="cap slate">${fmtDateTime(item.last_modified)}</span>
          <span class="cap blue">完整</span>
          <span class="cap violet">清单</span>
          <span class="cap green">直链</span>
        </span>
      </button>
    `;
  }
  return `
    <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
      <span class="version-number">${item.version}</span>
      <span class="caps">
        ${item.package_items ? '<span class="cap blue">压缩包</span>' : ""}
        ${item.update_items ? '<span class="cap amber">更新包</span>' : ""}
        ${item.has_chunk ? '<span class="cap violet">Chunk</span>' : ""}
        ${item.has_decompressed_path ? '<span class="cap green">直链文件</span>' : ""}
      </span>
    </button>
  `;
};

const renderStats = () => {
  const stats = isNte() ? nteStats() : hoyoStats();
  $("#stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join("");
};

const nteStats = () => {
  const version = nteVersion();
  const family = version.version.split(".").slice(0, 2).join(".");
  const isBase = version.version === `${family}.0`;
  return [
    ["当前版本", version.version],
    ["版本族", `${family} ${isBase ? "大版本" : "补丁版"}`],
    ["清单时间", fmtDateTime(version.last_modified)],
    ["完整文件", `${version.full.items} 个 / ${fmtBytes(version.full.bytes)}`],
    ["补丁文件", `${version.patches.items} 个 / ${fmtBytes(version.patches.bytes)}`],
  ];
};

const hoyoStats = () => {
  const summary = hoyoSummaries().find((item) => item.version === state.version);
  const chunk = hoyoVersion()?.chunk;
  return [
    ["当前版本", state.version],
    ["压缩包", `${summary?.package_items || 0} 个`],
    ["更新包", `${summary?.update_items || 0} 个`],
    ["直链体积", fmtBytes(summary?.direct_bytes || 0)],
    ["Chunk", chunk ? chunk.tag || "可用" : "无"],
  ];
};

const renderLinks = () => {
  if (isNte()) {
    const files = nteFiles();
    const disabled = state.mode === "reslist" || !files;
    $("#urlsLink").classList.toggle("disabled", disabled);
    $("#aria2Link").classList.toggle("disabled", disabled);
    $("#jsonLink").classList.toggle("disabled", disabled);
    $("#urlsLink").href = files?.urls || "#";
    $("#aria2Link").href = files?.aria2 || "#";
    $("#jsonLink").href = files?.json || "#";
    return;
  }

  $("#urlsLink").classList.add("disabled");
  $("#aria2Link").classList.add("disabled");
  $("#jsonLink").classList.add("disabled");
  $("#urlsLink").href = "#";
  $("#aria2Link").href = "#";
  $("#jsonLink").href = `data/hoyo/${state.gameId}_versions.json`;
  $("#jsonLink").classList.remove("disabled");
};

const renderPanelTitle = () => {
  const modeLabel = modesForGame().find(([id]) => id === state.mode)?.[1] || "文件列表";
  $("#selectedVersion").textContent = state.version || "-";
  $("#copyCommandBtn").innerHTML = `${icons.copy}<span>复制下载命令</span>`;
  $("#commandText").textContent = commandFor();
  $("#panelKicker").textContent = isNte() ? "NTE files" : "Hoyo files";
  $("#panelTitle").textContent = `${state.version} ${modeLabel}`;
};

const loadNteEntries = async () => {
  if (state.mode === "reslist") return [];
  const files = nteFiles();
  if (!files?.json) return [];
  const key = `${state.version}:${state.mode}`;
  if (!state.nteEntries.has(key)) {
    const response = await fetch(files.json);
    state.nteEntries.set(key, await response.json());
  }
  return state.nteEntries.get(key);
};

const loadHoyoChunk = async () => {
  const key = `${state.gameId}:${state.version}`;
  if (!state.chunkEntries.has(key)) {
    const response = await fetch(`data/hoyo/chunk/${state.gameId}_${state.version}.json`);
    const json = await response.json();
    state.chunkEntries.set(key, json.data);
  }
  return state.chunkEntries.get(key);
};

const nteItem = (entry, index, total) => {
  if (state.mode === "patches") {
    const patch = entry.patch || "";
    return {
      badge: "补丁分片",
      title: patch || entry.url.split("/").at(-1),
      subtitle: `${entry.oldfile || "-"}  ->  ${entry.newfile || "-"}`,
      size: entry.filesize,
      hash: patch.split(".")[0] || "-",
      url: entry.url,
      count: `${index + 1}/${total}`,
    };
  }
  return {
    badge: "完整文件",
    title: entry.filename?.split(/[\\/]/).at(-1) || entry.object,
    subtitle: entry.filename || entry.object,
    size: entry.filesize,
    hash: entry.md5,
    url: entry.url,
    count: `${index + 1}/${total}`,
  };
};

const hoyoPackageItems = () => {
  const version = hoyoVersion();
  if (!version) return [];
  const items = [];
  if (version.game?.full) items.push(hoyoDirectItem(version.game.full, "游戏包"));
  if (version.game?.segments?.length) {
    const total = version.game.segments.length;
    version.game.segments.forEach((item, index) => {
      items.push(hoyoDirectItem(item, "游戏包分卷", `${index + 1}/${total}`));
    });
  }
  for (const [lang, item] of Object.entries(version.voice || {})) {
    if (item) items.push(hoyoDirectItem(item, "语音包", audioLabels[lang] || lang));
  }
  return items;
};

const hoyoUpdateItems = () => {
  const version = hoyoVersion();
  if (!version) return [];
  const items = [];
  const fromVersions = Object.keys(version.update || {}).sort(compareVersions).reverse();
  for (const from of fromVersions) {
    const patch = version.update[from];
    if (patch?.game) items.push(hoyoDirectItem(patch.game, "游戏包更新", `${from} -> ${state.version}`));
    for (const [lang, item] of Object.entries(patch?.voice || {})) {
      if (item) items.push(hoyoDirectItem(item, "语音包更新", `${audioLabels[lang] || lang} ${from} -> ${state.version}`));
    }
  }
  return items;
};

const hoyoDirectItem = (item, badge, sublabel = "") => ({
  badge,
  title: item.name,
  subtitle: sublabel || item.url,
  size: item.size,
  hash: item.checksum,
  url: item.url,
});

const renderNteResList = () => {
  const version = nteVersion();
  const rows = [
    ["ResList.bin.zip", "官方版本清单入口", version.reslist_bytes, "PatcherXML0", version.reslist_url],
    ["完整 URL 列表", `${version.full.items} 个文件`, version.full.bytes, "urls.txt", version.full.urls],
    ["完整 aria2 列表", "保留原始目录结构", version.full.bytes, "aria2", version.full.aria2],
    ["完整 JSON 索引", "filename / filesize / md5 / url", version.full.bytes, "json", version.full.json],
    ["补丁 URL 列表", `${version.patches.items} 个补丁对象`, version.patches.bytes, "patch", version.patches.urls],
    ["补丁 aria2 列表", "lastdiff 解出的 patch 对象", version.patches.bytes, "aria2", version.patches.aria2],
  ];

  $("#fileList").innerHTML = rows
    .map(([title, subtitle, size, hash, url], index) => fileCard({
      badge: "清单资源",
      title,
      subtitle,
      size,
      hash,
      url,
      count: `${index + 1}/${rows.length}`,
    }))
    .join("");
  bindCardActions();
};

const renderHoyoChunk = async () => {
  const version = hoyoVersion();
  if (!version?.chunk) {
    $("#fileList").innerHTML = `<div class="empty">该版本没有 Chunk 信息</div>`;
    return;
  }
  const chunk = await loadHoyoChunk();
  const manifests = chunk.manifests || [];
  const summary = manifests.reduce((acc, item) => {
    acc.files += Number(item.stats?.file_count || 0);
    acc.chunks += Number(item.stats?.chunk_count || 0);
    acc.compressed += Number(item.stats?.compressed_size || item.manifest?.compressed_size || 0);
    acc.uncompressed += Number(item.stats?.uncompressed_size || item.manifest?.uncompressed_size || 0);
    return acc;
  }, { files: 0, chunks: 0, compressed: 0, uncompressed: 0 });

  const header = `
    <div class="chunk-summary">
      <div><span>Build Id</span><strong>${escapeHtml(chunk.build_id || "-")}</strong></div>
      <div><span>Manifest</span><strong>${manifests.length.toLocaleString()}</strong></div>
      <div><span>文件数</span><strong>${summary.files.toLocaleString()}</strong></div>
      <div><span>文件块</span><strong>${summary.chunks.toLocaleString()}</strong></div>
      <div><span>压缩大小</span><strong>${fmtBytes(summary.compressed)}</strong></div>
      <div><span>解压大小</span><strong>${fmtBytes(summary.uncompressed)}</strong></div>
    </div>
  `;

  const filtered = filterEntries(manifests);
  $("#fileList").innerHTML = header + (filtered.length ? filtered
    .map((item, index) => {
      const url = `${item.manifest_download.url_prefix}/${item.manifest.id}`;
      return fileCard({
        badge: "Chunk Manifest",
        title: item.category_name,
        subtitle: `manifest id: ${item.manifest.id} / matching field: ${item.matching_field || "-"}`,
        size: Number(item.stats?.compressed_size || item.manifest?.compressed_size || 0),
        hash: item.manifest.checksum,
        url,
        count: `${index + 1}/${filtered.length}`,
      });
    })
    .join("") : `<div class="empty">没有匹配到 Chunk Manifest</div>`);
  bindCardActions();
};

const fileCard = (item) => `
  <article class="file-card">
    <div class="file-icon">${icons.box}</div>
    <div class="file-main">
      <div class="file-title">
        <span class="pill">${escapeHtml(item.badge)}</span>
        <span class="count">${escapeHtml(item.count || "")}</span>
        <strong>${escapeHtml(item.title)}</strong>
      </div>
      <div class="file-meta">
        <span>${fmtBytes(item.size)}</span>
        <span># ${escapeHtml(item.hash || "-")}</span>
      </div>
      <div class="file-path">${escapeHtml(item.subtitle)}</div>
    </div>
    <div class="file-actions">
      <button class="icon-button copy-link" type="button" data-url="${escapeHtml(item.url)}" title="复制链接">${icons.copy}<span>复制链接</span></button>
      <a class="icon-button" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer" title="下载">${icons.down}<span>下载</span></a>
    </div>
  </article>
`;

const bindCardActions = () => {
  $$(".copy-link").forEach((button) => {
    button.addEventListener("click", () => copyText(button.dataset.url, "链接已复制"));
  });
};

const renderList = async () => {
  if (isNte()) {
    if (state.mode === "reslist") {
      renderNteResList();
      return;
    }
    const entries = await loadNteEntries();
    const filtered = filterEntries(entries);
    $("#fileList").innerHTML = filtered
      .map((entry, index) => fileCard(nteItem(entry, index, filtered.length)))
      .join("") || `<div class="empty">没有匹配到文件</div>`;
    bindCardActions();
    return;
  }

  if (state.mode === "chunk") {
    await renderHoyoChunk();
    return;
  }

  const entries = state.mode === "packages" ? hoyoPackageItems() : hoyoUpdateItems();
  const filtered = filterEntries(entries);
  $("#fileList").innerHTML = filtered
    .map((entry, index) => fileCard({ ...entry, count: `${index + 1}/${filtered.length}` }))
    .join("") || `<div class="empty">该版本没有${state.mode === "packages" ? "压缩包" : "更新包"}直链</div>`;
  bindCardActions();
};

const filterEntries = (entries) => {
  const needle = state.query;
  return entries.filter((entry) => JSON.stringify(entry).toLowerCase().includes(needle));
};

const ensureGameData = async () => {
  if (isNte()) {
    state.version = nteVersions().sort((a, b) => compareVersions(b.version, a.version))[0].version;
    return;
  }
  if (!state.hoyoVersions.has(state.gameId)) {
    const response = await fetch(`data/hoyo/${state.gameId}_versions.json`);
    state.hoyoVersions.set(state.gameId, await response.json());
  }
  const versions = hoyoSummaries()
    .filter((item) => item.package_items || item.update_items || item.has_chunk)
    .sort((a, b) => compareVersions(b.version, a.version));
  state.version = versions[0]?.version || null;
};

const renderNotice = () => {
  const notice = $("#notes");
  if (isNte()) {
    notice.innerHTML = `<strong>技术说明</strong><span>页面仅保存由官方 CDN 清单解析出的 URL、校验信息与下载索引；解密流程与复现细节见仓库 README。</span>`;
  } else {
    notice.innerHTML = `<strong>数据来源</strong><span>米家游戏数据迁移自 HoyoFiles 的公开版本清单接口，并在本站保存为静态索引；Chunk 视图只展示 Manifest 入口与统计信息。</span>`;
  }
};

const render = () => {
  renderGameRail();
  renderBrand();
  renderModes();
  renderVersionMenu();
  renderStats();
  renderLinks();
  renderPanelTitle();
  renderNotice();
  renderList();
};

Promise.all([
  fetch("./data/catalog.json").then((response) => response.json()),
  fetch("./data/hoyo/games.json").then((response) => response.json()),
]).then(async ([nteCatalog, hoyoIndex]) => {
  state.nteCatalog = nteCatalog;
  state.hoyoIndex = hoyoIndex;
  bindStaticActions();
  await ensureGameData();
  render();
});
