const state = {
  catalog: null,
  version: null,
  mode: "full",
  entries: new Map(),
  query: "",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const icons = {
  box: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 8-9-5-9 5 9 5 9-5Z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>',
  copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  down: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>',
  link: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 20l1.1-1.1"/></svg>',
};

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
const availableVersions = () => state.catalog.versions.filter((item) => item.status === 200 && item.full);
const currentVersion = () => state.catalog.versions.find((item) => item.version === state.version);
const currentFiles = () => currentVersion()?.[state.mode];

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const shortUrl = (url) => String(url).replace("https://yhcdn1.wmupd.com/clientRes/", "");

const commandFor = (version) =>
  `python scripts\\nte_downloader.py download ${version} --download-root downloads --workers 4 --pack --pack-dir packages`;

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

  $$(".mode-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      $$(".mode-tab").forEach((item) => item.classList.toggle("active", item === button));
      render();
    });
  });

  $("#fileSearch").addEventListener("input", (event) => {
    state.query = event.target.value.trim().toLowerCase();
    renderList();
  });

  $("#copyCommandBtn").addEventListener("click", () => copyText(commandFor(state.version), "命令已复制"));
};

const renderVersionMenu = () => {
  const groups = availableVersions()
    .sort((a, b) => compareVersions(b.version, a.version))
    .reduce((result, item) => {
      const family = item.version.split(".").slice(0, 2).join(".");
      if (!result.has(family)) result.set(family, []);
      result.get(family).push(item);
      return result;
    }, new Map());

  $("#versionMenu").innerHTML = [...groups.entries()]
    .map(([family, items]) => {
      const base = `${family}.0`;
      return `
        <div class="version-group">
          <div class="version-group-head">
            <strong>${family} 大版本</strong>
            <span>${items.length} 个可用版本</span>
          </div>
          ${items.map((item) => {
            const isBase = item.version === base;
            const selected = item.version === state.version;
            return `
              <button class="version-row ${selected ? "selected" : ""}" type="button" data-version="${item.version}">
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
          }).join("")}
        </div>
      `;
    })
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

const renderStats = () => {
  const version = currentVersion();
  const okCount = availableVersions().length;
  const family = version.version.split(".").slice(0, 2).join(".");
  const isBase = version.version === `${family}.0`;
  const stats = [
    ["当前版本", version.version],
    ["版本族", `${family} ${isBase ? "大版本" : "补丁版"}`],
    ["清单时间", fmtDateTime(version.last_modified)],
    ["完整文件", `${version.full.items} 个 / ${fmtBytes(version.full.bytes)}`],
    ["补丁文件", `${version.patches.items} 个 / ${fmtBytes(version.patches.bytes)}`],
  ];
  $("#stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join("");
};

const renderLinks = () => {
  const files = currentFiles();
  const disabled = state.mode === "reslist" || !files;
  $("#urlsLink").classList.toggle("disabled", disabled);
  $("#aria2Link").classList.toggle("disabled", disabled);
  $("#jsonLink").classList.toggle("disabled", disabled);
  $("#urlsLink").href = files?.urls || "#";
  $("#aria2Link").href = files?.aria2 || "#";
  $("#jsonLink").href = files?.json || "#";
};

const loadEntries = async () => {
  if (state.mode === "reslist") return [];
  const files = currentFiles();
  if (!files?.json) return [];
  const key = `${state.version}:${state.mode}`;
  if (!state.entries.has(key)) {
    const response = await fetch(files.json);
    state.entries.set(key, await response.json());
  }
  return state.entries.get(key);
};

const normalizeEntry = (entry, index, total) => {
  if (state.mode === "patches") {
    const patch = entry.patch || "";
    const name = patch || entry.url.split("/").at(-1);
    return {
      badge: "补丁分片",
      title: name,
      subtitle: `${entry.oldfile || "-"}  →  ${entry.newfile || "-"}`,
      size: entry.filesize,
      hash: patch.split(".")[0] || "-",
      url: entry.url,
      count: `${index + 1}/${total}`,
    };
  }

  const name = entry.filename?.split(/[\\/]/).at(-1) || entry.object;
  return {
    badge: "完整文件",
    title: name,
    subtitle: entry.filename || entry.object,
    size: entry.filesize,
    hash: entry.md5,
    url: entry.url,
    count: `${index + 1}/${total}`,
  };
};

const renderResList = () => {
  const version = currentVersion();
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

const fileCard = (item) => `
  <article class="file-card">
    <div class="file-icon">${icons.box}</div>
    <div class="file-main">
      <div class="file-title">
        <span class="pill">${item.badge}</span>
        <span class="count">${item.count}</span>
        <strong>${escapeHtml(item.title)}</strong>
      </div>
      <div class="file-meta">
        <span>${fmtBytes(item.size)}</span>
        <span># ${escapeHtml(item.hash)}</span>
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
  if (state.mode === "reslist") {
    renderResList();
    return;
  }

  const entries = await loadEntries();
  const needle = state.query;
  const filtered = entries.filter((entry) => JSON.stringify(entry).toLowerCase().includes(needle));
  $("#fileList").innerHTML = filtered
    .map((entry, index) => fileCard(normalizeEntry(entry, index, filtered.length)))
    .join("") || `<div class="empty">没有匹配到文件</div>`;
  bindCardActions();
};

const render = () => {
  const version = currentVersion();
  $("#selectedVersion").textContent = version.version;
  $("#copyCommandBtn").innerHTML = `${icons.copy}<span>复制下载命令</span>`;
  $("#commandText").textContent = commandFor(version.version);
  $("#panelKicker").textContent = state.mode === "full" ? "Full files" : state.mode === "patches" ? "Patch objects" : "Manifests";
  $("#panelTitle").textContent = `${version.version} ${state.mode === "full" ? "完整文件" : state.mode === "patches" ? "更新补丁" : "清单文件"}`;
  renderVersionMenu();
  renderStats();
  renderLinks();
  renderList();
};

fetch("./data/catalog.json")
  .then((response) => response.json())
  .then((catalog) => {
    state.catalog = catalog;
    state.version = availableVersions().sort((a, b) => compareVersions(b.version, a.version))[0].version;
    bindStaticActions();
    render();
  });
