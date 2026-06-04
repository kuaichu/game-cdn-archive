const ALLOWED_HOSTS = new Set([
  "autopatchcn.yuanshen.com",
  "autopatchcn.bhsr.com",
  "autopatchcn.juequling.com",
  "autopatchcn.bh3.com",
]);

const proxy = async (request) => {
  const pageUrl = new URL(request.url);
  const rawTarget = pageUrl.searchParams.get("url");
  if (!rawTarget) return new Response("Missing url", { status: 400 });

  let target;
  try {
    target = new URL(rawTarget);
  } catch {
    return new Response("Invalid url", { status: 400 });
  }

  if (target.protocol !== "https:" || !ALLOWED_HOSTS.has(target.hostname)) {
    return new Response("Host not allowed", { status: 403 });
  }

  const response = await fetch(target.toString(), {
    headers: {
      "User-Agent": "game-cdn-archive/1.0",
    },
  });
  const headers = new Headers();
  for (const name of ["content-type", "content-length", "etag", "last-modified"]) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("Access-Control-Allow-Origin", "*");
  headers.set("Cache-Control", "public, max-age=604800");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/cdn-proxy") return proxy(request);
    return env.ASSETS.fetch(request);
  },
};
