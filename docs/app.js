const state = {
  gameId: "nte",
  mode: "full",
  version: null,
  manualVersions: {},
  latestVersions: {},
  collapsedVersionGroups: {},
  compareVersion: null,
  diffFilter: "all",
  query: "",
  nteCatalog: null,
  hoyoIndex: null,
  endfieldIndex: null,
  endfieldVersions: null,
  wuwaIndex: null,
  wuwaVersions: {},
  wuwaVersionPromises: new Map(),
  arknightsIndex: null,
  arknightsVersions: null,
  androidIndex: null,
  hoyoLegacyCandidates: {},
  wuwaEntries: new Map(),
  wuwaFilePath: "",
  wuwaExpandedFile: "",
  hoyoVersions: new Map(),
  hoyoVersionPromises: new Map(),
  hoyoFileEntries: new Map(),
  hoyoFileVisible: 150,
  hoyoFilePath: "",
  hoyoExpandedFile: "",
  nteEntries: new Map(),
  nteFilePath: "",
  nteExpandedFile: "",
  chunkEntries: new Map(),
  nteAnalytics: null,
  nteAnalyticsPromise: null,
  endfieldAnalytics: null,
  endfieldAnalyticsPromise: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const VIEW_STORAGE_KEY = "game-cdn-archive:view";
const REPOSITORY_URL = "https://github.com/kuaichu/game-cdn-archive";
const HOYOFILES_API_BASE = "https://autopatch.amarea.cn/pkg_version";
const HOYO_FILE_PAGE_SIZE = 150;
const ASSET_VERSION = "20260706-hoyo-split";

const cacheBusted = (url) => {
  if (!url || /^https?:\/\//.test(url)) return url;
  return `${url}${url.includes("?") ? "&" : "?"}v=${ASSET_VERSION}`;
};

const fetchJson = (url) => fetch(cacheBusted(url)).then((response) => response.json());

const fetchOptionalJson = async (url) => {
  try {
    const response = await fetch(cacheBusted(url));
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
};

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
      manualVersions: state.manualVersions,
      latestVersions: state.latestVersions,
      collapsedVersionGroups: state.collapsedVersionGroups,
    }));
  } catch {
    // The page still works when storage is blocked or unavailable.
  }
};

const versionContextKey = (gameId = state.gameId, mode = state.mode) => `${gameId}:${mode}`;
const versionGroupKey = (family, gameId = state.gameId, mode = state.mode) => `${versionContextKey(gameId, mode)}:${family}`;

const preferredVersionForContext = (gameId = state.gameId, mode = state.mode) =>
  state.manualVersions?.[versionContextKey(gameId, mode)] || state.manualVersions?.[gameId] || null;

const rememberVersionSelection = (version = state.version) => {
  if (!version) return;
  state.manualVersions[versionContextKey()] = version;
};

const isVersionGroupCollapsed = (family) =>
  Boolean(state.collapsedVersionGroups?.[versionGroupKey(family)]);

const setVersionGroupCollapsed = (family, collapsed) => {
  const key = versionGroupKey(family);
  if (collapsed) {
    state.collapsedVersionGroups[key] = true;
  } else {
    delete state.collapsedVersionGroups[key];
  }
  saveView();
};

const selectVersionForContext = (versions, preferredVersion = null) => {
  const latest = versions[0]?.version || null;
  if (!latest) return null;
  const key = versionContextKey();
  const lastSeenLatest = state.latestVersions?.[key] || null;
  const hasNewLatest = lastSeenLatest && compareVersions(latest, lastSeenLatest) > 0;
  const preferredAvailable = versions.some((item) => item.version === preferredVersion);
  state.latestVersions[key] = latest;
  return hasNewLatest ? latest : preferredAvailable ? preferredVersion : latest;
};

const icons = {
  box: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 8-9-5-9 5 9 5 9-5Z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>',
  file: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/></svg>',
  folder: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6.5A2.5 2.5 0 0 1 5.5 4H9l2 2h7.5A2.5 2.5 0 0 1 21 8.5v9A2.5 2.5 0 0 1 18.5 20h-13A2.5 2.5 0 0 1 3 17.5Z"/></svg>',
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
  ["files", "文件清单"],
  ["updates", "更新包"],
  ["chunk", "Chunk 信息"],
  ["compare", "版本对比"],
];

const hoyoLegacyMode = ["legacy", "候选线索"];

const endfieldModes = [
  ["packages", "完整包"],
  ["patches", "更新补丁"],
  ["archive", "归档信息"],
  ["compare", "版本对比"],
];

const wuwaModes = [
  ["files", "文件清单"],
  ["patches", "更新路线"],
];

const arknightsModes = [
  ["packages", "完整包"],
];

const androidMode = ["android", "Android APK"];

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

const fmtKnownBytes = (bytes, fallback = "大小未知") => {
  const value = Number(bytes || 0);
  return value > 0 ? fmtBytes(value) : fallback;
};

const androidIcons = {
  aethergazer: "assets/icons/aethergazer.ico",
  arknights: "assets/icons/arknights.ico",
  bluearchive: "assets/icons/bluearchive.png",
  calabiyau: "assets/icons/calabiyau.png",
  gf2: "assets/icons/gf2.png",
  pns: "assets/icons/pns.png",
  reverse1999: "assets/icons/reverse1999.png",
  snowbreak: "assets/icons/snowbreak.svg",
};

const androidShortNames = {
  aethergazer: "SK",
  arknights: "AK",
  bluearchive: "BA",
  calabiyau: "KLB",
  gf2: "GF2",
  pns: "PNS",
  reverse1999: "1999",
  snowbreak: "CBJQ",
};

const parseDateValue = (value) => {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const text = String(value).trim();
  const zoneMatch = text.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2}) ([+-])(\d{2})(\d{2})$/);
  const normalized = zoneMatch
    ? `${zoneMatch[1]}T${zoneMatch[2]}${zoneMatch[3]}${zoneMatch[4]}:${zoneMatch[5]}`
    : text;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
};

const fmtDateTime = (value) => {
  if (!value) return "-";
  const date = parseDateValue(value);
  if (!date) return value;
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

const pcTimeLabel = (source) => source === "pc_package" || source === "pc_file" ? "文件时间" : "索引时间";

const wuwaVersionDate = (summary) => summary?.release_date || summary?.last_modified || "";

const fmtRelativeTime = (value) => {
  const date = parseDateValue(value);
  if (!date) return "-";
  const diffMs = Date.now() - date.getTime();
  const absMs = Math.abs(diffMs);
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  const rtf = new Intl.RelativeTimeFormat("zh-CN", { numeric: "auto" });
  if (absMs < hour) return rtf.format(Math.round(-diffMs / minute), "minute");
  if (absMs < day) return rtf.format(Math.round(-diffMs / hour), "hour");
  return rtf.format(Math.round(-diffMs / day), "day");
};

const newerDateValue = (current, candidate) => {
  const currentDate = parseDateValue(current);
  const candidateDate = parseDateValue(candidate);
  if (!candidateDate) return current || candidate || "";
  if (!currentDate || candidateDate > currentDate) return candidate;
  return current;
};

const compareVersions = (left, right) => {
  if (left === right) return 0;
  const leftParts = left.split(".").map(Number);
  const rightParts = right.split(".").map(Number);
  const length = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < length; index += 1) {
    const leftPart = Number.isFinite(leftParts[index]) ? leftParts[index] : -1;
    const rightPart = Number.isFinite(rightParts[index]) ? rightParts[index] : -1;
    const diff = leftPart - rightPart;
    if (diff !== 0) return diff;
  }
  return String(left).localeCompare(String(right));
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

const sideSections = ["home", "notes", "files", "commands"];

const setActiveSideLink = (sectionId) => {
  $$(".side-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.section === sectionId);
  });
};

const updateActiveSideLink = () => {
  const hashSection = location.hash.replace("#", "");
  if (sideSections.includes(hashSection)) {
    setActiveSideLink(hashSection);
    return;
  }

  const threshold = 24;
  const current = sideSections
    .map((id) => ({
      id,
      top: document.getElementById(id)?.getBoundingClientRect().top ?? Number.POSITIVE_INFINITY,
    }))
    .filter((item) => item.top <= threshold)
    .sort((a, b) => b.top - a.top)[0];
  setActiveSideLink(current?.id || "home");
};

const allGames = () => {
  const baseGames = [
    nteGame,
    ...(state.endfieldIndex?.game ? [state.endfieldIndex.game] : []),
    ...(state.arknightsIndex?.game ? [state.arknightsIndex.game] : []),
    ...(state.wuwaIndex?.game ? [state.wuwaIndex.game] : []),
    ...(state.hoyoIndex?.games || []).map((game) => ({
    ...game,
    subName: hoyoEnglishNames[game.id] || game.name,
    icon: `assets/icons/${game.id}.png`,
    kind: "hoyo",
    })),
  ];
  const knownIds = new Set(baseGames.map((game) => game.id));
  const androidOnlyGames = Object.entries(state.androidIndex?.games || {})
    .filter(([id]) => !knownIds.has(id))
    .map(([id, game]) => ({
      id,
      name: game.name || id,
      subName: game.subName || game.name || id,
      shortName: androidShortNames[id] || id.toUpperCase().slice(0, 3),
      icon: androidIcons[id] || `assets/icons/${id}.png`,
      kind: "android",
    }));
  return [...baseGames, ...androidOnlyGames];
};

const currentGame = () => allGames().find((game) => game.id === state.gameId) || nteGame;
const isNte = () => currentGame().kind === "nte";
const isEndfield = () => currentGame().kind === "endfield";
const isWuwa = () => currentGame().kind === "wuwa";
const isArknights = () => currentGame().kind === "arknights";
const isAndroidOnly = () => currentGame().kind === "android";
const androidGame = () => state.androidIndex?.games?.[state.gameId] || null;
const androidEntries = () => androidGame()?.versions || [];
const androidAvailability = (entry) => entry?.availability?.interpretation || null;
const androidAvailabilityState = (entry) => androidAvailability(entry)?.state || "";
const androidAvailabilityLabel = (entry) => androidAvailability(entry)?.display_label || (
  entry?.error || Number(entry?.status || 0) < 200 || Number(entry?.status || 0) >= 400 ? "链接失效" : "可用"
);
const androidEntryUnavailable = (entry) => {
  const state = androidAvailabilityState(entry);
  if (state) return state === "unavailable";
  return Boolean(entry?.error || Number(entry?.status || 0) < 200 || Number(entry?.status || 0) >= 400);
};
const androidSummaries = () => {
  const byVersion = new Map();
  androidEntries().forEach((entry) => {
    const row = byVersion.get(entry.version) || {
      version: entry.version,
      apk_count: 0,
      size: 0,
      known_size_count: 0,
      channels: [],
      status: entry.status,
      last_modified: entry.last_modified,
      updated_at: entry.updated_at || entry.last_modified,
      updated_at_source: entry.updated_at_source || (entry.last_modified ? "apk_last_modified" : ""),
      unavailable_count: 0,
    };
    row.apk_count += 1;
    if (Number(entry.size || 0) > 0) {
      row.size += Number(entry.size || 0);
      row.known_size_count += 1;
    }
    if (androidEntryUnavailable(entry)) {
      row.unavailable_count += 1;
    }
    if (entry.channel && !row.channels.includes(entry.channel)) row.channels.push(entry.channel);
    row.updated_at = newerDateValue(row.updated_at, entry.updated_at || entry.last_modified);
    row.last_modified = newerDateValue(row.last_modified, entry.last_modified);
    if (row.updated_at === entry.updated_at && entry.updated_at_source) {
      row.updated_at_source = entry.updated_at_source;
    }
    byVersion.set(entry.version, row);
  });
  return [...byVersion.values()];
};
const hasAndroidApks = () => androidSummaries().length > 0;
const hoyoLegacyPayload = () => state.hoyoLegacyCandidates?.[state.gameId] || null;
const hoyoLegacyRecords = () => hoyoLegacyPayload()?.records || [];
const hasHoyoLegacyCandidates = () => currentGame().kind === "hoyo" && hoyoLegacyRecords().length > 0;
const hoyoLegacySummaries = () => {
  const records = hoyoLegacyRecords();
  if (!records.length) return [];
  return [{
    version: "legacy",
    label: "候选线索",
    records_count: records.length,
    generated_at_from_path: records.map((record) => record.generated_at_from_path).filter(Boolean).sort()[0] || "",
    unavailable_count: records.filter((record) => Number(record.current?.status_code || 0) >= 400).length,
  }];
};
const modesForGame = () => {
  const modes = isAndroidOnly()
    ? []
    : isNte() ? nteModes : isEndfield() ? endfieldModes : isWuwa() ? wuwaModes : isArknights() ? arknightsModes : hoyoModes;
  const withLegacy = hasHoyoLegacyCandidates() ? [...modes, hoyoLegacyMode] : modes;
  return hasAndroidApks() ? [...withLegacy, androidMode] : withLegacy;
};

