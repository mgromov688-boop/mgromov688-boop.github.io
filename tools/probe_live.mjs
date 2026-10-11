// Разведка перед выкладкой: статус, заголовок и meta robots у адресов из sitemap.
// node tools/probe_live.mjs <url> [<url> ...]
const urls = process.argv.slice(2);
for (const u of urls) {
  try {
    const r = await fetch(u, { redirect: "follow", headers: { "User-Agent": "Mozilla/5.0 Chrome/129.0" } });
    const t = await r.text();
    const title = (t.match(/<title>([\s\S]*?)<\/title>/) || [, "-"])[1].trim().slice(0, 80);
    const rob = t.match(/<meta[^>]+name="robots"[^>]*>/g) || [];
    const old = /ClaudeCodich|Кодыч/.test(t) ? " | OLD-BRAND" : "";
    console.log(r.status, u, "|", title, "|", rob.join(" ") || "robots:-", old);
  } catch (e) { console.log("ERR", u, e.message); }
}
