"""Проверка сайта AUREUS в корне user-site перед push: разметка, адреса, бренд, ссылки.

    python tools/site_check.py            # всё, включая живые внешние ссылки
    python tools/site_check.py --offline  # без сети

Адаптация geo/site_check.py (прототип под /aureus/). Код возврата 1, если есть ошибки.
"""
import json, pathlib, re, sys, xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = "https://mgromov688-boop.github.io"
ENTITY = "AUREUS | Нейросети"
PUBLISHED = [p for p in ROOT.rglob("*") if p.is_file() and not any(
    part in (".git", "tools", "_drafts") for part in p.relative_to(ROOT).parts)
    and p.suffix in (".html", ".txt", ".xml", ".css", ".md") and p.name != "README.md"]
errors, warns = [], []


def err(msg): errors.append(msg); print("❌", msg)
def warn(msg): warns.append(msg); print("⚠ ", msg)
def ok(msg): print("✅", msg)


def url_of(path: pathlib.Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return HOST + "/" + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)


# 1. HTML: JSON-LD, canonical, описание, плейсхолдеры
for f in sorted(ROOT.rglob("*.html")):
    if "tools" in f.relative_to(ROOT).parts or re.fullmatch(r"google[0-9a-f]+\.html", f.name) or f.name == "404.html":
        continue  # подтверждение Search Console и 404 (noindex): служебные, разметка им не нужна
    rel, t = f.relative_to(ROOT).as_posix(), f.read_text(encoding="utf-8")
    for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
        try:
            d = json.loads(b)
        except json.JSONDecodeError as e:
            err(f"{rel}: JSON-LD не парсится: {e}"); continue
        nodes = d.get("@graph", [d])
        types = [n.get("@type") for n in nodes]
        ok(f"{rel}: JSON-LD {types}")
        for n in nodes:
            if n.get("@type") == "Organization":
                if n.get("name") != ENTITY: err(f"{rel}: Organization.name = {n.get('name')!r}")
                if n.get("alternateName") != "aureus_ai_hub": err(f"{rel}: alternateName = {n.get('alternateName')!r}")
                if len(n.get("sameAs", [])) != 7: err(f"{rel}: sameAs {len(n.get('sameAs', []))}, нужно 7")
            if n.get("@type") == "ItemList":
                ok(f"{rel}: ItemList, гайдов {len(n['itemListElement'])}")
            if n.get("@type") in ("Article", "BlogPosting"):
                for who in ("author", "publisher"):
                    if n.get(who, {}).get("name") != ENTITY: err(f"{rel}: Article.{who} = {n.get(who)}")
                if not n.get("datePublished"): err(f"{rel}: нет datePublished")
    can = re.search(r'<link rel="canonical" href="([^"]+)"', t)
    if not can: err(f"{rel}: нет canonical")
    elif can.group(1) != url_of(f): err(f"{rel}: canonical {can.group(1)} ≠ {url_of(f)}")
    desc = re.search(r'<meta name="description" content="([^"]+)"', t)
    n = len(desc.group(1)) if desc else 0
    (ok if 140 <= n <= 160 else err)(f"{rel}: meta description {n} знаков")
    if "{{" in t: err(f"{rel}: остался плейсхолдер {{{{…}}}}")
    for href in re.findall(r'(?:href|src)="(/[^"#?]*)"', t):  # внутренние ссылки
        target = ROOT / href.lstrip("/")
        if href.startswith(("/prompts/", "/guide/")):
            continue  # живут в других репозиториях того же хоста
        if not (target.is_file() or (target / "index.html").is_file()):
            err(f"{rel}: битая внутренняя ссылка {href}")

# 2. sitemap
try:
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.parse(ROOT / "sitemap.xml").getroot().findall("s:url/s:loc", ns)]
    foreign = [u for u in locs if not u.startswith(HOST + "/")]
    if foreign: err(f"sitemap: чужие адреса {foreign}")
    for u in locs:
        path = u[len(HOST):]
        if path.startswith(("/prompts/", "/guide/")):
            continue
        local = ROOT / path.lstrip("/")
        if not (local.is_file() or (local / "index.html").is_file()):
            err(f"sitemap: {u} нет в папке сайта")
    ok(f"sitemap.xml парсится, адресов {len(locs)}: " + ", ".join(u[len(HOST):] for u in locs))
except ET.ParseError as e:
    err(f"sitemap.xml не парсится: {e}")

# 3. Хвосты прототипа и старый бренд
old_lines = []
for f in PUBLISHED:
    t = f.read_text(encoding="utf-8")
    rel = f.relative_to(ROOT).as_posix()
    if "/aureus/" in t: err(f"{rel}: остался путь /aureus/")
    if "{{TEXT" in t: err(f"{rel}: остался {{{{TEXT}}}}")
    old_lines += [f"{rel}: {ln.strip()[:90]}" for ln in t.splitlines() if re.search(r"ClaudeCodich|Кодыч|claudecodich", ln)]
if len(old_lines) == 1 and old_lines[0].startswith("llms.txt"):
    ok(f"старый бренд ровно в одной строке: {old_lines[0]}")
else:
    err(f"старый бренд: {len(old_lines)} строк, нужна 1 в llms.txt: {old_lines}")

# 4. Длинное тире в своих текстах (статья Максима проверяется отдельно, в ней его нет)
for f in PUBLISHED:
    n = f.read_text(encoding="utf-8").count("—")
    if n: warn(f"{f.relative_to(ROOT).as_posix()}: длинных тире {n}")

# 5. robots, IndexNow, .nojekyll
robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
(ok if f"Sitemap: {HOST}/sitemap.xml" in robots else err)("robots.txt: строка Sitemap")
keys = [p for p in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem)]
if len(keys) == 1 and keys[0].read_text(encoding="utf-8").strip() == keys[0].stem:
    ok(f"IndexNow: {keys[0].name}, ключ внутри совпадает с именем")
else:
    err(f"IndexNow: файлов-ключей {len(keys)} или ключ не совпадает")
(ok if (ROOT / ".nojekyll").exists() else err)(".nojekyll")

# 6. Живые внешние ссылки
if "--offline" not in sys.argv:
    import urllib.request
    text = "".join(f.read_text(encoding="utf-8") for f in PUBLISHED if f.suffix in (".html", ".txt"))
    urls = sorted(set(u.rstrip(".,") for u in re.findall(r'https://[^"\s)<]+', text)
                      if not u.startswith(HOST + "/") or u.startswith((HOST + "/prompts/", HOST + "/guide/"))))
    urls = [u for u in urls if "fonts.g" not in u and "schema.org" not in u and "sitemaps.org" not in u]
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 Chrome/129.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                code, body = r.status, r.read(200_000).decode("utf-8", "ignore")
            if "telegra.ph" in u and "<title>Telegraph</title>" in body:
                code = "200-EMPTY"
        except Exception as e:
            code = getattr(e, "code", None) or f"ERR {str(e)[:50]}"
        (print if code == 200 else err)(f"{code} {u[:110]}")
    print(f"внешних ссылок {len(urls)}")

print(f"\nИТОГ: ошибок {len(errors)}, предупреждений {len(warns)}")
sys.exit(1 if errors else 0)