const nteVersions = () => state.nteCatalog.versions.filter((item) => item.status === 200 && item.full);
const nteVersion = () => state.nteCatalog.versions.find((item) => item.version === state.version);
const nteFiles = () => nteVersion()?.[state.mode];

const hoyoSummary = () => state.hoyoIndex.games.find((game) => game.id === state.gameId);
const hoyoVersionMap = () => state.hoyoVersions.get(state.gameId) || {};
const hoyoVersion = () => hoyoVersionMap()?.[state.version] || null;
const hoyoSummaries = () => hoyoSummary()?.versions || [];

const hoyoVersionUrl = (gameId, version) => (
  `data/hoyo/versions/${encodeURIComponent(gameId)}/${encodeURIComponent(version)}.json`
);

const loadHoyoVersion = async (version = state.version, gameId = state.gameId) => {
  if (!version || !gameId) return null;
  const cached = state.hoyoVersions.get(gameId) || {};
  if (cached[version]) return cached[version];
  const key = `${gameId}:${version}`;
  if (!state.hoyoVersionPromises.has(key)) {
    state.hoyoVersionPromises.set(key, fetchJson(hoyoVersionUrl(gameId, version)));
  }
  const row = await state.hoyoVersionPromises.get(key);
  const next = state.hoyoVersions.get(gameId) || {};
  next[version] = row;
  state.hoyoVersions.set(gameId, next);
  return row;
};

const endfieldVersion = () => state.endfieldVersions?.[state.version] || null;
const endfieldSummaries = () => state.endfieldIndex?.versions || [];

const wuwaVersion = (version = state.version) => state.wuwaVersions?.[version] || null;
const wuwaSummaries = () => state.wuwaIndex?.versions || [];
const arknightsVersion = () => state.arknightsVersions?.[state.version] || null;
const arknightsSummaries = () => state.arknightsIndex?.versions || [];
const androidVersion = () => androidSummaries().find((item) => item.version === state.version) || null;
const androidVersionEntries = () => androidEntries().filter((item) => item.version === state.version);

const hoyoPackageUrl = (row) => row?.game?.full?.url || row?.game?.segments?.[0]?.url || "";

const hoyoDecompressedPath = (row) => {
  if (row?.decompressed_path) return row.decompressed_path;
  if (state.gameId !== "hkrpg") return "";

  const url = hoyoPackageUrl(row);
  if (!url) return "";
  if (url.includes("/PC/download/")) return `${url.split("/PC/download/")[0]}/PC/unzip`;
  if (url.includes("/PC/")) return `${url.split("/PC/")[0]}/PC/unzip`;
  if (/\/StarRail_[^/]+\.zip$/.test(url)) return `${url.slice(0, url.lastIndexOf("/"))}/unzip`;
  return "";
};

const hoyoDistributionProfile = (summary, version = null) => {
  const row = version || hoyoVersionMap()?.[summary?.version] || {};
  const path = String(hoyoDecompressedPath(row) || "");
  const hasPackage = Boolean(summary?.package_items || row?.game?.full || row?.game?.segments?.length);
  const hasDirect = Boolean(summary?.has_decompressed_path || path);
  const hasChunk = Boolean(summary?.has_chunk || row?.chunk);

  if (state.gameId === "hkrpg") {
    if (hasPackage && hasDirect && hasChunk) return { label: "三轨并行", color: "violet", detail: "压缩包 + unzip 文件树 + Chunk" };
    if (hasPackage && hasDirect && path.includes("/unzip")) return { label: "unzip 双轨", color: "green", detail: "压缩包 + 官方 unzip 文件树" };
    if (hasDirect && path.includes("/unzip")) return { label: "unzip 直链", color: "green", detail: "官方 unzip 文件树" };
  }

  if (hasPackage && hasDirect && hasChunk) return { label: "三轨并行", color: "violet", detail: "压缩包 + 散文件直链 + Chunk" };
  if (hasChunk && !hasPackage && !hasDirect) return { label: "Chunk 独占", color: "violet", detail: "Chunk Manifest 文件分发" };
  if (hasChunk && hasDirect) return { label: "直链 + Chunk", color: "violet", detail: "散文件直链 + Chunk" };
  if (hasChunk && hasPackage) return { label: "压缩包 + Chunk", color: "violet", detail: "压缩包 + Chunk" };
  if (path.includes("/pc_test/")) return { label: "实验直链", color: "amber", detail: "pc_test 文件树 + 压缩包" };
  if (path.includes("/pc_mihoyo/")) return { label: "正式文件树", color: "green", detail: "pc_mihoyo 文件树 + 压缩包" };
  if (path.includes("/ScatteredFiles")) return { label: "ScatteredFiles", color: "green", detail: "ScatteredFiles 散文件 + 压缩包" };
  if (hasPackage && hasDirect) return { label: "压缩包 + 直链", color: "green", detail: "压缩包 + 官方散文件直链" };
  if (hasDirect) return { label: "直链文件", color: "green", detail: "官方散文件直链" };
  if (hasPackage) return { label: "整包分发", color: "blue", detail: "完整压缩包分发" };
  return { label: "索引记录", color: "slate", detail: "仅保存版本索引" };
};

const asArray = (value) => Array.isArray(value) ? value : value ? [value] : [];

const hoyoDownloadItems = (row) => {
  const items = [];
  const game = row?.game || {};
  items.push(...asArray(game.full), ...asArray(game.segments));
  Object.values(row?.voice || {}).forEach((voice) => items.push(...asArray(voice)));
  Object.values(row?.update || {}).forEach((patch) => {
    items.push(...asArray(patch?.game));
    Object.values(patch?.voice || {}).forEach((voice) => items.push(...asArray(voice)));
  });
  return items.filter((item) => item && typeof item === "object" && item.url);
};

const hoyoUnavailableCount = (version) => {
  const summary = hoyoSummaries().find((item) => item.version === version);
  if (summary && Number.isFinite(Number(summary.unavailable_items))) {
    return Number(summary.unavailable_items || 0);
  }
  const row = hoyoVersionMap()?.[version];
  return hoyoDownloadItems(row).filter((item) => Number(item.size || 0) <= 0).length;
};

const endfieldOfficialStatus = (version) => {
  const row = state.endfieldVersions?.[version];
  const items = [...(row?.packages || []), ...(row?.patches || [])];
  const officialExpired = items.filter((item) => item.official_url && item.official_available === false);
  if (!officialExpired.length) return null;
  const mirrored = officialExpired.filter((item) => item.mirror_url || item.preferred_url).length;
  return mirrored === officialExpired.length
    ? { color: "amber", label: "官方过期" }
    : { color: "red", label: `失效 ${officialExpired.length}` };
};

const versionAvailabilityCap = (item) => {
  if (state.mode === "android") {
    const count = Number(item.unavailable_count || 0);
    if (!count) return "";
    const label = count >= Number(item.apk_count || 0) ? "链接失效" : `含失效 ${count}`;
    return `<span class="cap red">${label}</span>`;
  }
  if (isEndfield()) {
    const status = endfieldOfficialStatus(item.version);
    return status ? `<span class="cap ${status.color}">${status.label}</span>` : "";
  }
  if (!isNte() && !isWuwa()) {
    const count = hoyoUnavailableCount(item.version);
    if (count) return `<span class="cap red">${count === 1 ? "链接失效" : `含失效 ${count}`}</span>`;
  }
  return "";
};

const availableSummaries = () => {
  if (state.mode === "android") return androidSummaries();
  if (state.mode === "legacy") return hoyoLegacySummaries();
  if (isNte()) return nteVersions();
  if (isEndfield()) return endfieldSummaries();
  if (isWuwa()) return wuwaSummaries();
  if (isArknights()) return arknightsSummaries();
  return hoyoSummaries().filter((item) => item.package_items || item.update_items || item.has_chunk);
};

const availableVersions = () => availableSummaries()
  .map((item) => item.version)
  .sort(compareVersions);

const latestByVersion = (rows, predicate = () => true) => rows
  .filter((item) => item?.version && predicate(item))
  .slice()
  .sort((a, b) => compareVersions(b.version, a.version))[0] || null;

const currentGameSyncInfo = () => {
  const game = currentGame();
  const androidLatest = latestByVersion(androidSummaries());
  if (isNte()) {
    const latest = latestByVersion(nteVersions());
    return {
      game,
      source: "异环官方启动器 ResList",
      checked: state.nteCatalog?.last_checked_at || state.nteCatalog?.generated_at,
      updated: state.nteCatalog?.generated_at,
      latest: latest?.version,
      detail: `${latest?.full?.items || 0} 个完整文件 / ${fmtBytes(latest?.full?.bytes || 0)}`,
      android: androidLatest?.version,
    };
  }
  if (isEndfield()) {
    const latest = latestByVersion(endfieldSummaries());
    return {
      game,
      source: "daydreamer-json 上游归档",
      checked: state.endfieldIndex?.last_checked_at || state.endfieldIndex?.generated_from_observation,
      updated: state.endfieldIndex?.generated_from_observation,
      latest: latest?.version,
      detail: `${latest?.package_items || 0} 个完整分卷 / ${fmtBytes(latest?.packed_size || 0)}`,
      android: androidLatest?.version,
    };
  }
  if (isArknights()) {
    const latest = latestByVersion(arknightsSummaries());
    return {
      game,
      source: "鹰角官方启动器 API",
      checked: state.arknightsIndex?.last_checked_at || state.arknightsIndex?.generated_at,
      updated: state.arknightsIndex?.generated_at,
      latest: latest?.version,
      detail: `${latest?.package_items || 0} 个完整分卷 / ${fmtBytes(latest?.packed_size || 0)}`,
      android: androidLatest?.version,
    };
  }
  if (isWuwa()) {
    const latest = latestByVersion(wuwaSummaries());
    return {
      game,
      source: "鸣潮官方启动器索引",
      checked: state.wuwaIndex?.last_checked_at || state.wuwaIndex?.generated_at,
      updated: state.wuwaIndex?.generated_at,
      latest: latest?.version,
      detail: `${(latest?.file_count || 0).toLocaleString()} 个文件 / ${fmtBytes(latest?.size || 0)}`,
      android: androidLatest?.version,
    };
  }
  const latest = latestByVersion(hoyoSummaries().filter((item) => item.package_items || item.update_items || item.has_chunk));
  return {
    game,
    source: "HoyoFiles 公开版本清单",
    checked: state.hoyoIndex?.last_checked_at || state.hoyoIndex?.generated_at,
    updated: state.hoyoIndex?.generated_at,
    latest: latest?.version,
    detail: `${latest?.package_items || 0} 个压缩包 / ${latest?.update_items || 0} 个更新包`,
    android: androidLatest?.version,
  };
};

const defaultCompareVersion = () => {
  const versions = availableVersions();
  const currentIndex = versions.indexOf(state.version);
  if (currentIndex > 0) return versions[currentIndex - 1];
  return versions.find((version) => version !== state.version) || null;
};

const versionFamily = (version) => {
  if (version === "legacy") return "候选线索";
  const parts = version.split(".");
  return isNte() || isEndfield() ? parts.slice(0, 2).join(".") : `${parts[0]}.x`;
};

const commandFor = () => {
  if (state.mode === "compare") {
    return "版本对比模式不需要下载命令";
  }
  if (state.mode === "legacy") {
    return "候选线索模式不生成 aria2 列表；请在卡片中逐条复制或打开原始官方 CDN URL";
  }
  if (state.mode === "android") {
    const links = androidGame()?.links?.[state.version];
    return links?.aria2
      ? `aria2c -c -x16 -s16 -i ${links.aria2}`
      : "当前游戏没有 Android APK 直链记录";
  }
  if (isNte()) {
    return `python scripts\\nte_downloader.py download ${state.version} --download-root downloads --workers 4 --pack --pack-dir packages`;
  }
  if (isEndfield()) {
    return `aria2c -c -x16 -s16 data/endfield/lists/${state.version}_${state.mode === "patches" ? "patches" : "packages"}.aria2.txt`;
  }
  if (isArknights()) {
    return `aria2c -c -x16 -s16 -i data/arknights/lists/${state.version}_packages.aria2.txt`;
  }
  if (isWuwa()) {
    return state.mode === "files"
      ? `aria2c -c -x16 -s16 -i data/wuwa/lists/${state.version}-files.aria2.txt`
      : "更新路线模式用于查看旧版本到当前版本的官方索引";
  }
  return `aria2c -c -x16 -s16 <从页面复制对应 URL 列表>`;
};

