import { t as ZSTDDecoder } from "./vendor/zstddec.modern.js";

const textDecoder = new TextDecoder();
let decoderPromise = null;
const manifestCache = new Map();

const proxiedUrl = (url) => (
  typeof location === "undefined" ? url : `/cdn-proxy?url=${encodeURIComponent(url)}`
);

const fetchBytes = async (url, signal) => {
  const response = await fetch(proxiedUrl(url), { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return new Uint8Array(await response.arrayBuffer());
};

const getDecoder = async () => {
  if (!decoderPromise) {
    decoderPromise = (async () => {
      const decoder = new ZSTDDecoder();
      await decoder.init();
      return decoder;
    })();
  }
  return decoderPromise;
};

const zstdDecode = async (bytes, expectedSize = 0) => {
  const decoder = await getDecoder();
  return decoder.decode(bytes, Number(expectedSize || 0));
};

const readVarint = (bytes, cursor) => {
  let result = 0;
  let shift = 0;
  let index = cursor.index;
  for (;;) {
    if (index >= bytes.length) throw new Error("Unexpected end of protobuf varint");
    const value = bytes[index++];
    result += (value & 0x7f) * 2 ** shift;
    if ((value & 0x80) === 0) break;
    shift += 7;
  }
  cursor.index = index;
  return result;
};

const readBytes = (bytes, cursor) => {
  const length = readVarint(bytes, cursor);
  const start = cursor.index;
  const end = start + length;
  if (end > bytes.length) throw new Error("Unexpected end of protobuf bytes");
  cursor.index = end;
  return bytes.subarray(start, end);
};

const skipField = (bytes, cursor, wireType) => {
  if (wireType === 0) {
    readVarint(bytes, cursor);
    return;
  }
  if (wireType === 2) {
    readBytes(bytes, cursor);
    return;
  }
  if (wireType === 5) {
    cursor.index += 4;
    return;
  }
  if (wireType === 1) {
    cursor.index += 8;
    return;
  }
  throw new Error(`Unsupported protobuf wire type ${wireType}`);
};

const readTag = (bytes, cursor) => {
  const tag = readVarint(bytes, cursor);
  return { field: tag >> 3, wireType: tag & 7 };
};

const decodeChunk = (bytes) => {
  const cursor = { index: 0 };
  const chunk = {};
  while (cursor.index < bytes.length) {
    const { field, wireType } = readTag(bytes, cursor);
    if (field === 1 && wireType === 2) chunk.id = textDecoder.decode(readBytes(bytes, cursor));
    else if (field === 2 && wireType === 2) chunk.checksum = textDecoder.decode(readBytes(bytes, cursor));
    else if (field === 3 && wireType === 0) chunk.offset = readVarint(bytes, cursor);
    else if (field === 4 && wireType === 0) chunk.compressedSize = readVarint(bytes, cursor);
    else if (field === 5 && wireType === 0) chunk.uncompressedSize = readVarint(bytes, cursor);
    else skipField(bytes, cursor, wireType);
  }
  return chunk;
};

const decodeFile = (bytes) => {
  const cursor = { index: 0 };
  const file = { chunks: [] };
  while (cursor.index < bytes.length) {
    const { field, wireType } = readTag(bytes, cursor);
    if (field === 1 && wireType === 2) file.path = textDecoder.decode(readBytes(bytes, cursor));
    else if (field === 2 && wireType === 2) file.chunks.push(decodeChunk(readBytes(bytes, cursor)));
    else if (field === 3 && wireType === 0) file.isFolder = Boolean(readVarint(bytes, cursor));
    else if (field === 4 && wireType === 0) file.size = readVarint(bytes, cursor);
    else if (field === 5 && wireType === 2) file.checksum = textDecoder.decode(readBytes(bytes, cursor));
    else skipField(bytes, cursor, wireType);
  }
  return file;
};

const decodeManifest = (bytes) => {
  const cursor = { index: 0 };
  const manifest = { files: [] };
  while (cursor.index < bytes.length) {
    const { field, wireType } = readTag(bytes, cursor);
    if (field === 1 && wireType === 2) manifest.files.push(decodeFile(readBytes(bytes, cursor)));
    else skipField(bytes, cursor, wireType);
  }
  return manifest;
};

const fetchManifest = async (manifestInfo, cacheKey, signal) => {
  if (manifestCache.has(cacheKey)) return manifestCache.get(cacheKey);
  const url = `${manifestInfo.manifest_download.url_prefix}/${manifestInfo.manifest.id}${manifestInfo.manifest_download.url_suffix || ""}`;
  const compressed = await fetchBytes(url, signal).catch((error) => {
    throw new Error(`Manifest 下载失败：${error.message}`);
  });
  const decompressed = await zstdDecode(compressed, manifestInfo.manifest.uncompressed_size);
  const manifest = decodeManifest(decompressed);
  manifestCache.set(cacheKey, manifest);
  return manifest;
};

const saveBytes = (filename, bytes) => {
  const blob = new Blob([bytes], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
};

const downloadChunks = async ({ chunks, urlPrefix, urlSuffix = "", signal, onProgress }) => {
  const sorted = [...chunks].sort((left, right) => Number(left.offset || 0) - Number(right.offset || 0));
  const parts = new Array(sorted.length);
  let next = 0;
  let done = 0;
  const workerCount = Math.min(4, sorted.length);

  const worker = async () => {
    for (;;) {
      const index = next;
      next += 1;
      if (index >= sorted.length) return;
      const chunk = sorted[index];
      const compressed = await fetchBytes(`${urlPrefix}/${chunk.id}${urlSuffix}`, signal).catch((error) => {
        throw new Error(`Chunk 下载失败：${error.message}`);
      });
      parts[index] = await zstdDecode(compressed, chunk.uncompressedSize);
      done += 1;
      onProgress?.({ stage: "downloading", done, total: sorted.length });
    }
  };

  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return parts;
};

export const downloadHoyoChunkFile = async ({ file, manifests, gameId, version, signal, onProgress }) => {
  let matchedFile = null;
  let matchedManifest = null;

  for (let index = 0; index < manifests.length; index += 1) {
    const manifestInfo = manifests[index];
    onProgress?.({ stage: "manifest", done: index + 1, total: manifests.length });
    const cacheKey = `${gameId}:${version}:${manifestInfo.manifest.id}`;
    const manifest = await fetchManifest(manifestInfo, cacheKey, signal);
    matchedFile = manifest.files.find((entry) => entry.path === file.remoteName);
    if (matchedFile) {
      matchedManifest = manifestInfo;
      break;
    }
  }

  if (!matchedFile || !matchedManifest) throw new Error("Manifest 中没有找到该文件");
  if (!matchedFile.chunks?.length) throw new Error("该文件没有可下载的 Chunk");

  const chunkDownload = matchedManifest.chunk_download;
  const parts = await downloadChunks({
    chunks: matchedFile.chunks,
    urlPrefix: chunkDownload.url_prefix,
    urlSuffix: chunkDownload.url_suffix || "",
    signal,
    onProgress,
  });

  onProgress?.({ stage: "merging", done: parts.length, total: parts.length });
  const byteLength = parts.reduce((sum, part) => sum + part.byteLength, 0);
  const merged = new Uint8Array(byteLength);
  let offset = 0;
  for (const part of parts) {
    merged.set(part, offset);
    offset += part.byteLength;
  }

  const filename = file.remoteName.split(/[\\/]/).at(-1) || "download.bin";
  saveBytes(filename, merged);
  onProgress?.({ stage: "done", done: parts.length, total: parts.length });
  return { filename, size: byteLength };
};
