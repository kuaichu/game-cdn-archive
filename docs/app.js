const state = {
  gameId: "nte",
  mode: "full",
  version: null,
  compareVersion: null,
  query: "",
  nteCatalog: null,
  hoyoIndex: null,
  endfieldIndex: null,
  endfieldVersions: null,
  hoyoVersions: new Map(),
  nteEntries: new Map(),
  chunkEntries: new Map(),
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const VIEW_STORAGE_KEY = "game-cdn-archive:view";
const REPOSITORY_URL = "https://github.com/kuaichu/game-cdn-archive";

const loadSavedView = () => {
  try {
    return JSON.parse(localStorage.getItem(VIEW_STORAGE_KEY)) || {};
  } catch {
    return {};
  }
};

const saveView = () => {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify({
      gameId: state.gameId,
      mode: state.mode,
      version: state.version,
    }));
  } catch {
    // The page still works when storage is blocked or unavailable.
  }
};

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
  icon: "assets/icons/nte.png",
  kind: "nte",
};

const audioLabels = {
  "zh-cn": "中文",
  "en-us": "英语",
  "ja-jp": "日语",
  "ko-kr": "韩语",
};

const hoyoEnglishNames = {
  hk4e: "Genshin Impact",
  hkrpg: "Honkai: Star Rail",
  nap: "Zenless Zone Zero",
  bh3: "Honkai Impact 3rd",
};

const nteModes = [
  ["full", "完整文件"],
  ["patches", "更新补丁"],
  ["reslist", "清单文件"],
  ["compare", "版本对比"],
];

const hoyoModes = [
  ["packages", "压缩包"],
  ["updates", "更新包"],
  ["chunk", "Chunk 信息"],
  ["compare", "版本对比"],
];

const endfieldModes = [
  ["packages", "完整包"],
  ["patches", "更新补丁"],
  ["archive", "归档信息"],
  ["compare", "版本对比"],
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
  ...(state.endfieldIndex?.game ? [state.endfieldIndex.game] : []),
  ...(state.hoyoIndex?.games || []).map((game) => ({
    ...game,
    subName: hoyoEnglishNames[game.id] || game.name,
    icon: `assets/icons/${game.id}.png`,
    kind: "hoyo",
  })),
];

const currentGame = () => allGames().find((game) => game.id === state.gameId) || nteGame;
const isNte = () => currentGame().kind === "nte";
const isEndfield = () => currentGame().kind === "endfield";
const modesForGame = () => (isNte() ? nteModes : isEndfield() ? endfieldModes : hoyoModes);

const nteVersions = () => state.nteCatalog.versions.filter((item) => item.status === 200 && item.full);
const nteVersion = () => state.nteCatalog.versions.find((item) => item.version === state.version);
const nteFiles = () => nteVersion()?.[state.mode];

const hoyoSummary = () => state.hoyoIndex.games.find((game) => game.id === state.gameId);
const hoyoVersionMap = () => state.hoyoVersions.get(state.gameId);
const hoyoVersion = () => hoyoVersionMap()?.[state.version] || null;
const hoyoSummaries = () => hoyoSummary()?.versions || [];

const endfieldVersion = () => state.endfieldVersions?.[state.version] || null;
const endfieldSummaries = () => state.endfieldIndex?.versions || [];

const availableSummaries = () => {
  if (isNte()) return nteVersions();
  if (isEndfield()) return endfieldSummaries();
  return hoyoSummaries().filter((item) => item.package_items || item.update_items || item.has_chunk);
};

const availableVersions = () => availableSummaries()
  .map((item) => item.version)
  .sort(compareVersions);

const defaultCompareVersion = () => {
  const versions = availableVersions();
  const currentIndex = versions.indexOf(state.version);
  if (currentIndex > 0) return versions[currentIndex - 1];
  return versions.find((version) => version !== state.version) || null;
};