const psSingleQuote = (value) => String(value ?? "").replace(/'/g, "''");

const downloadTextFile = (filename, text, type = "text/plain;charset=utf-8") => {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const nteDownloadScript = (version, entries) => {
  const root = `NTE_${version}_full`;
  const items = entries.map((entry) => {
    const path = String(entry.filename || entry.subtitle || entry.object || "").replace(/\\/g, "/").replace(/^\/+/, "");
    return `  @{ Url='${psSingleQuote(entry.url)}'; Mirror='${psSingleQuote(nteCdn2Url(entry.url))}'; Path='${psSingleQuote(path)}'; Size=${Number(entry.filesize || entry.size || 0)}; Md5='${psSingleQuote(entry.md5 || entry.hash || "")}' }`;
  }).join(",\n");
  return `# Game CDN Archive - NTE ${version} full download
# 在 PowerShell 中运行：powershell -ExecutionPolicy Bypass -File .\\NTE_${version}_full_download.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = Join-Path (Get-Location) '${psSingleQuote(root)}'
$Items = @(
${items}
)

New-Item -ItemType Directory -Force -Path $Root | Out-Null

$aria2 = Get-Command aria2c -ErrorAction SilentlyContinue
if ($aria2) {
  $InputFile = Join-Path $Root 'download.aria2.txt'
  $Lines = New-Object System.Collections.Generic.List[string]
  foreach ($Item in $Items) {
    $Target = Join-Path $Root $Item.Path
    $Dir = Split-Path -Parent $Target
    $Out = Split-Path -Leaf $Target
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    $Lines.Add($Item.Url)
    if ($Item.Mirror) { $Lines.Add($Item.Mirror) }
    $Lines.Add('  dir=' + $Dir)
    $Lines.Add('  out=' + $Out)
  }
  [System.IO.File]::WriteAllLines($InputFile, $Lines, [System.Text.UTF8Encoding]::new($false))
  & $aria2.Source -c -x16 -s16 -j4 -i $InputFile
  exit $LASTEXITCODE
}

foreach ($Item in $Items) {
  $Target = Join-Path $Root $Item.Path
  $Dir = Split-Path -Parent $Target
  New-Item -ItemType Directory -Force -Path $Dir | Out-Null

  if ((Test-Path $Target) -and ((Get-Item $Target).Length -eq [int64]$Item.Size)) {
    Write-Host ('Skip ' + $Item.Path)
    continue
  }

  Write-Host ('Download ' + $Item.Path)
  $Downloaded = $false
  foreach ($Url in @($Item.Url, $Item.Mirror)) {
    if (-not $Url) { continue }
    try {
      Invoke-WebRequest -Uri $Url -OutFile $Target
      $Downloaded = $true
      break
    } catch {
      Write-Warning ('Failed ' + $Url)
    }
  }
  if (-not $Downloaded) {
    throw ('Download failed: ' + $Item.Path)
  }
}

Write-Host 'Download complete.'
`;
};

const downloadNteScript = async () => {
  if (!isNte() || state.mode !== "full") return;
  const entries = await loadNteEntries(state.version, "full");
  if (!entries.length) {
    showToast("当前版本没有完整文件清单");
    return;
  }
  downloadTextFile(`NTE_${state.version}_full_download.ps1`, nteDownloadScript(state.version, entries));
  showToast("下载脚本已生成");
};

const wuwaDownloadScript = (version, entries) => {
  const root = `WutheringWaves_${version}`;
  const items = entries.map((entry) => {
    const path = String(entry.dest || entry.name || "").replace(/\\/g, "/").replace(/^\/+/, "");
    const urls = (entry.urls?.length ? entry.urls : [entry.url])
      .filter(Boolean)
      .map((url) => `'${psSingleQuote(url)}'`)
      .join(", ");
    return `  @{ Urls=@(${urls}); Path='${psSingleQuote(path)}'; Size=${Number(entry.size || 0)}; Md5='${psSingleQuote(entry.md5 || "")}' }`;
  }).join(",\n");
  return `# Game CDN Archive - Wuthering Waves ${version} full download
# 在 PowerShell 中运行：powershell -ExecutionPolicy Bypass -File .\\WutheringWaves_${version}_download.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = Join-Path (Get-Location) '${psSingleQuote(root)}'
$Items = @(
${items}
)

New-Item -ItemType Directory -Force -Path $Root | Out-Null

$aria2 = Get-Command aria2c -ErrorAction SilentlyContinue
if ($aria2) {
  $InputFile = Join-Path $Root 'download.aria2.txt'
  $Lines = New-Object System.Collections.Generic.List[string]
  foreach ($Item in $Items) {
    $Target = Join-Path $Root $Item.Path
    $Dir = Split-Path -Parent $Target
    $Out = Split-Path -Leaf $Target
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    foreach ($Url in $Item.Urls) { $Lines.Add($Url) }
    $Lines.Add('  dir=' + $Dir)
    $Lines.Add('  out=' + $Out)
    if ($Item.Md5) { $Lines.Add('  checksum=md5=' + $Item.Md5) }
  }
  [System.IO.File]::WriteAllLines($InputFile, $Lines, [System.Text.UTF8Encoding]::new($false))
  & $aria2.Source -c -x16 -s16 -j4 -i $InputFile
  exit $LASTEXITCODE
}

foreach ($Item in $Items) {
  $Target = Join-Path $Root $Item.Path
  $Dir = Split-Path -Parent $Target
  New-Item -ItemType Directory -Force -Path $Dir | Out-Null

  if ((Test-Path $Target) -and ((Get-Item $Target).Length -eq [int64]$Item.Size)) {
    Write-Host ('Skip ' + $Item.Path)
    continue
  }

  Write-Host ('Download ' + $Item.Path)
  $Downloaded = $false
  foreach ($Url in $Item.Urls) {
    try {
      Invoke-WebRequest -Uri $Url -OutFile $Target
      $Downloaded = $true
      break
    } catch {
      Write-Warning ('Failed ' + $Url)
    }
  }
  if (-not $Downloaded) {
    throw ('Download failed: ' + $Item.Path)
  }
}

Write-Host 'Download complete.'
`;
};

const downloadWuwaScript = async () => {
  if (!isWuwa() || state.mode !== "files") return;
  const entries = await loadWuwaEntries();
  if (!entries.length) {
    showToast("当前版本没有文件清单");
    return;
  }
  downloadTextFile(`WutheringWaves_${state.version}_download.ps1`, wuwaDownloadScript(state.version, entries));
  showToast("下载脚本已生成");
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
    state.hoyoFileVisible = HOYO_FILE_PAGE_SIZE;
    state.hoyoExpandedFile = "";
    state.nteExpandedFile = "";
    state.wuwaExpandedFile = "";
    renderList();
  });

  $("#copyCommandBtn").addEventListener("click", () => copyText(commandFor(), "命令已复制"));
  $("#scriptButton").addEventListener("click", () => {
    const task = isWuwa() ? downloadWuwaScript() : downloadNteScript();
    Promise.resolve(task).catch((error) => {
      console.error(error);
      showToast(`脚本生成失败：${error.message}`);
    });
  });

  $$(".side-link").forEach((link) => {
    link.addEventListener("click", () => setActiveSideLink(link.dataset.section));
  });
  window.addEventListener("hashchange", updateActiveSideLink);
  window.addEventListener("scroll", updateActiveSideLink, { passive: true });
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
      state.hoyoFileVisible = HOYO_FILE_PAGE_SIZE;
      state.hoyoFilePath = "";
      state.hoyoExpandedFile = "";
      state.nteFilePath = "";
      state.nteExpandedFile = "";
      state.wuwaFilePath = "";
      state.wuwaExpandedFile = "";
      $("#fileSearch").value = "";
      await ensureGameData(preferredVersionForContext(state.gameId, state.mode));
      state.compareVersion = null;
      state.diffFilter = "all";
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
    button.addEventListener("click", async () => {
      state.mode = button.dataset.mode;
      state.compareVersion = null;
      state.diffFilter = "all";
      state.hoyoFileVisible = HOYO_FILE_PAGE_SIZE;
      state.hoyoFilePath = "";
      state.hoyoExpandedFile = "";
      state.nteFilePath = "";
      state.nteExpandedFile = "";
      state.wuwaFilePath = "";
      state.wuwaExpandedFile = "";
      await ensureGameData(preferredVersionForContext(state.gameId, state.mode));
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
    .map(([family, items]) => {
      const collapsed = isVersionGroupCollapsed(family);
      const titleSuffix = state.mode === "legacy" ? "" : isNte() || isEndfield() ? "大版本" : "版本";
      const countLabel = state.mode === "legacy" ? `${items[0]?.records_count || items.length} 条线索` : `${items.length} 个可用版本`;
      return `
      <div class="version-group ${collapsed ? "collapsed" : ""}">
        <button class="version-group-head" type="button" data-family="${family}" aria-expanded="${!collapsed}" title="${collapsed ? "展开" : "收纳"} ${family} 版本">
          <span class="group-title">
            <span class="group-chevron" aria-hidden="true"></span>
            <strong>${escapeHtml(`${family}${titleSuffix ? ` ${titleSuffix}` : ""}`)}</strong>
          </span>
          <span class="group-meta">${escapeHtml(countLabel)}</span>
        </button>
        <div class="version-group-body" ${collapsed ? "hidden" : ""}>
          ${items.map((item) => versionButton(item)).join("")}
        </div>
      </div>
    `;
    })
    .join("");

  $$(".version-group-head").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const family = button.dataset.family;
      const collapsed = button.getAttribute("aria-expanded") === "true";
      setVersionGroupCollapsed(family, collapsed);
      renderVersionMenu();
    });
  });

  $$(".version-row").forEach((button) => {
    button.addEventListener("click", async () => {
      state.version = button.dataset.version;
      rememberVersionSelection();
      state.compareVersion = null;
      state.diffFilter = "all";
      state.hoyoFileVisible = HOYO_FILE_PAGE_SIZE;
      state.hoyoFilePath = "";
      state.hoyoExpandedFile = "";
      state.nteFilePath = "";
      state.nteExpandedFile = "";
      state.wuwaFilePath = "";
      state.wuwaExpandedFile = "";
      $("#versionMenu").hidden = true;
      $("#selectButton").setAttribute("aria-expanded", "false");
      if (isWuwa()) {
        await loadWuwaVersion();
      } else if (currentGame().kind === "hoyo") {
        await loadHoyoVersion();
      }
      render();
    });
  });
};

