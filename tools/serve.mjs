// Локальный просмотр сайта как в корне GitHub Pages: node tools/serve.mjs [порт]
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const PORT = Number(process.argv[2] || 8765);
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8", ".xml": "application/xml", ".json": "application/json", ".webp": "image/webp" };

createServer(async (req, res) => {
  let p = join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (!p.startsWith(ROOT)) { res.writeHead(403).end(); return; }
  try {
    if ((await stat(p)).isDirectory()) p = join(p, "index.html");
    res.writeHead(200, { "Content-Type": TYPES[extname(p)] || "application/octet-stream" }).end(await readFile(p));
  } catch { res.writeHead(404).end("404"); }
}).listen(PORT, () => console.log(`http://localhost:${PORT}/`));