const versionFamily = (version) => {
  const parts = version.split(".");
  return isNte() || isEndfield() ? parts.slice(0, 2).join(".") : `${parts[0]}.x`;
};

const commandFor = () => {
  if (state.mode === "compare") {
    return "版本对比模式不需要下载命令";
  }
  if (isNte()) {
    return `python scripts\\nte_downloader.py download ${state.version} --download-root downloads --workers 4 --pack --pack-dir packages`;
  }
  if (isEndfield()) {
    return `aria2c -c -x16 -s16 data/endfield/lists/${state.version}_${state.mode === "patches" ? "patches" : "packages"}.aria2.txt`;
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
      state.compareVersion = null;
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
      state.compareVersion = null;
      $$(".mode-tab").forEach((item) => item.classList.toggle("active", item === button));
      render();
    });
  });
};

const renderVersionMenu = () => {
  const groups = [...availableSummaries()]
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
          <strong>${family} ${isNte() || isEndfield() ? "大版本" : "版本"}</strong>
          <span>${items.length} 个可用版本</span>
        </div>
        ${items.map((item) => versionButton(item)).join("")}
      </div>
    `)
    .join("");

  $$(".version-row").forEach((button) => {
    button.addEventListener("click", () => {
      state.version = button.dataset.version;
      state.compareVersion = null;
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
  if (isEndfield()) {
    return `
      <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
        <span class="version-number">${item.version}</span>
        <span class="caps">
          <span class="cap slate">${fmtDateTime(item.released_at)}</span>
          <span class="cap blue">${item.package_items} 个完整分卷</span>
          ${item.patch_routes ? `<span class="cap amber">${item.patch_routes} 条更新路径</span>` : ""}
          ${item.mirror_items ? '<span class="cap green">归档镜像</span>' : ""}
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
  const stats = isNte() ? nteStats() : isEndfield() ? endfieldStats() : hoyoStats();
  $("#stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join("");
};

const endfieldStats = () => {
  const summary = endfieldSummaries().find((item) => item.version === state.version);
  const version = endfieldVersion();
  return [
    ["当前版本", state.version],
    ["归档时间", fmtDateTime(summary?.released_at)],
    ["完整包", `${summary?.package_items || 0} 个 / ${fmtBytes(summary?.packed_size || 0)}`],
    ["解压大小", fmtBytes(summary?.unpacked_size || 0)],
    ["更新路径", `${version?.patches?.length || 0} 条`],
  ];
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
  if (state.mode === "compare") {
    $("#urlsLink").classList.add("disabled");
    $("#aria2Link").classList.add("disabled");
    $("#jsonLink").classList.add("disabled");
    $("#urlsLink").href = "#";
    $("#aria2Link").href = "#";
    $("#jsonLink").href = "#";
    return;
  }

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

  if (isEndfield()) {
    const links = endfieldVersion()?.links?.[state.mode];
    const disabled = !links || state.mode === "archive";
    $("#urlsLink").classList.toggle("disabled", disabled);
    $("#aria2Link").classList.toggle("disabled", disabled);
    $("#urlsLink").href = links?.urls || "#";
    $("#aria2Link").href = links?.aria2 || "#";
    $("#jsonLink").href = "data/endfield/versions.json";
    $("#jsonLink").classList.remove("disabled");
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
  $("#panelKicker").textContent = isNte() ? "NTE files" : isEndfield() ? "Endfield files" : "Hoyo files";
  $("#panelTitle").textContent = `${state.version} ${modeLabel}`;
};

const loadNteEntries = async (version = state.version, mode = state.mode) => {
  if (mode === "reslist" || mode === "compare") mode = "full";
  const row = state.nteCatalog.versions.find((item) => item.version === version);
  const files = row?.[mode];
  if (!files?.json) return [];
  const key = `${version}:${mode}`;
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

const endfieldPackageItems = () => {
  const version = endfieldVersion();
  if (!version) return [];
  return version.packages.map((item) => ({
    badge: item.official_available ? "官方完整分卷" : "完整分卷",
    title: item.name,
    subtitle: item.official_available ? "上游探测时官方链接可用" : "上游曾标记官方链接不可用；实际状态可能变化",
    size: item.size,
    hash: item.md5,
    officialUrl: item.official_url,
    officialAvailable: item.official_available,
    mirrorUrl: item.mirror_url,
    preferredUrl: item.preferred_url,
  }));
};

const endfieldPatchItems = () => {
  const version = endfieldVersion();
  if (!version) return [];
  return version.patches.flatMap((route) => route.parts.map((item) => ({
    badge: "更新分卷",
    title: item.name,
    subtitle: `${route.from} -> ${route.to}${item.official_available ? " / 上游探测可用" : " / 官方状态未知，镜像可用"}`,
    size: item.size,
    hash: item.md5,
    officialUrl: item.official_url,
    officialAvailable: item.official_available,
    mirrorUrl: item.mirror_url,
    preferredUrl: item.preferred_url,
  })));
};

const normalizeVersionText = (value) => String(value || "").replace(/\d+\.\d+\.\d+/g, "{version}");

const hoyoComparableItems = (version) => {
  const row = hoyoVersionMap()?.[version];
  if (!row) return [];
  const items = [];
  const addItem = (item, badge, sublabel = "") => {
    if (!item) return;
    const title = item.name || item.url;
    items.push({
      key: `${badge}:${normalizeVersionText(sublabel)}:${normalizeVersionText(title)}`,
      title,
      subtitle: sublabel || item.url,
      badge,
      size: Number(item.size || 0),
      hash: item.checksum || "",
      url: item.url,
    });
  };

  addItem(row.game?.full, "游戏包");
  (row.game?.segments || []).forEach((item, index) => addItem(item, "游戏包分卷", `分卷 ${index + 1}`));
  Object.entries(row.voice || {}).forEach(([lang, item]) => addItem(item, "语音包", audioLabels[lang] || lang));
  Object.entries(row.update || {}).forEach(([from, patch]) => {
    addItem(patch?.game, "游戏包更新", normalizeVersionText(`${from} -> ${version}`));
    Object.entries(patch?.voice || {}).forEach(([lang, item]) => {
      addItem(item, "语音包更新", `${audioLabels[lang] || lang} ${normalizeVersionText(`${from} -> ${version}`)}`);
    });
  });
  return items;
};

const endfieldComparableItems = (version) => {
  const row = state.endfieldVersions?.[version];
  if (!row) return [];
  const packages = (row.packages || []).map((item, index) => ({
    key: `package:${index + 1}`,
    title: item.name,
    subtitle: item.official_available ? "官方完整分卷" : "完整分卷",
    badge: "完整包",
    size: Number(item.size || 0),
    hash: item.md5 || "",
    url: item.preferred_url || item.official_url || item.mirror_url,
  }));
  const patches = (row.patches || []).flatMap((route) => route.parts.map((item, index) => ({
    key: `patch:${normalizeVersionText(route.from)}->${normalizeVersionText(route.to)}:${index + 1}`,
    title: item.name,
    subtitle: `${route.from} -> ${route.to}`,
    badge: "更新补丁",
    size: Number(item.size || 0),
    hash: item.md5 || "",
    url: item.preferred_url || item.official_url || item.mirror_url,
  })));
  return [...packages, ...patches];
};

const nteComparableItems = async (version) => {
  const entries = await loadNteEntries(version, "full");
  return entries.map((item) => ({
    key: item.filename || item.object,
    title: item.filename?.split(/[\\/]/).at(-1) || item.object,
    subtitle: item.filename || item.object,
    badge: "完整文件",
    size: Number(item.filesize || 0),
    hash: item.md5 || "",
    url: item.url,
  }));
};

const comparableItems = async (version) => {
  if (isNte()) return nteComparableItems(version);
  if (isEndfield()) return endfieldComparableItems(version);
  return hoyoComparableItems(version);
};

const diffVersions = (oldItems, newItems) => {
  const oldMap = new Map(oldItems.map((item) => [item.key, item]));
  const newMap = new Map(newItems.map((item) => [item.key, item]));
  const added = [];
  const removed = [];
  const checksumChanged = [];
  const sizeChanged = [];

  for (const [key, item] of newMap) {
    const oldItem = oldMap.get(key);
    if (!oldItem) {
      added.push(item);
      continue;
    }
    if (oldItem.hash && item.hash && oldItem.hash !== item.hash) {
      checksumChanged.push({ ...item, oldHash: oldItem.hash, oldSize: oldItem.size });
    }
    if (Number(oldItem.size || 0) !== Number(item.size || 0)) {
      sizeChanged.push({ ...item, oldHash: oldItem.hash, oldSize: oldItem.size });
    }
  }

  for (const [key, item] of oldMap) {
    if (!newMap.has(key)) removed.push(item);
  }

  return { added, removed, checksumChanged, sizeChanged };
};

const diffLabels = {
  added: ["新增文件", "green"],
  removed: ["删除文件", "rose"],
  checksumChanged: ["MD5 变化", "violet"],
  sizeChanged: ["大小变化", "amber"],
};

const renderCompare = async () => {
  const versions = availableVersions();
  if (!state.compareVersion || state.compareVersion === state.version || !versions.includes(state.compareVersion)) {
    state.compareVersion = defaultCompareVersion();
  }
  if (!state.compareVersion) {
    $("#fileList").innerHTML = `<div class="empty">没有可用于对比的其他版本</div>`;
    return;
  }

  const [oldItems, newItems] = await Promise.all([
    comparableItems(state.compareVersion),
    comparableItems(state.version),
  ]);
  const diff = diffVersions(oldItems, newItems);
  const totalChanges = Object.values(diff).reduce((sum, items) => sum + items.length, 0);
  const sourceHint = isNte()
    ? "异环基于完整文件清单做文件级对比。"
    : "当前基于本站保存的归档条目对比；要做压缩包内部文件级对比，需要额外保存 Chunk/Manifest 文件索引。";

  const selector = `
    <div class="compare-toolbar">
      <div>
        <span>对比范围</span>
        <strong>${escapeHtml(state.compareVersion)} -> ${escapeHtml(state.version)}</strong>
      </div>
      <label>
        <span>基准版本</span>
        <select id="compareVersionSelect">
          ${versions.filter((version) => version !== state.version).map((version) => `
            <option value="${escapeHtml(version)}" ${version === state.compareVersion ? "selected" : ""}>${escapeHtml(version)}</option>
          `).join("")}
        </select>
      </label>
      <p>${sourceHint}</p>
    </div>
    <div class="compare-summary">
      ${Object.entries(diffLabels).map(([key, [label, tone]]) => `
        <div class="compare-stat ${tone}">
          <span>${label}</span>
          <strong>${diff[key].length.toLocaleString()}</strong>
        </div>
      `).join("")}
    </div>
  `;

  if (!totalChanges) {
    $("#fileList").innerHTML = `${selector}<div class="empty">两个版本没有可见差异</div>`;
  } else {
    $("#fileList").innerHTML = selector + Object.entries(diffLabels)
      .map(([key, [label]]) => compareSection(label, diff[key], key))
      .join("");
  }
  $("#compareVersionSelect")?.addEventListener("change", (event) => {
    state.compareVersion = event.target.value;
    renderList();
  });
  bindCardActions();
};

const compareSection = (label, items, type) => {
  const filtered = filterEntries(items);
  if (!filtered.length) return "";
  return `
    <section class="compare-section">
      <div class="compare-section-head">
        <strong>${label}</strong>
        <span>${filtered.length.toLocaleString()} 项</span>
      </div>
      ${filtered.slice(0, 300).map((item, index) => fileCard(compareCardItem(item, type, index, filtered.length))).join("")}
      ${filtered.length > 300 ? `<div class="empty compact">已显示前 300 项，可用搜索继续过滤</div>` : ""}
    </section>
  `;
};

const compareCardItem = (item, type, index, total) => {
  const [label] = diffLabels[type];
  const details = [];
  if (item.oldHash && item.hash && item.oldHash !== item.hash) details.push(`MD5: ${item.oldHash} -> ${item.hash}`);
  if (item.oldSize !== undefined && Number(item.oldSize || 0) !== Number(item.size || 0)) details.push(`大小: ${fmtBytes(item.oldSize)} -> ${fmtBytes(item.size)}`);
  return {
    ...item,
    badge: label,
    subtitle: details.length ? `${item.subtitle} / ${details.join(" / ")}` : item.subtitle,
    count: `${index + 1}/${total}`,
  };
};

const renderEndfieldArchive = () => {
  const rows = [
    {
      badge: "上游归档",
      title: "ak-endfield-api-archive",
      subtitle: "持续记录官方启动器 API 返回与文件镜像状态",
      hash: "GitHub",
      url: state.endfieldIndex.source,
    },
    {
      badge: "下载库",
      title: "Endfield API Archive",
      subtitle: "上游项目提供的版本与下载入口",
      hash: "Archive",
      url: state.endfieldIndex.source_site,
    },
    {
      badge: "官方接口",
      title: "Hypergryph Launcher API",
      subtitle: "国服官方渠道最新版本接口",
      hash: "Official",
      url: state.endfieldIndex.official_api,
    },
    {
      badge: "本站索引",
      title: "Endfield versions.json",
      subtitle: "本站生成的精简静态索引",
      hash: "JSON",
      url: "data/endfield/versions.json",
    },
  ];
  $("#fileList").innerHTML = rows.map((item, index) => fileCard({
    ...item,
    count: `${index + 1}/${rows.length}`,
  })).join("");
  bindCardActions();
};

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

const fileCard = (item) => {
  const preferredUrl = item.preferredUrl || item.url;
  const actions = item.officialUrl
    ? `
      <button class="icon-button copy-link" type="button" data-url="${escapeHtml(preferredUrl)}" title="复制当前可用链接">${icons.copy}<span>复制可用链接</span></button>
      <a class="icon-button ${item.officialAvailable ? "" : "stale-link"}" href="${escapeHtml(item.officialUrl)}" target="_blank" rel="noreferrer" title="${item.officialAvailable ? "上游探测时可用" : "上游曾标记不可用，实际状态可能变化"}">${icons.down}<span>官方${item.officialAvailable ? "" : "状态未知"}</span></a>
      ${item.mirrorUrl ? `<a class="icon-button mirror-link" href="${escapeHtml(item.mirrorUrl)}" target="_blank" rel="noreferrer" title="公开归档镜像">${icons.down}<span>归档镜像</span></a>` : ""}
    `
    : `
      <button class="icon-button copy-link" type="button" data-url="${escapeHtml(preferredUrl)}" title="复制链接">${icons.copy}<span>复制链接</span></button>
      <a class="icon-button" href="${escapeHtml(preferredUrl)}" target="_blank" rel="noreferrer" title="打开">${icons.down}<span>打开</span></a>
    `;
  return `
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
      <div class="file-actions">${actions}</div>
    </article>
  `;
};

const bindCardActions = () => {
  $$(".copy-link").forEach((button) => {
    button.addEventListener("click", () => copyText(button.dataset.url, "链接已复制"));
  });
};

const renderList = async () => {
  if (state.mode === "compare") {
    await renderCompare();
    return;
  }

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

  if (isEndfield()) {
    if (state.mode === "archive") {
      renderEndfieldArchive();
      return;
    }
    const entries = state.mode === "packages" ? endfieldPackageItems() : endfieldPatchItems();
    const filtered = filterEntries(entries);
    $("#fileList").innerHTML = filtered
      .map((entry, index) => fileCard({ ...entry, count: `${index + 1}/${filtered.length}` }))
      .join("") || `<div class="empty">该版本没有${state.mode === "packages" ? "完整包" : "更新补丁"}记录</div>`;
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

const ensureGameData = async (preferredVersion = null) => {
  if (isNte()) {
    const versions = nteVersions().sort((a, b) => compareVersions(b.version, a.version));
    state.version = versions.some((item) => item.version === preferredVersion) ? preferredVersion : versions[0]?.version || null;
    return;
  }
  if (isEndfield()) {
    const versions = endfieldSummaries().sort((a, b) => compareVersions(b.version, a.version));
    state.version = versions.some((item) => item.version === preferredVersion) ? preferredVersion : versions[0]?.version || null;
    return;
  }
  if (!state.hoyoVersions.has(state.gameId)) {
    const response = await fetch(`data/hoyo/${state.gameId}_versions.json`);
    state.hoyoVersions.set(state.gameId, await response.json());
  }
  const versions = hoyoSummaries()
    .filter((item) => item.package_items || item.update_items || item.has_chunk)
    .sort((a, b) => compareVersions(b.version, a.version));
  state.version = versions.some((item) => item.version === preferredVersion) ? preferredVersion : versions[0]?.version || null;
};

const renderNotice = () => {
  const notice = $("#notes");
  if (isNte()) {
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>数据来源</strong>
        <span>页面保存由异环官方启动器 CDN 清单解析出的 URL、校验信息与下载索引；解密流程与复现细节见仓库 README。</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="${escapeHtml(nteVersion()?.reslist_url || "#")}" target="_blank" rel="noreferrer">官方 ResList 清单</a>
        <a class="source-link" href="${REPOSITORY_URL}#nte-manifest-notes" target="_blank" rel="noreferrer">本站仓库 README</a>
      </div>
    `;
  } else if (isEndfield()) {
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>数据来源</strong>
        <span>上游项目持续归档终末地官方启动器 API。页面展示的是上游历史探测状态，并非实时检测；官方链接状态可能变化，归档镜像作为稳定备用入口。</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="${escapeHtml(state.endfieldIndex.source)}" target="_blank" rel="noreferrer">daydreamer-json/ak-endfield-api-archive</a>
      </div>
    `;
  } else {
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>数据来源</strong>
        <span>米家游戏数据迁移自 HoyoFiles 的公开版本清单接口，并在本站保存为静态索引；Chunk 视图只展示 Manifest 入口与统计信息。</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="https://hoyo-files.amarea.cn/" target="_blank" rel="noreferrer">hoyo-files.amarea.cn</a>
      </div>
    `;
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
  saveView();
};

Promise.all([
  fetch("./data/catalog.json").then((response) => response.json()),
  fetch("./data/hoyo/games.json").then((response) => response.json()),
  fetch("./data/endfield/index.json").then((response) => response.json()),
  fetch("./data/endfield/versions.json").then((response) => response.json()),
]).then(async ([nteCatalog, hoyoIndex, endfieldIndex, endfieldVersions]) => {
  state.nteCatalog = nteCatalog;
  state.hoyoIndex = hoyoIndex;
  state.endfieldIndex = endfieldIndex;
  state.endfieldVersions = endfieldVersions;
  const savedView = loadSavedView();
  if (allGames().some((game) => game.id === savedView.gameId)) {
    state.gameId = savedView.gameId;
  }
  state.mode = modesForGame().some(([mode]) => mode === savedView.mode)
    ? savedView.mode
    : modesForGame()[0][0];
  bindStaticActions();
  await ensureGameData(savedView.version);
  render();
});