const versionButton = (item) => {
  if (state.mode === "legacy") {
    return `
      <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
        <span class="version-number">${escapeHtml(item.label || item.version)}</span>
        <span class="caps">
          <span class="cap amber">${Number(item.records_count || 0).toLocaleString()} 条</span>
          <span class="cap slate">${fmtDateTime(item.generated_at_from_path)}</span>
          <span class="cap red">${Number(item.unavailable_count || 0).toLocaleString()} 个 404</span>
          <span class="cap violet">未确认版本</span>
        </span>
      </button>
    `;
  }
  const family = item.version.split(".").slice(0, 2).join(".");
  const isBase = item.version === `${family}.0`;
  if (state.mode === "android") {
    return `
      <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
        <span class="version-number">${item.version}</span>
        <span class="caps">
          <span class="cap green">APK</span>
          <span class="cap blue">${Number(item.apk_count || 0).toLocaleString()} 个包</span>
          <span class="cap green">${escapeHtml((item.channels || []).join(" / ") || "官方渠道")}</span>
          <span class="cap slate">${fmtDateTime(item.updated_at || item.last_modified)}</span>
          <span class="cap slate">${fmtKnownBytes(item.size)}</span>
          ${versionAvailabilityCap(item)}
        </span>
      </button>
    `;
  }
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
          ${versionAvailabilityCap(item)}
        </span>
      </button>
    `;
  }
  if (isWuwa()) {
    const versionDate = wuwaVersionDate(item);
    return `
      <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
        <span class="version-number">${item.version}</span>
        <span class="caps">
          ${versionDate ? `<span class="cap slate">${fmtDateTime(versionDate)}</span>` : ""}
          <span class="cap blue">${Number(item.file_count || 0).toLocaleString()} 个文件</span>
          <span class="cap green">${item.cdn_count || 0} CDN</span>
          ${item.patch_routes ? `<span class="cap amber">${item.patch_routes} 条更新路线</span>` : ""}
          ${item.release_stage === "preload" ? '<span class="cap amber">预下载</span>' : item.source_note ? '<span class="cap slate">历史索引</span>' : '<span class="cap violet">当前索引</span>'}
        </span>
      </button>
    `;
  }
  if (isArknights()) {
    return `
      <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
        <span class="version-number">${item.version}</span>
        <span class="caps">
          <span class="cap blue">${item.package_items || 0} 个分卷</span>
          <span class="cap green">${fmtBytes(item.packed_size || 0)}</span>
          <span class="cap violet">官方接口</span>
        </span>
      </button>
    `;
  }
  const profile = hoyoDistributionProfile(item);
  return `
    <button class="version-row ${item.version === state.version ? "selected" : ""}" type="button" data-version="${item.version}">
      <span class="version-number">${item.version}</span>
      <span class="caps">
        ${item.last_modified ? `<span class="cap slate">${fmtDateTime(item.last_modified)}</span>` : ""}
        <span class="cap ${profile.color}">${profile.label}</span>
        ${item.update_items ? '<span class="cap amber">更新包</span>' : ""}
        ${versionAvailabilityCap(item)}
      </span>
    </button>
  `;
};

const renderStats = () => {
  const stats = state.mode === "legacy"
    ? hoyoLegacyStats()
    : state.mode === "android"
    ? androidStats()
    : isNte() ? nteStats() : isEndfield() ? endfieldStats() : isWuwa() ? wuwaStats() : isArknights() ? arknightsStats() : hoyoStats();
  $("#stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join("");
};

const renderSyncStatus = () => {
  const panel = $("#syncStatus");
  if (state.mode === "android") {
    panel.hidden = true;
    panel.innerHTML = "";
    return;
  }
  panel.hidden = false;
  const current = currentGameSyncInfo();
  const checkedAt = current.checked || current.updated;
  const checkedText = checkedAt
    ? fmtRelativeTime(checkedAt)
    : "-";
  panel.innerHTML = `
    <div class="sync-current">
      <div class="sync-current-head">
        <span class="sync-pulse" aria-hidden="true"></span>
        <div>
          <p class="kicker">Sync Status</p>
          <h2>${escapeHtml(current.game.name)} 最新归档</h2>
        </div>
      </div>
      <div class="sync-current-grid">
        <div>
          <span>最新 PC 版本</span>
          <strong>${escapeHtml(current.latest || "-")}</strong>
        </div>
        <div>
          <span>网页同步</span>
          <strong>${fmtDateTime(checkedAt)}</strong>
          <small>${checkedText}</small>
        </div>
        <div>
          <span>来源</span>
          <strong>${escapeHtml(current.source)}</strong>
          <small>${escapeHtml(current.detail)}</small>
        </div>
        <div>
          <span>Android 留档</span>
          <strong>${escapeHtml(current.android || "暂无")}</strong>
          <small>${current.android ? "已记录 APK 直链" : "当前游戏未记录 APK"}</small>
        </div>
      </div>
    </div>
  `;
};

const androidStats = () => {
  const entry = androidVersion();
  const entries = androidVersionEntries();
  const labels = [...new Set(entries.map(androidAvailabilityLabel).filter(Boolean))];
  return [
    ["当前版本", state.version],
    ["平台", "Android"],
    ["APK 数", `${entries.length.toLocaleString()} 个`],
    ["渠道", entry?.channels?.join(" / ") || "-"],
    ["更新时间", fmtDateTime(entry?.updated_at || entry?.last_modified)],
    ["APK 大小", fmtKnownBytes(entry?.size)],
    ["可用性", labels.join(" / ") || "-"],
    ["状态", entry?.status ? `HTTP ${entry.status}` : "-"],
  ];
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

const arknightsStats = () => {
  const summary = arknightsSummaries().find((item) => item.version === state.version);
  const version = arknightsVersion();
  return [
    ["当前版本", state.version],
    ["归档时间", fmtDateTime(summary?.observed_at)],
    ["完整分卷", `${summary?.package_items || 0} 个 / ${fmtBytes(summary?.packed_size || 0)}`],
    ["接口体积", fmtBytes(summary?.unpacked_size || 0)],
    ["文件校验", version?.game_files_md5 ? "game_files_md5" : "无"],
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
  const version = hoyoVersion();
  const profile = hoyoDistributionProfile(summary, version);
  const decompressedPath = hoyoDecompressedPath(version);
  const stats = [
    ["当前版本", state.version],
    ["分发架构", profile.label],
    ["压缩包", `${summary?.package_items || 0} 个`],
    ["散文件直链", decompressedPath ? "可用" : "无"],
    ["Chunk", version?.chunk ? version.chunk.tag || "可用" : "无"],
  ];
  if (summary?.last_modified) {
    stats.splice(2, 0, [pcTimeLabel(summary.last_modified_source), fmtDateTime(summary.last_modified)]);
  }
  return stats;
};

const hoyoLegacyStats = () => {
  const payload = hoyoLegacyPayload();
  const records = hoyoLegacyRecords();
  const firstGenerated = records.map((record) => record.generated_at_from_path).filter(Boolean).sort()[0] || "";
  const platforms = [...new Set(records.map((record) => record.platform).filter(Boolean))];
  const unavailable = records.filter((record) => Number(record.current?.status_code || 0) >= 400).length;
  return [
    ["当前视图", "候选线索"],
    ["来源游戏", payload?.game_name || currentGame().name],
    ["候选资源", `${records.length.toLocaleString()} 条`],
    ["平台", platforms.join(" / ") || "-"],
    ["路径时间", fmtDateTime(firstGenerated)],
    ["当前状态", unavailable ? `${unavailable} 个 404` : "待确认"],
  ];
};

const wuwaStats = () => {
  const summary = wuwaSummaries().find((item) => item.version === state.version);
  const versionDate = wuwaVersionDate(summary);
  const stats = [
    ["当前版本", state.version],
    ["区服", `${summary?.region?.toUpperCase() || "-"} ${summary?.channel || "-"}`],
    ["文件数", `${(summary?.file_count || 0).toLocaleString()} 个`],
    ["总大小", fmtBytes(summary?.size || 0)],
    ["CDN", `${summary?.cdn_count || 0} 个 / 更新路线 ${summary?.patch_routes || 0} 条`],
  ];
  if (versionDate) {
    const label = summary?.release_date_source === "tomyjan_git_first_added"
      ? "归档时间"
      : pcTimeLabel(summary?.last_modified_source);
    stats.splice(2, 0, [label, fmtDateTime(versionDate)]);
  }
  return stats;
};


const renderLinks = () => {
  const scriptButton = $("#scriptButton");
  scriptButton.hidden = true;

  if (state.mode === "android") {
    const links = androidGame()?.links?.[state.version];
    const disabled = !links;
    $("#urlsLink").classList.toggle("disabled", disabled);
    $("#aria2Link").classList.toggle("disabled", disabled);
    $("#jsonLink").classList.toggle("disabled", disabled);
    $("#urlsLink").href = links?.urls || "#";
    $("#aria2Link").href = links?.aria2 || "#";
    $("#jsonLink").href = links?.json || "data/android/index.json";
    return;
  }
  scriptButton.disabled = true;
  if (state.mode === "compare") {
    $("#urlsLink").classList.add("disabled");
    $("#aria2Link").classList.add("disabled");
    $("#jsonLink").classList.add("disabled");
    $("#urlsLink").href = "#";
    $("#aria2Link").href = "#";
    $("#jsonLink").href = "#";
    return;
  }

  if (state.mode === "legacy") {
    $("#urlsLink").classList.add("disabled");
    $("#aria2Link").classList.add("disabled");
    $("#jsonLink").classList.remove("disabled");
    $("#urlsLink").href = "#";
    $("#aria2Link").href = "#";
    $("#jsonLink").href = `data/hoyo/${state.gameId}_legacy_candidates.json`;
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
    scriptButton.hidden = disabled || state.mode !== "full";
    scriptButton.disabled = disabled || state.mode !== "full";
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

  if (isArknights()) {
    const links = arknightsVersion()?.links?.packages;
    const disabled = !links;
    $("#urlsLink").classList.toggle("disabled", disabled);
    $("#aria2Link").classList.toggle("disabled", disabled);
    $("#jsonLink").classList.remove("disabled");
    $("#urlsLink").href = links?.urls || "#";
    $("#aria2Link").href = links?.aria2 || "#";
    $("#jsonLink").href = links?.json || "data/arknights/versions.json";
    return;
  }

  if (isWuwa()) {
    const links = state.mode === "patches" ? wuwaVersion()?.links?.patches : wuwaVersion()?.links?.files;
    const disabled = !links;
    $("#urlsLink").classList.toggle("disabled", disabled);
    $("#aria2Link").classList.toggle("disabled", disabled);
    $("#jsonLink").classList.remove("disabled");
    $("#urlsLink").href = links?.urls || "#";
    $("#aria2Link").href = links?.aria2 || "#";
    $("#jsonLink").href = links?.json || `data/wuwa/versions/${encodeURIComponent(state.version)}.json`;
    scriptButton.hidden = disabled;
    scriptButton.disabled = disabled;
    return;
  }

  $("#urlsLink").classList.add("disabled");
  $("#aria2Link").classList.add("disabled");
  $("#urlsLink").href = "#";
  $("#aria2Link").href = "#";
  $("#jsonLink").href = state.mode === "files"
    ? hoyoFileListUrl(state.version)
    : hoyoVersionUrl(state.gameId, state.version);
  $("#jsonLink").classList.remove("disabled");
};

const renderPanelTitle = () => {
  const modeLabel = modesForGame().find(([id]) => id === state.mode)?.[1] || "文件列表";
  const displayVersion = state.mode === "legacy" ? "候选线索" : state.version || "-";
  $("#selectedVersion").textContent = displayVersion;
  $("#copyCommandBtn").innerHTML = `${icons.copy}<span>复制下载命令</span>`;
  $("#commandText").textContent = commandFor();
  $("#panelKicker").textContent = state.mode === "android"
    ? "Android APK"
    : state.mode === "legacy" ? "Historical candidates"
    : isNte() ? "NTE files" : isEndfield() ? "Endfield files" : isWuwa() ? "Wuwa files" : isArknights() ? "Arknights packages" : "Hoyo files";
  $("#panelTitle").textContent = state.mode === "legacy" ? displayVersion : `${displayVersion} ${modeLabel}`;
};

const loadNteEntries = async (version = state.version, mode = state.mode) => {
  if (mode === "reslist" || mode === "compare") mode = "full";
  const row = state.nteCatalog.versions.find((item) => item.version === version);
  const files = row?.[mode];
  if (!files?.json) return [];
  const key = `${version}:${mode}`;
  if (!state.nteEntries.has(key)) {
    state.nteEntries.set(key, await fetchJson(files.json));
  }
  return state.nteEntries.get(key);
};

const loadWuwaEntries = async (version = state.version) => {
  const row = await loadWuwaVersion(version);
  const fileList = row?.links?.files?.json;
  if (!fileList) return [];
  const key = `${version}:files`;
  if (!state.wuwaEntries.has(key)) {
    state.wuwaEntries.set(key, await fetchJson(fileList));
  }
  return state.wuwaEntries.get(key);
};

const loadWuwaVersion = async (version = state.version) => {
  if (!version) return null;
  if (state.wuwaVersions?.[version]) return state.wuwaVersions[version];
  if (!state.wuwaVersionPromises.has(version)) {
    const url = `data/wuwa/versions/${encodeURIComponent(version)}.json`;
    state.wuwaVersionPromises.set(version, fetchJson(url));
  }
  const row = await state.wuwaVersionPromises.get(version);
  state.wuwaVersions[version] = row;
  return row;
};

const loadHoyoChunk = async () => {
  const key = `${state.gameId}:${state.version}`;
  if (!state.chunkEntries.has(key)) {
    const json = await fetchJson(`data/hoyo/chunk/${state.gameId}_${state.version}.json`);
    state.chunkEntries.set(key, json.data);
  }
  return state.chunkEntries.get(key);
};

const hoyoFileListUrl = (version, channel = "pkg_version") => (
  `${HOYOFILES_API_BASE}/${state.gameId}/${version}/${encodeURIComponent(channel)}`
);

const joinHoyoFileUrl = (base, path) => {
  if (!base || !path) return "";
  const encodedPath = String(path)
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${String(base).replace(/\/+$/, "")}/${encodedPath}`;
};

const parseJsonLines = (text) => text
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter(Boolean)
  .map((line) => JSON.parse(line));

const loadHoyoFileEntries = async (version = state.version, channel = "pkg_version") => {
  const key = `${state.gameId}:${version}:${channel}`;
  if (!state.hoyoFileEntries.has(key)) {
    const response = await fetch(cacheBusted(hoyoFileListUrl(version, channel)));
    if (!response.ok) throw new Error(`HoyoFiles list not available: ${response.status}`);
    state.hoyoFileEntries.set(key, parseJsonLines(await response.text()));
  }
  return state.hoyoFileEntries.get(key);
};

const hoyoFileItem = (entry, index = 0, total = 0) => {
  const path = entry.remoteName || entry.path || entry.name || "";
  return {
    key: path,
    badge: "游戏文件",
    title: path.split(/[\\/]/).at(-1) || path,
    subtitle: path,
    remoteName: path,
    size: Number(entry.fileSize || entry.size || 0),
    hash: entry.md5 || entry.hash || "",
    extraHash: entry.hash && entry.hash !== entry.md5 ? entry.hash : "",
    chunkDownload: false,
    directUrl: "",
    count: total ? `${index + 1}/${total}` : "",
  };
};

const nteCdn2Url = (url) => {
  const text = String(url || "");
  const mirror = text.replace("https://yhcdn1.wmupd.com/", "https://yhcdn2.wmupd.com/");
  return mirror === text ? "" : mirror;
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
      mirrorUrl: nteCdn2Url(entry.url),
      mirrorLabel: "CDN2",
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
    mirrorUrl: nteCdn2Url(entry.url),
    mirrorLabel: "CDN2",
    count: `${index + 1}/${total}`,
  };
};

const wuwaFileItem = (entry, index = 0, total = 0) => {
  const urls = entry.urls?.length ? entry.urls : [entry.url].filter(Boolean);
  return {
    key: entry.dest,
    badge: "游戏文件",
    title: entry.name || entry.dest?.split(/[\\/]/).at(-1) || "-",
    subtitle: entry.dest || entry.name || "-",
    remoteName: entry.dest || entry.name || "",
    size: Number(entry.size || 0),
    hash: entry.md5 || "",
    url: urls[0] || "",
    extraLinks: urls.slice(1).map((url, index) => ({ url, label: `CDN${index + 2}` })),
    count: total ? `${index + 1}/${total}` : "",
  };
};

const wuwaPatchItem = (route, entry, index = 0, total = 0) => {
  const urls = entry.urls?.length ? entry.urls : [entry.url].filter(Boolean);
  return {
    key: `${route.from}->${route.to}:${entry.dest}`,
    badge: "补丁分片",
    title: entry.name || entry.dest?.split(/[\\/]/).at(-1) || "-",
    subtitle: `${route.from} -> ${route.to} / ${entry.dest || entry.name || "-"}`,
    remoteName: entry.dest || entry.name || "",
    size: Number(entry.size || 0),
    hash: entry.md5 || "",
    url: urls[0] || "",
    extraLinks: urls.slice(1).map((url, extraIndex) => ({ url, label: `CDN${extraIndex + 2}` })),
    count: total ? `${index + 1}/${total}` : "",
  };
};

const androidItem = (entry, index = 0, total = 0) => ({
  badge: "Android APK",
  title: entry.filename || `${currentGame().name}_${entry.version}.apk`,
  subtitle: `${entry.channel || "官方渠道"} / ${fmtDateTime(entry.updated_at || entry.last_modified)}`,
  size: Number(entry.size || 0),
  sizeLabel: `${androidAvailabilityLabel(entry)} / ${fmtKnownBytes(entry.size)}`,
  hash: entry.md5 || entry.etag || "",
  url: entry.url,
  extraLinks: entry.archive_url ? [{ url: entry.archive_url, label: "签名留档" }] : [],
  count: total ? `${index + 1}/${total}` : "",
});

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

const hoyoLegacyItems = () => hoyoLegacyRecords().map((record) => {
  const currentStatus = record.current?.status_code ? `当前 HTTP ${record.current.status_code}` : "当前状态未知";
  const archiveStatus = record.archive?.status_code ? `CDX ${record.archive.status_code}` : "CDX 未确认";
  return {
    badge: `${record.platform || "未知平台"} 候选`,
    title: record.filename || record.url,
    subtitle: record.url,
    sizeLabel: `${currentStatus} / ${archiveStatus}`,
    hash: record.archive?.digest || "",
    url: record.url,
    extraLinks: record.archive?.timestamp
      ? [{
        url: `https://web.archive.org/web/${record.archive.timestamp}/${record.url}`,
        label: "CDX 快照",
      }]
      : [],
    count: fmtDateTime(record.generated_at_from_path),
  };
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

const arknightsPackageItems = () => {
  const version = arknightsVersion();
  if (!version) return [];
  return version.packages.map((item) => ({
    badge: "官方完整分卷",
    title: item.name,
    subtitle: `分卷 ${item.part} / Hypergryph launcher API`,
    size: item.size,
    hash: item.md5,
    url: item.url,
  }));
};

const normalizeVersionText = (value) => String(value || "").replace(/\d+\.\d+\.\d+/g, "{version}");

const hoyoArchiveComparableItems = async (version) => {
  const row = await loadHoyoVersion(version);
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

const hoyoFileComparableItems = async (version) => {
  const entries = await loadHoyoFileEntries(version);
  return entries.map((entry) => hoyoFileItem(entry));
};

const hoyoComparableItems = async (version) => {
  try {
    const items = await hoyoFileComparableItems(version);
    if (items.length) return items;
  } catch (error) {
    console.warn(error);
  }
  return hoyoArchiveComparableItems(version);
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
  const modified = [];

  for (const [key, item] of newMap) {
    const oldItem = oldMap.get(key);
    if (!oldItem) {
      added.push(item);
      continue;
    }
    const hashChanged = Boolean(oldItem.hash && item.hash && oldItem.hash !== item.hash);
    const sizeChanged = Number(oldItem.size || 0) !== Number(item.size || 0);
    if (hashChanged || sizeChanged) {
      modified.push({
        ...item,
        oldHash: oldItem.hash,
        oldSize: oldItem.size,
        hashChanged,
        sizeChanged,
      });
    }
  }

  for (const [key, item] of oldMap) {
    if (!newMap.has(key)) removed.push(item);
  }

  return { added, removed, modified };
};

const diffLabels = {
  added: ["Added", "+", "green"],
  removed: ["Removed", "-", "rose"],
  modified: ["Modified", "~", "amber"],
};

const diffFilterLabels = [
  ["all", "全部"],
  ["added", "新增"],
  ["removed", "删除"],
  ["modified", "修改"],
  ["size", "仅大小变化"],
  ["hash", "仅 MD5 变化"],
];

const sumSizes = (items, field = "size") => items.reduce((sum, item) => sum + Number(item[field] || 0), 0);
const sumModifiedDelta = (items) => items.reduce((sum, item) => sum + Number(item.size || 0) - Number(item.oldSize || 0), 0);

const fmtSignedBytes = (bytes) => {
  const value = Number(bytes || 0);
  if (value === 0) return "0 B";
  return `${value > 0 ? "+" : "-"}${fmtBytes(Math.abs(value))}`;
};

const fmtChartGB = (bytes, signed = false) => {
  const value = Number(bytes || 0) / 1024 ** 3;
  const prefix = signed && value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(1)} GB`;
};

const nteTrendRows = () => nteVersions()
  .slice()
  .sort((a, b) => compareVersions(a.version, b.version))
  .map((item, index, rows) => {
    const bytes = Number(item.full?.bytes || 0);
    const previous = index > 0 ? Number(rows[index - 1].full?.bytes || 0) : bytes;
    return {
      version: item.version,
      bytes,
      delta: index > 0 ? bytes - previous : 0,
      date: item.last_modified,
    };
  });

const endfieldTrendRows = () => endfieldSummaries()
  .slice()
  .sort((a, b) => compareVersions(a.version, b.version))
  .map((item, index, rows) => {
    const bytes = Number(item.packed_size || 0);
    const previous = index > 0 ? Number(rows[index - 1].packed_size || 0) : bytes;
    return {
      version: item.version,
      bytes,
      delta: index > 0 ? bytes - previous : 0,
      date: item.released_at,
    };
  });

const analyticsTrendRows = () => (isEndfield() ? endfieldTrendRows() : nteTrendRows());

const svgPoints = (rows, valueKey, { width, height, padX, padY, min, max }) => {
  const span = Math.max(max - min, 1);
  const usableW = width - padX * 2;
  const usableH = height - padY * 2;
  return rows.map((row, index) => {
    const x = padX + (rows.length === 1 ? usableW / 2 : (usableW * index) / (rows.length - 1));
    const y = padY + usableH - ((Number(row[valueKey] || 0) - min) / span) * usableH;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
};

const renderTrendChart = (rows) => {
  if (!rows.length) return `<div class="empty compact">暂无趋势数据</div>`;
  const width = 760;
  const height = 280;
  const padLeft = 82;
  const padRight = 96;
  const padTop = 36;
  const padBottom = 48;
  const padX = padLeft;
  const padY = padTop;
  const fullValues = rows.map((row) => row.bytes);
  const deltaValues = rows.map((row) => row.delta);
  const fullMin = Math.min(...fullValues);
  const fullMax = Math.max(...fullValues);
  const deltaMin = Math.min(...deltaValues);
  const deltaMax = Math.max(...deltaValues);
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const fullScale = (value) => padTop + plotHeight - ((Number(value || 0) - fullMin) / Math.max(fullMax - fullMin, 1)) * plotHeight;
  const deltaScale = (value) => padTop + plotHeight - ((Number(value || 0) - deltaMin) / Math.max(deltaMax - deltaMin, 1)) * plotHeight;
  const xScale = (index) => padLeft + (rows.length === 1 ? plotWidth / 2 : (plotWidth * index) / (rows.length - 1));
  const fullPoints = rows.map((row, index) => `${xScale(index).toFixed(2)},${fullScale(row.bytes).toFixed(2)}`).join(" ");
  const deltaPoints = rows.map((row, index) => `${xScale(index).toFixed(2)},${deltaScale(row.delta).toFixed(2)}`).join(" ");
  const fullTicks = [fullMax, (fullMax + fullMin) / 2, fullMin];
  const deltaTicks = [deltaMax, 0, deltaMin]
    .filter((value, index, list) => list.findIndex((item) => Math.abs(item - value) < 1) === index);
  const tickEvery = Math.max(1, Math.ceil(rows.length / 6));
  let tickIndexes = rows
    .map((_, index) => index)
    .filter((index) => index % tickEvery === 0);
  if (!tickIndexes.includes(rows.length - 1)) tickIndexes.push(rows.length - 1);
  if (rows.length > 8 && tickIndexes.length > 2 && tickIndexes.at(-1) - tickIndexes.at(-2) < Math.max(2, Math.floor(tickEvery / 2))) {
    tickIndexes.splice(-2, 1);
  }
  const zeroY = deltaScale(0);
  return `
    <svg class="trend-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="版本体积趋势图">
      <defs>
        <linearGradient id="fullLineGlow" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stop-color="#44a2ff" />
          <stop offset="1" stop-color="#4ad7c8" />
        </linearGradient>
      </defs>
      <path class="chart-axis" d="M${padLeft} ${padTop}V${height - padBottom}H${width - padRight}M${width - padRight} ${padTop}V${height - padBottom}" />
      ${fullTicks.map((value) => {
        const y = fullScale(value);
        return `
          <path class="chart-grid" d="M${padLeft} ${y.toFixed(2)}H${width - padRight}" />
          <text class="chart-y-label" x="${padLeft - 10}" y="${(y + 4).toFixed(2)}" text-anchor="end">${fmtChartGB(value)}</text>
        `;
      }).join("")}
      ${deltaTicks.map((value) => {
        const y = deltaScale(value);
        return `<text class="chart-y-label right" x="${width - padRight + 10}" y="${(y + 4).toFixed(2)}">${fmtChartGB(value, true)}</text>`;
      }).join("")}
      <text class="chart-axis-title" x="${padLeft}" y="16">完整包体积</text>
      <text class="chart-axis-title right" x="${width - padRight}" y="16" text-anchor="end">净变化</text>
      <path class="chart-zero" d="M${padLeft} ${zeroY.toFixed(2)}H${width - padRight}" />
      <polyline class="chart-line full" points="${fullPoints}" />
      <polyline class="chart-line delta" points="${deltaPoints}" />
      ${rows.map((row, index) => {
        const x = xScale(index);
        const y = fullScale(row.bytes);
        return `<circle class="chart-dot" cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="3"><title>${escapeHtml(row.version)} / ${fmtBytes(row.bytes)} / ${fmtSignedBytes(row.delta)}</title></circle>`;
      }).join("")}
      ${tickIndexes.map((index, visibleIndex) => {
        const row = rows[index];
        const x = xScale(index);
        return `
          <path class="chart-x-tick" d="M${x.toFixed(2)} ${height - padBottom}V${height - padBottom + 5}" />
          <text class="chart-label" x="${x.toFixed(2)}" y="${height - 18}" text-anchor="${visibleIndex === 0 ? "start" : visibleIndex === tickIndexes.length - 1 ? "end" : "middle"}">${escapeHtml(row.version)}</text>
        `;
      }).join("")}
    </svg>
  `;
};

const getNteAnalytics = async () => {
  if (state.nteAnalytics) return state.nteAnalytics;
  if (!state.nteAnalyticsPromise) {
    state.nteAnalyticsPromise = buildVersionAnalytics(
      nteVersions().slice().sort((a, b) => compareVersions(a.version, b.version)),
      (version) => nteComparableItems(version),
    ).then((analytics) => {
      state.nteAnalytics = analytics;
      return analytics;
    });
  }
  return state.nteAnalyticsPromise;
};

const getEndfieldAnalytics = async () => {
  if (state.endfieldAnalytics) return state.endfieldAnalytics;
  if (!state.endfieldAnalyticsPromise) {
    state.endfieldAnalyticsPromise = buildVersionAnalytics(
      endfieldSummaries().slice().sort((a, b) => compareVersions(a.version, b.version)),
      (version) => endfieldComparableItems(version),
    ).then((analytics) => {
      state.endfieldAnalytics = analytics;
      return analytics;
    });
  }
  return state.endfieldAnalyticsPromise;
};

const getCurrentAnalytics = () => (isEndfield() ? getEndfieldAnalytics() : getNteAnalytics());

const buildVersionAnalytics = async (versions, itemLoader) => {
  const entriesByVersion = new Map();
  await Promise.all(versions.map(async (item) => {
    entriesByVersion.set(item.version, await itemLoader(item.version));
  }));
  const pairs = [];
  for (let index = 1; index < versions.length; index += 1) {
    const from = versions[index - 1].version;
    const to = versions[index].version;
    const diff = diffVersions(entriesByVersion.get(from) || [], entriesByVersion.get(to) || []);
    const modifiedDelta = sumModifiedDelta(diff.modified);
    const addedBytes = sumSizes(diff.added);
    const removedBytes = sumSizes(diff.removed);
    const modifiedBytes = diff.modified.reduce((sum, item) =>
      sum + Math.abs(Number(item.size || 0) - Number(item.oldSize || 0)), 0);
    const changedBytes = addedBytes + removedBytes + modifiedBytes;
    pairs.push({
      from,
      to,
      added: diff.added.length,
      removed: diff.removed.length,
      modified: diff.modified.length,
      changedFiles: diff.added.length + diff.removed.length + diff.modified.length,
      changedBytes,
      netBytes: addedBytes - removedBytes + modifiedDelta,
    });
  }
  return {
    pairs,
    topChanged: pairs.slice().sort((a, b) => b.changedBytes - a.changedBytes).slice(0, 5),
    topGrowth: pairs.slice().sort((a, b) => b.netBytes - a.netBytes).slice(0, 3),
  };
};

const renderAnalytics = () => {
  const panel = $("#analytics");
  if (state.mode === "android" || (!isNte() && !isEndfield())) {
    panel.hidden = true;
    panel.innerHTML = "";
    return;
  }
  panel.hidden = false;
  const rows = analyticsTrendRows();
  const latest = rows.at(-1);
  const first = rows[0];
  const totalGrowth = latest && first ? latest.bytes - first.bytes : 0;
  const sourceLabel = isEndfield() ? "终末地完整包归档" : "异环完整文件清单";
  panel.innerHTML = `
    <div class="analytics-head">
      <div>
        <p class="kicker">Version Analytics</p>
        <h2>版本体积趋势</h2>
      </div>
      <div class="chart-legend">
        <span class="legend full">完整包体积</span>
        <span class="legend delta">净变化</span>
      </div>
    </div>
    <div class="analytics-grid">
      <div class="trend-panel">
        ${renderTrendChart(rows)}
        <div class="trend-meta">
          <span>${rows.length} 个可用版本</span>
          <span>${first?.version || "-"} -> ${latest?.version || "-"}</span>
          <strong>${fmtSignedBytes(totalGrowth)}</strong>
          <span>${sourceLabel}</span>
        </div>
      </div>
      <div class="rank-panel" id="diffRankPanel">
        <div class="rank-loading">正在计算相邻版本 Diff 排行...</div>
      </div>
    </div>
  `;
  getCurrentAnalytics()
    .then((analytics) => {
      if (state.mode === "android" || (!isNte() && !isEndfield())) return;
      renderDiffRank(analytics);
    })
    .catch((error) => {
      $("#diffRankPanel").innerHTML = `<div class="empty compact">排行计算失败：${escapeHtml(error.message)}</div>`;
    });
};

const renderDiffRank = (analytics) => {
  const panel = $("#diffRankPanel");
  if (!panel) return;
  const rows = analytics.topChanged;
  const biggestGrowth = analytics.topGrowth.find((item) => item.netBytes > 0);
  panel.innerHTML = `
    <div class="rank-head">
      <div>
        <strong>最重相邻 Diff</strong>
        <span>按累计变动体积排序</span>
      </div>
      ${biggestGrowth ? `<small>最大净增 ${biggestGrowth.from} -> ${biggestGrowth.to} / ${fmtSignedBytes(biggestGrowth.netBytes)}</small>` : ""}
    </div>
    <div class="rank-list">
      ${rows.map((item, index) => `
        <article class="rank-row">
          <div class="rank-index">${index + 1}</div>
          <div class="rank-body">
            <strong>${escapeHtml(item.from)} -> ${escapeHtml(item.to)}</strong>
            <span>+${item.added} / -${item.removed} / ~${item.modified}，${item.changedFiles} 个文件</span>
            <em>累计 ${fmtBytes(item.changedBytes)} / 净变化 ${fmtSignedBytes(item.netBytes)}</em>
          </div>
          <button class="icon-button open-compare" type="button" data-from="${escapeHtml(item.from)}" data-to="${escapeHtml(item.to)}">打开对比</button>
        </article>
      `).join("")}
    </div>
  `;
  $$(".open-compare").forEach((button) => {
    button.addEventListener("click", () => {
      state.mode = "compare";
      state.version = button.dataset.to;
      state.compareVersion = button.dataset.from;
      state.diffFilter = "all";
      state.query = "";
      $("#fileSearch").value = "";
      render();
      $("#files").scrollIntoView({ block: "start" });
    });
  });
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
  const modifiedNetBytes = sumModifiedDelta(diff.modified);
  const sourceHint = isNte()
    ? "异环基于完整文件清单做文件级对比。"
    : isEndfield()
      ? "终末地基于完整包与补丁归档条目对比。"
      : "米家游戏优先读取 HoyoFiles 文件清单接口做文件级对比；接口不可用时回退到本站保存的压缩包条目。";

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
      <div class="compare-stat green">
        <span>+ 新增</span>
        <strong>${diff.added.length.toLocaleString()} 个</strong>
        <small>${fmtBytes(sumSizes(diff.added))}</small>
      </div>
      <div class="compare-stat rose">
        <span>- 删除</span>
        <strong>${diff.removed.length.toLocaleString()} 个</strong>
        <small>${fmtBytes(sumSizes(diff.removed))}</small>
      </div>
      <div class="compare-stat amber">
        <span>~ 修改</span>
        <strong>${diff.modified.length.toLocaleString()} 个</strong>
        <small>净变化 ${fmtSignedBytes(modifiedNetBytes)}</small>
      </div>
    </div>
    <div class="diff-filter" role="toolbar" aria-label="Diff filter">
      ${diffFilterLabels.map(([id, label]) => `
        <button class="${state.diffFilter === id ? "active" : ""}" type="button" data-diff-filter="${id}">${label}</button>
      `).join("")}
    </div>
  `;

  const sections = [
    ["added", diff.added],
    ["removed", diff.removed],
    ["modified", diff.modified],
  ]
    .filter(([key]) => shouldShowDiffSection(key))
    .map(([key, items]) => compareSection(diffLabels[key][0], items, key))
    .join("");

  if (!totalChanges) {
    $("#fileList").innerHTML = `${selector}<div class="empty">两个版本没有可见差异</div>`;
  } else {
    $("#fileList").innerHTML = selector + (sections || `<div class="empty">当前筛选条件没有匹配项</div>`);
  }
  $("#compareVersionSelect")?.addEventListener("change", (event) => {
    state.compareVersion = event.target.value;
    state.diffFilter = "all";
    renderList();
  });
  $$("[data-diff-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.diffFilter = button.dataset.diffFilter;
      renderList();
    });
  });
  bindCardActions();
};

const shouldShowDiffSection = (type) => {
  if (state.diffFilter === "all") return true;
  if (state.diffFilter === "size" || state.diffFilter === "hash") return type === "modified";
  return state.diffFilter === type;
};

const filterDiffItems = (items, type) => {
  const typed = type === "modified" && state.diffFilter === "size"
    ? items.filter((item) => item.sizeChanged)
    : type === "modified" && state.diffFilter === "hash"
      ? items.filter((item) => item.hashChanged)
      : items;
  return filterEntries(typed);
};

const compareSection = (label, items, type) => {
  const filtered = filterDiffItems(items, type);
  if (!filtered.length) return "";
  return `
    <section class="compare-section ${type}">
      <div class="compare-section-head">
        <strong>${label}</strong>
        <span>${filtered.length.toLocaleString()} 项</span>
      </div>
      <div class="diff-table">
        ${filtered.slice(0, 500).map((item, index) => compareRow(item, type, index, filtered.length)).join("")}
      </div>
      ${filtered.length > 500 ? `<div class="empty compact">已显示前 500 项，可用搜索继续过滤</div>` : ""}
    </section>
  `;
};

const compareRow = (item, type, index, total) => {
  const [, marker] = diffLabels[type];
  const hashLine = type === "modified" && item.hashChanged
    ? `<div class="diff-change">md5: <code>${escapeHtml(item.oldHash || "-")}</code> <span>→</span> <code>${escapeHtml(item.hash || "-")}</code></div>`
    : type === "modified"
      ? `<div class="diff-change muted">md5 unchanged</div>`
      : "";
  const sizeLine = type === "modified" && item.sizeChanged
    ? `<div class="diff-change">size: <code>${fmtBytes(item.oldSize)}</code> <span>→</span> <code>${fmtBytes(item.size)}</code> <em>${fmtSignedBytes(Number(item.size || 0) - Number(item.oldSize || 0))}</em></div>`
    : type === "modified"
      ? `<div class="diff-change muted">size: ${fmtBytes(item.size)} unchanged</div>`
      : "";
  const meta = type === "modified"
    ? `${sizeLine}${hashLine}`
    : `<div class="diff-change"><code>${fmtBytes(item.size)}</code>${item.hash ? ` <span>#</span> <code>${escapeHtml(item.hash)}</code>` : ""}</div>`;
  return `
    <article class="diff-row diff-${type}">
      <div class="diff-marker">${marker}</div>
      <div class="diff-body">
        <div class="diff-title">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${index + 1}/${total}</span>
        </div>
        <div class="diff-path">${escapeHtml(item.subtitle)}</div>
        ${meta}
      </div>
      <div class="diff-actions">
        ${item.url ? `<button class="icon-button copy-link" type="button" data-url="${escapeHtml(item.url)}" title="复制链接">${icons.copy}<span>复制</span></button>` : ""}
      </div>
    </article>
  `;
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

const renderNteFullFiles = (items) => {
  const filtered = filterEntries(items);
  const note = `
    <div class="notice file-browser-note">
      <div class="notice-copy">
        <strong>清单口径</strong>
        <span>这里展示的是官方 ResList 中可直接下载的游戏对象数量，不等同于本地安装目录递归后的文件数；启动器 Allfile 属于 launcher 独立清单。</span>
      </div>
    </div>
  `;
  if (state.query) {
    $("#fileList").innerHTML = note + (filtered.length
      ? `<div class="hoyo-browser search-results">${filtered.map((entry) => hoyoFileRow(entry, "search", state.nteExpandedFile)).join("")}</div>`
      : `<div class="empty">没有匹配到文件</div>`);
  } else {
    $("#fileList").innerHTML = note + renderDirectoryBrowser({
      files: items,
      currentPath: state.nteFilePath || "",
      expandedFile: state.nteExpandedFile,
    });
  }
  bindCardActions();
  bindNteBrowserActions();
};

const bindNteBrowserActions = () => {
  $$(".folder-row, .breadcrumb-step").forEach((button) => {
    button.addEventListener("click", () => {
      state.nteFilePath = button.dataset.folder || "";
      state.nteExpandedFile = "";
      renderList();
    });
  });
  $$(".hoyo-browser .file-row").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.file || "";
      state.nteExpandedFile = state.nteExpandedFile === key ? "" : key;
      renderList();
    });
  });
};

const renderWuwaFiles = async () => {
  const entries = await loadWuwaEntries();
  const items = entries.map((entry, index) => wuwaFileItem(entry, index, entries.length));
  const filtered = filterEntries(items);
  const version = wuwaVersion();
  const prefix = version?.release_stage === "preload" ? "当前索引来自官方预下载目录；" : "";
  const note = `
    <div class="notice file-browser-note">
      <div class="notice-copy">
        <strong>文件索引</strong>
        <span>${escapeHtml(prefix)}鸣潮官方启动器提供散文件索引；当前版本 ${escapeHtml(state.version)} 含 ${entries.length.toLocaleString()} 个文件，页面按目录浏览，下载时可使用 ${version?.cdn_urls?.length || 0} 个官方 CDN 镜像。</span>
      </div>
    </div>
  `;
  if (state.query) {
    $("#fileList").innerHTML = note + (filtered.length
      ? `<div class="hoyo-browser search-results">${filtered.map((entry) => hoyoFileRow(entry, "search", state.wuwaExpandedFile)).join("")}</div>`
      : `<div class="empty">没有匹配到文件</div>`);
  } else {
    $("#fileList").innerHTML = note + renderDirectoryBrowser({
      files: items,
      currentPath: state.wuwaFilePath || "",
      expandedFile: state.wuwaExpandedFile,
    });
  }
  bindCardActions();
  bindWuwaBrowserActions();
};

const bindWuwaBrowserActions = () => {
  $$(".folder-row, .breadcrumb-step").forEach((button) => {
    button.addEventListener("click", () => {
      state.wuwaFilePath = button.dataset.folder || "";
      state.wuwaExpandedFile = "";
      renderList();
    });
  });
  $$(".hoyo-browser .file-row").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.file || "";
      state.wuwaExpandedFile = state.wuwaExpandedFile === key ? "" : key;
      renderList();
    });
  });
};

const renderWuwaPatches = async () => {
  const version = await loadWuwaVersion();
  const patchFiles = (version?.patches || []).flatMap((route) => route.parts?.length
    ? route.parts.map((entry) => wuwaPatchItem(route, entry))
    : []);
  if (patchFiles.length) {
    const filteredFiles = filterEntries(patchFiles);
    const note = `
      <div class="notice file-browser-note">
        <div class="notice-copy">
          <strong>预下载补丁</strong>
          <span>当前版本 ${escapeHtml(state.version)} 已记录 ${patchFiles.length.toLocaleString()} 个官方补丁分片对象，来源于 ${(version?.patches || []).map((route) => `${route.from} -> ${route.to}`).join(" / ")}。</span>
        </div>
      </div>
    `;
    $("#fileList").innerHTML = note + (filteredFiles.length
      ? filteredFiles.map((entry, index) => fileCard({ ...entry, count: `${index + 1}/${filteredFiles.length}` })).join("")
      : `<div class="empty">没有匹配到补丁分片</div>`);
    bindCardActions();
    return;
  }
  const routes = (version?.patches || []).map((route, index, all) => ({
    badge: "更新路线",
    title: `${route.from} -> ${route.to}`,
    subtitle: route.base_url || route.index_file || route.index_url,
    size: route.size,
    hash: route.index_file_md5,
    url: route.index_url,
    count: `${index + 1}/${all.length}`,
  }));
  const filtered = filterEntries(routes);
  $("#fileList").innerHTML = filtered.length
    ? filtered.map((entry, index) => fileCard({ ...entry, count: `${index + 1}/${filtered.length}` })).join("")
    : `<div class="empty">没有匹配到更新路线</div>`;
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

const renderHoyoFiles = async () => {
  try {
    const entries = await loadHoyoFileEntries();
    const canChunkDownload = Boolean(hoyoVersion()?.chunk);
    const decompressedPath = hoyoDecompressedPath(hoyoVersion());
    const files = entries.map((entry, index) => ({
      ...hoyoFileItem(entry, index, entries.length),
      chunkDownload: canChunkDownload,
      directUrl: joinHoyoFileUrl(decompressedPath, entry.remoteName || entry.path || entry.name || ""),
    }));
    const filtered = filterEntries(files);
    const header = `
      <div class="chunk-summary">
        <div><span>文件清单</span><strong>pkg_version</strong></div>
        <div><span>文件数</span><strong>${entries.length.toLocaleString()}</strong></div>
        <div><span>总大小</span><strong>${fmtBytes(sumSizes(entries.map((entry) => ({ size: entry.fileSize }))))}</strong></div>
        <div><span>来源</span><strong>HoyoFiles API</strong></div>
      </div>
    `;
    $("#fileList").innerHTML = header + (state.query
      ? renderHoyoSearchResults(filtered)
      : renderHoyoFileBrowser(files));
  } catch (error) {
    $("#fileList").innerHTML = `<div class="empty">文件清单读取失败：${escapeHtml(error.message)}</div>`;
  }
  bindCardActions();
  bindHoyoBrowserActions();
  $(".load-more-files")?.addEventListener("click", () => {
    state.hoyoFileVisible += HOYO_FILE_PAGE_SIZE;
    renderHoyoFiles();
  });
};

const renderHoyoSearchResults = (filtered) => {
  const visibleCount = Math.min(state.hoyoFileVisible, filtered.length);
  const visible = filtered.slice(0, visibleCount);
  const more = filtered.length - visibleCount;
  const footer = more > 0
    ? `<div class="list-pager">
        <span>已显示 ${visibleCount.toLocaleString()} / ${filtered.length.toLocaleString()} 个文件</span>
        <button class="icon-button load-more-files" type="button">加载更多 ${Math.min(HOYO_FILE_PAGE_SIZE, more).toLocaleString()} 个</button>
      </div>`
    : filtered.length
      ? `<div class="list-pager muted">已显示全部 ${filtered.length.toLocaleString()} 个文件</div>`
      : "";
  return filtered.length
    ? `<div class="hoyo-browser search-results">${visible.map((entry) => hoyoFileRow(entry, "search")).join("")}</div>${footer}`
    : `<div class="empty">没有匹配到文件</div>`;
};

const renderDirectoryBrowser = ({ files, currentPath = "", expandedFile = "" }) => {
  const prefix = currentPath ? `${currentPath}/` : "";
  const folders = new Map();
  const currentFiles = [];

  files.forEach((item) => {
    const remoteName = item.remoteName || item.subtitle || item.title || "";
    if (prefix && !remoteName.startsWith(prefix)) return;
    const rest = prefix ? remoteName.slice(prefix.length) : remoteName;
    if (!rest) return;
    const slash = rest.indexOf("/");
    if (slash >= 0) {
      const name = rest.slice(0, slash);
      const path = prefix ? `${currentPath}/${name}` : name;
      const folder = folders.get(name) || { name, path, count: 0, size: 0 };
      folder.count += 1;
      folder.size += Number(item.size || 0);
      folders.set(name, folder);
      return;
    }
    currentFiles.push(item);
  });

  const folderRows = [...folders.values()].sort((a, b) => a.name.localeCompare(b.name));
  const fileRows = currentFiles.sort((a, b) => a.title.localeCompare(b.title));
  const rows = [
    ...folderRows.map(hoyoFolderRow),
    ...fileRows.map((item) => hoyoFileRow(item, "browser", expandedFile)),
  ].join("");
  const currentLabel = currentPath || "根目录";
  return `
    <div class="hoyo-browser-head">
      <div class="hoyo-breadcrumb">
        ${hoyoBreadcrumb(currentPath)}
      </div>
      <div class="hoyo-browser-count">
        <span>${escapeHtml(currentLabel)}</span>
        <strong>${folderRows.length.toLocaleString()} 个文件夹 / ${fileRows.length.toLocaleString()} 个文件</strong>
      </div>
    </div>
    <div class="hoyo-browser">
      ${rows || `<div class="empty">当前目录没有可显示文件</div>`}
    </div>
  `;
};

const renderHoyoFileBrowser = (files) => renderDirectoryBrowser({
  files,
  currentPath: state.hoyoFilePath || "",
  expandedFile: state.hoyoExpandedFile,
});

const hoyoBreadcrumb = (currentPath) => {
  const segments = currentPath ? currentPath.split("/") : [];
  let acc = "";
  const buttons = [
    `<button class="breadcrumb-step ${segments.length ? "" : "active"}" type="button" data-folder="">根目录</button>`,
  ];
  segments.forEach((segment, index) => {
    acc = index === 0 ? segment : `${acc}/${segment}`;
    buttons.push(`<button class="breadcrumb-step ${index === segments.length - 1 ? "active" : ""}" type="button" data-folder="${escapeHtml(acc)}">${escapeHtml(segment)}</button>`);
  });
  return buttons.join('<span class="breadcrumb-sep">/</span>');
};

const hoyoFolderRow = (folder) => `
  <button class="browser-row folder-row" type="button" data-folder="${escapeHtml(folder.path)}">
    <span class="browser-icon folder">${icons.folder}</span>
    <span class="browser-name">
      <strong>${escapeHtml(folder.name)}</strong>
      <small>${folder.count.toLocaleString()} 个文件</small>
    </span>
    <span class="browser-size">${fmtBytes(folder.size)}</span>
  </button>
`;

const hoyoFileRow = (item, context, expandedKey = state.hoyoExpandedFile) => {
  const key = item.remoteName || item.subtitle || item.title || "";
  const expanded = expandedKey === key;
  const hashText = [item.hash, item.extraHash ? `xxHash64 ${item.extraHash}` : ""].filter(Boolean).join(" / ") || "-";
  return `
    <button class="browser-row file-row ${expanded ? "selected" : ""}" type="button" data-file="${escapeHtml(key)}">
      <span class="browser-icon file">${icons.file}</span>
      <span class="browser-name">
        <strong>${escapeHtml(item.title)}</strong>
        <small>${escapeHtml(context === "search" ? item.subtitle : hashText)}</small>
      </span>
      <span class="browser-size">${fmtBytes(item.size)}</span>
    </button>
    ${expanded ? `
      <div class="browser-detail">
        <div>
          <strong>${escapeHtml(item.subtitle)}</strong>
          <span># ${escapeHtml(hashText)}</span>
        </div>
        <div class="file-actions">${fileActionHtml(item)}</div>
      </div>
    ` : ""}
  `;
};

const fileAlternateLinks = (item) => [
  ...(item.mirrorUrl ? [{ url: item.mirrorUrl, label: item.mirrorLabel || "镜像" }] : []),
  ...(item.extraLinks || []),
].filter((link) => link.url);

const fileAlternateActionHtml = (links, fallbackLabel = "镜像") => links
  .map((link) => `<a class="icon-button mirror-link" href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer" title="备用下载链接">${icons.down}<span>${escapeHtml(link.label || fallbackLabel)}</span></a>`)
  .join("");

const fileActionHtml = (item) => {
  const preferredUrl = item.preferredUrl || item.url;
  const alternateLinks = fileAlternateLinks(item);
  const primaryLabel = alternateLinks.length ? "CDN1" : "打开";
  const copyLabel = alternateLinks.length ? "复制 CDN1" : "复制链接";
  const urlActions = item.officialUrl
    ? `
      <button class="icon-button copy-link" type="button" data-url="${escapeHtml(preferredUrl)}" title="复制当前可用链接">${icons.copy}<span>复制可用链接</span></button>
      <a class="icon-button ${item.officialAvailable ? "" : "stale-link"}" href="${escapeHtml(item.officialUrl)}" target="_blank" rel="noreferrer" title="${item.officialAvailable ? "上游探测时可用" : "上游曾标记不可用，实际状态可能变化"}">${icons.down}<span>官方${item.officialAvailable ? "" : "状态未知"}</span></a>
      ${fileAlternateActionHtml(alternateLinks, "归档镜像")}
    `
    : `
      <button class="icon-button copy-link" type="button" data-url="${escapeHtml(preferredUrl)}" title="${escapeHtml(copyLabel)}">${icons.copy}<span>${escapeHtml(copyLabel)}</span></button>
      <a class="icon-button" href="${escapeHtml(preferredUrl)}" target="_blank" rel="noreferrer" title="${escapeHtml(primaryLabel)}">${icons.down}<span>${escapeHtml(primaryLabel)}</span></a>
      ${fileAlternateActionHtml(alternateLinks)}
    `;
  const chunkAction = item.chunkDownload
    ? `<button class="icon-button chunk-download-file" type="button" data-remote="${escapeHtml(item.remoteName || item.subtitle)}" data-size="${Number(item.size || 0)}" title="通过官方 Chunk 下载">${icons.down}<span>Chunk 下载</span></button>`
    : "";
  const directAction = item.directUrl
    ? `
      <button class="icon-button copy-link" type="button" data-url="${escapeHtml(item.directUrl)}" title="复制官方散文件直链">${icons.copy}<span>复制直链</span></button>
      <a class="icon-button direct-file-link" href="${escapeHtml(item.directUrl)}" target="_blank" rel="noreferrer" title="打开官方散文件直链">${icons.down}<span>官方直链</span></a>
    `
    : "";
  return `${preferredUrl ? urlActions : ""}${directAction}${chunkAction}`;
};

const fileCard = (item) => {
  const fileActions = fileActionHtml(item);
  const hashText = [item.hash, item.extraHash ? `xxHash64 ${item.extraHash}` : ""].filter(Boolean).join(" / ") || "-";
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
          <span>${escapeHtml(item.sizeLabel || fmtBytes(item.size))}</span>
          <span># ${escapeHtml(hashText)}</span>
        </div>
        <div class="file-path">${escapeHtml(item.subtitle)}</div>
      </div>
      <div class="file-actions">${fileActions}</div>
    </article>
  `;
};

const bindHoyoBrowserActions = () => {
  $$(".folder-row, .breadcrumb-step").forEach((button) => {
    button.addEventListener("click", () => {
      state.hoyoFilePath = button.dataset.folder || "";
      state.hoyoExpandedFile = "";
      renderHoyoFiles();
    });
  });
  $$(".hoyo-browser .file-row").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.file || "";
      state.hoyoExpandedFile = state.hoyoExpandedFile === key ? "" : key;
      renderHoyoFiles();
    });
  });
};

const chunkProgressText = ({ stage, done, total }) => {
  if (stage === "manifest") return `Manifest ${done}/${total}`;
  if (stage === "downloading") return `Chunk ${done}/${total}`;
  if (stage === "merging") return "合并中";
  if (stage === "done") return "完成";
  return "下载中";
};

const downloadHoyoFileByChunk = async (button) => {
  const remoteName = button.dataset.remote;
  const size = Number(button.dataset.size || 0);
  if (size > 2 * 1024 ** 3 && !window.confirm(`该文件大小约 ${fmtBytes(size)}，浏览器内存压力会很大，确定继续？`)) {
    return;
  }

  const label = button.querySelector("span");
  const original = label?.textContent || "Chunk 下载";
  button.disabled = true;
  label.textContent = "准备中";

  try {
    const chunk = await loadHoyoChunk();
    const manifests = chunk.manifests || [];
    if (!manifests.length) throw new Error("该版本没有 Chunk Manifest");

    const { downloadHoyoChunkFile } = await import("./chunk-download.js");
    const result = await downloadHoyoChunkFile({
      file: { remoteName },
      manifests,
      gameId: state.gameId,
      version: state.version,
      onProgress: (progress) => {
        label.textContent = chunkProgressText(progress);
      },
    });
    showToast(`已生成下载：${result.filename}`);
  } catch (error) {
    console.error(error);
    showToast(`Chunk 下载失败：${error.message}`);
  } finally {
    button.disabled = false;
    label.textContent = original;
  }
};

const bindCardActions = () => {
  $$(".copy-link").forEach((button) => {
    button.addEventListener("click", () => copyText(button.dataset.url, "链接已复制"));
  });
  $$(".chunk-download-file").forEach((button) => {
    button.addEventListener("click", () => downloadHoyoFileByChunk(button));
  });
};

const renderList = async () => {
  if (state.mode === "compare") {
    await renderCompare();
    return;
  }

  if (state.mode === "android") {
    const entries = androidVersionEntries();
    const filtered = filterEntries(entries.map((entry, index) => androidItem(entry, index, entries.length)));
    $("#fileList").innerHTML = filtered
      .map((entry, index) => fileCard({ ...entry, count: `${index + 1}/${filtered.length}` }))
      .join("") || `<div class="empty">当前游戏没有 Android APK 直链记录</div>`;
    bindCardActions();
    return;
  }

  if (state.mode === "legacy") {
    const entries = hoyoLegacyItems();
    const filtered = filterEntries(entries);
    $("#fileList").innerHTML = filtered
      .map((entry, index) => fileCard({ ...entry, count: entry.count || `${index + 1}/${filtered.length}` }))
      .join("") || `<div class="empty">当前游戏没有候选线索</div>`;
    bindCardActions();
    return;
  }

  if (isNte()) {
    if (state.mode === "reslist") {
      renderNteResList();
      return;
    }
    const entries = await loadNteEntries();
    const items = entries.map((entry, index) => nteItem(entry, index, entries.length));
    if (state.mode === "full") {
      renderNteFullFiles(items);
      return;
    }
    const filtered = filterEntries(items);
    $("#fileList").innerHTML = filtered
      .map((entry, index) => fileCard({ ...entry, count: `${index + 1}/${filtered.length}` }))
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

  if (isArknights()) {
    const entries = arknightsPackageItems();
    const filtered = filterEntries(entries);
    $("#fileList").innerHTML = filtered
      .map((entry, index) => fileCard({ ...entry, count: `${index + 1}/${filtered.length}` }))
      .join("") || `<div class="empty">该版本没有完整包记录</div>`;
    bindCardActions();
    return;
  }

  if (isWuwa()) {
    if (state.mode === "files") {
      await renderWuwaFiles();
    } else {
      await renderWuwaPatches();
    }
    return;
  }

  if (state.mode === "files") {
    await renderHoyoFiles();
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
  if (state.mode === "legacy") {
    const versions = hoyoLegacySummaries();
    state.version = selectVersionForContext(versions, preferredVersion);
    return;
  }
  if (state.mode === "android") {
    const versions = androidSummaries().slice().sort((a, b) => compareVersions(b.version, a.version));
    state.version = selectVersionForContext(versions, preferredVersion);
    return;
  }
  if (isNte()) {
    const versions = nteVersions().sort((a, b) => compareVersions(b.version, a.version));
    state.version = selectVersionForContext(versions, preferredVersion);
    return;
  }
  if (isEndfield()) {
    const versions = endfieldSummaries().sort((a, b) => compareVersions(b.version, a.version));
    state.version = selectVersionForContext(versions, preferredVersion);
    return;
  }
  if (isWuwa()) {
    const versions = wuwaSummaries().sort((a, b) => compareVersions(b.version, a.version));
    state.version = selectVersionForContext(versions, preferredVersion);
    await loadWuwaVersion();
    return;
  }
  if (isArknights()) {
    const versions = arknightsSummaries().sort((a, b) => compareVersions(b.version, a.version));
    state.version = selectVersionForContext(versions, preferredVersion);
    return;
  }
  const versions = hoyoSummaries()
    .filter((item) => item.package_items || item.update_items || item.has_chunk)
    .sort((a, b) => compareVersions(b.version, a.version));
  state.version = selectVersionForContext(versions, preferredVersion);
  await loadHoyoVersion();
};

const renderNotice = () => {
  const notice = $("#notes");
  if (state.mode === "legacy") {
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>未确认候选线索</strong>
        <span>这里保存用户发现的官方 CDN 历史路径。它们不计入正式版本列表，也不代表当前可下载；页面保留路径时间、当前探测状态与 CDX 证据，方便后续版本考古。</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="data/hoyo/${state.gameId}_legacy_candidates.json" target="_blank" rel="noreferrer">候选 JSON</a>
        <a class="source-link" href="${REPOSITORY_URL}" target="_blank" rel="noreferrer">本站仓库</a>
      </div>
    `;
  } else if (state.mode === "android") {
    const androidNotice = isEndfield()
      ? "页面保存已确认的官方 Android APK 下载入口；终末地使用官方 launcher latest 入口，同时留档同步时解析到的 Hycdn 临时签名目标。签名目标可能过期，但仍保留历史记录价值。该列表从当前可确认版本开始滚动保存，不代表完整历史。"
      : "页面保存已确认的官方 Android APK CDN URL；同步任务会解析支持的官方最新下载入口，发现新 APK 后记录大小、Last-Modified、ETag 与可用状态。该列表从当前可确认版本开始滚动保存，不代表完整历史。";
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>Android APK 直链</strong>
        <span>${androidNotice}</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="data/android/index.json" target="_blank" rel="noreferrer">Android APK 索引</a>
        <a class="source-link" href="${REPOSITORY_URL}#android-apk-archive" target="_blank" rel="noreferrer">本站仓库 README</a>
      </div>
    `;
  } else if (isNte()) {
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
  } else if (isArknights()) {
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>数据来源</strong>
        <span>页面读取明日方舟 PC 官方启动器 API，保存当前完整分卷 URL、MD5 与大小。该接口仅提供当前最新版本，历史版本后续再通过网页时空机或旧接口快照补充。</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="${escapeHtml(state.arknightsIndex.official_api)}" target="_blank" rel="noreferrer">官方 get_latest API</a>
        <a class="source-link" href="${escapeHtml(state.arknightsIndex.source_site)}" target="_blank" rel="noreferrer">明日方舟 PC 官网</a>
        <a class="source-link" href="data/arknights/versions.json" target="_blank" rel="noreferrer">本站方舟 PC 索引</a>
      </div>
    `;
  } else if (isWuwa()) {
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>数据来源</strong>
        <span>页面基于 yuhkix/wuwa-downloader 的启动器发现入口，读取鸣潮国服官方启动器索引与 resource index，保存官方 CDN 文件 URL、MD5 与目录结构。</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="${escapeHtml(state.wuwaIndex.source)}" target="_blank" rel="noreferrer">yuhkix/wuwa-downloader</a>
        <a class="source-link" href="${escapeHtml(state.wuwaIndex.selected_launcher_index)}" target="_blank" rel="noreferrer">官方 launcher index</a>
        <a class="source-link" href="${escapeHtml(wuwaVersion()?.resource_index || "#")}" target="_blank" rel="noreferrer">resource index</a>
      </div>
    `;
  } else {
    const profile = hoyoDistributionProfile(
      hoyoSummaries().find((item) => item.version === state.version),
      hoyoVersion(),
    );
    const decompressedPath = hoyoDecompressedPath(hoyoVersion());
    const downloadOrder = decompressedPath
      ? "文件下载优先使用官方散文件直链；若同时存在 Chunk，可作为兜底。"
      : hoyoVersion()?.chunk
        ? "文件下载通过官方 Chunk Manifest 定位、下载并合并。"
        : "该版本主要通过官方压缩包分发。";
    notice.innerHTML = `
      <div class="notice-copy">
        <strong>${escapeHtml(profile.label)}</strong>
        <span>${escapeHtml(profile.detail)}。${escapeHtml(downloadOrder)}文件清单与版本对比按需读取 HoyoFiles 的 pkg_version 索引。</span>
      </div>
      <div class="source-links">
        <a class="source-link" href="https://hoyo-files.amarea.cn/" target="_blank" rel="noreferrer">hoyo-files.amarea.cn</a>
        <a class="source-link" href="${HOYOFILES_API_BASE}/${state.gameId}/${state.version}/pkg_version" target="_blank" rel="noreferrer">pkg_version 文件清单</a>
        ${state.gameId === "hk4e" ? `<a class="source-link" href="${REPOSITORY_URL}#genshin-cdn-evolution" target="_blank" rel="noreferrer">原神 CDN 演进</a>` : ""}
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
  renderSyncStatus();
  renderAnalytics();
  renderLinks();
  renderPanelTitle();
  renderNotice();
  renderList();
  updateActiveSideLink();
  saveView();
};

updateActiveSideLink();

Promise.all([
  fetchJson("./data/catalog.json"),
  fetchJson("./data/hoyo/games.json"),
  fetchJson("./data/endfield/index.json"),
  fetchJson("./data/endfield/versions.json"),
  fetchJson("./data/wuwa/index.json"),
  fetchJson("./data/arknights/index.json"),
  fetchJson("./data/arknights/versions.json"),
  fetchJson("./data/android/index.json"),
  fetchOptionalJson("./data/hoyo/nap_legacy_candidates.json"),
]).then(async ([nteCatalog, hoyoIndex, endfieldIndex, endfieldVersions, wuwaIndex, arknightsIndex, arknightsVersions, androidIndex, napLegacyCandidates]) => {
  state.nteCatalog = nteCatalog;
  state.hoyoIndex = hoyoIndex;
  state.endfieldIndex = endfieldIndex;
  state.endfieldVersions = endfieldVersions;
  state.wuwaIndex = wuwaIndex;
  state.wuwaVersions = {};
  state.arknightsIndex = arknightsIndex;
  state.arknightsVersions = arknightsVersions;
  state.androidIndex = androidIndex;
  state.hoyoLegacyCandidates = napLegacyCandidates?.game_id
    ? { [napLegacyCandidates.game_id]: napLegacyCandidates }
    : {};
  const savedView = loadSavedView();
  if (allGames().some((game) => game.id === savedView.gameId)) {
    state.gameId = savedView.gameId;
  }
  state.manualVersions = savedView.manualVersions && typeof savedView.manualVersions === "object"
    ? savedView.manualVersions
    : {};
  state.latestVersions = savedView.latestVersions && typeof savedView.latestVersions === "object"
    ? savedView.latestVersions
    : {};
  state.collapsedVersionGroups = savedView.collapsedVersionGroups && typeof savedView.collapsedVersionGroups === "object"
    ? savedView.collapsedVersionGroups
    : {};
  state.mode = modesForGame().some(([mode]) => mode === savedView.mode)
    ? savedView.mode
    : modesForGame()[0][0];
  bindStaticActions();
  await ensureGameData(preferredVersionForContext(state.gameId, state.mode));
  render();
});
