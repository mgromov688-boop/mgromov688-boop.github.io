r"""Новая статья блога AUREUS: md → blog/<slug>/index.html + обновление blog/index, главной, sitemap.xml, llms.txt.

    python tools/new_post.py статья.md --slug claude-code-3-skilla-montazh --date 2026-10-11 \
        --description "140–160 знаков для поисковика" [--bot-key skills3] [--dry]

Формат md тот же, что у telegraph_publish.py: первая строка заголовок, дальше **жирный**, _курсив_,
`код`, [текст](url), > цитата, ## подзаголовок, ---, ![подпись](url), списки «- » и «1. ».
Ссылки на бота ?start=<ключ>_<метка> переписываются на <ключ>_site: так в gate_log видно, что человек пришёл с сайта.
Статья публичная: блоки кода и команды установки скрипт не пропускает (флаг --allow-commands снимает запрет).
Повторный запуск с тем же --slug перезаписывает статью, а не плодит дубль.
"""
import argparse, datetime, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = "https://mgromov688-boop.github.io"
ORG = f"{HOST}/#org"
REGISTRY = ROOT / "tools" / "posts.json"
TEMPLATE = ROOT / "tools" / "post_template.html"
BOT = "https://t.me/MaximToshaBot"
CHANNEL = "https://t.me/aureus_ai_hub"
LATEST_ON_HOME = 5
# Подвал «на нас»: стоит на каждой странице, его наличие проверяет tools/check_links.py.
SOCIAL = """  <nav aria-label="AUREUS | Нейросети в соцсетях">
    <a href="https://t.me/aureus_ai_hub" rel="me">Telegram</a>
    <a href="https://www.instagram.com/aureus_ai_hub/" rel="me">Instagram</a>
    <a href="https://www.tiktok.com/@aureus_ai_hub" rel="me">TikTok</a>
    <a href="https://www.youtube.com/@aureus_ai_hub" rel="me">YouTube</a>
    <a href="https://www.threads.com/@aureus_ai_hub" rel="me">Threads</a>
    <a href="https://t.me/MaximToshaBot?start={key}_site">Бот @MaximToshaBot</a>
  </nav>"""

# Адреса этого хоста, которые живут в других репозиториях (prompts, guide) или в корне.
# courses-h3rkqlfs сюда не входит: страница отдаёт noindex и выдаётся только за подписку (решение Максима 10.10).
SITEMAP_STATIC = [
    ("/", "1.0", "weekly"),
    ("/llms.txt", "0.6", "weekly"),
    ("/blog/", "0.8", "daily"),
    ("/prompts/cc-guide/", "0.7", "monthly"),
    ("/prompts/cc-guide-2/", "0.7", "monthly"),
    ("/guide/", "0.7", "monthly"),
    ("/prompts/guide/", "0.6", "monthly"),
]
STATIC_LASTMOD = "2026-10-11"

COMMAND_RX = re.compile(r"^\s*(```|\$ |npx |npm i|npm install|pip install|git clone|claude mcp|curl |winget |brew )", re.M)


# ---------- markdown → html ----------
def inline(text: str) -> str:
    keep = []

    def stash(s):
        keep.append(s)
        return f"\x00{len(keep) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: stash(f'<a href="{html.escape(m.group(2), quote=True)}">{inline_plain(m.group(1))}</a>'), text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w/])_(.+?)_(?![\w])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], text)


def inline_plain(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"(?<![\w/])_(.+?)_(?![\w])", r"<em>\1</em>", text)


def md_to_html(md: str) -> str:
    out, para, lst, quote = [], [], None, []

    def flush():
        nonlocal para, lst, quote
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>")
            lst = None
        if quote:
            out.append(f"<blockquote><p>{inline(' '.join(quote))}</p></blockquote>")
            quote = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush(); continue
        if m := re.match(r"^(#{2,3})\s+(.*)", line):
            flush(); lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); continue
        if re.match(r"^-{3,}$", line.strip()):
            flush(); out.append("<hr>"); continue
        if m := re.match(r"^!\[([^\]]*)\]\(([^)\s]+)\)$", line.strip()):
            flush(); alt = html.escape(m.group(1), quote=True)
            out.append(f'<figure><img src="{html.escape(m.group(2), quote=True)}" alt="{alt}" loading="lazy">'
                       + (f"<figcaption>{inline(m.group(1))}</figcaption>" if m.group(1) else "") + "</figure>")
            continue
        if line.startswith(">"):
            if para or lst: flush()
            quote.append(line.lstrip("> ").strip()); continue
        if m := re.match(r"^\s*(?:[-*]|(\d+)\.)\s+(.*)", line):
            tag = "ol" if m.group(1) else "ul"
            if para or quote: flush()
            if lst and lst[0] != tag: flush()
            if not lst: lst = (tag, [])
            lst[1].append(m.group(2)); continue
        if lst or quote: flush()
        para.append(line.strip())
    flush()
    return "\n".join(out)


# ---------- helpers ----------
def ru_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def plain(md_line: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md_line)
    return re.sub(r"[*_`]", "", s).strip()


def auto_description(body_md: str) -> str:
    for line in body_md.splitlines():
        t = plain(line)
        if t and not line.startswith(("#", ">", "-", "!")):
            if len(t) <= 160:
                return t
            cut = t[:157].rsplit(" ", 1)[0]
            return cut.rstrip(",.:;") + "..."
    return ""


def retag_bot(md: str, bot_key: str | None) -> str:
    def sub(m):
        key = bot_key or m.group(1).rpartition("_")[0] or m.group(1)
        return f"{BOT}?start={key}_site"
    return re.sub(r"https://t\.me/MaximToshaBot\?start=([A-Za-z0-9_]+)", sub, md)


def replace_between(text: str, start: str, end: str, new: str) -> str:
    i, j = text.find(start), text.find(end)
    if i < 0 or j < 0 or j < i:
        sys.exit(f"не найдены метки {start!r} … {end!r}")
    return text[: i + len(start)] + "\n" + new + "\n" + text[j:]


# ---------- builders ----------
def build_post(meta: dict, body_html: str) -> str:
    url = f"{HOST}/blog/{meta['slug']}/"
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": url + "#article",
                "headline": meta["title"],
                "description": meta["description"],
                "datePublished": meta["date"],
                "dateModified": meta.get("modified", meta["date"]),
                "inLanguage": "ru",
                "mainEntityOfPage": url,
                "url": url,
                "image": f"{HOST}/assets/aureus_logo_final_1254.png",
                "author": {"@type": "Organization", "@id": ORG, "name": "AUREUS | Нейросети", "url": HOST + "/"},
                "publisher": {"@type": "Organization", "@id": ORG, "name": "AUREUS | Нейросети",
                              "logo": {"@type": "ImageObject", "url": f"{HOST}/assets/aureus_logo_final_1254.png"}},
                "isPartOf": {"@type": "Blog", "@id": f"{HOST}/blog/#blog"},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "AUREUS | Нейросети", "item": HOST + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Блог", "item": f"{HOST}/blog/"},
                    {"@type": "ListItem", "position": 3, "name": meta["title"], "item": url},
                ],
            },
        ],
    }
    page = TEMPLATE.read_text(encoding="utf-8")
    rep = {
        "{{TITLE}}": html.escape(meta["title"], quote=True),
        "{{DESCRIPTION}}": html.escape(meta["description"], quote=True),
        "{{URL}}": url,
        "{{DATE_ISO}}": meta["date"],
        "{{DATE_RU}}": ru_date(meta["date"]),
        "{{BOT_URL}}": f"{BOT}?start={meta['bot_key']}_site" if meta.get("bot_key") else BOT,
        "{{JSONLD}}": json.dumps(ld, ensure_ascii=False, indent=2),
        "{{BODY}}": body_html,
        "{{SOCIAL}}": SOCIAL.format(key=meta.get("bot_key") or "skills3"),
    }
    for k, v in rep.items():
        page = page.replace(k, v)
    return page


def build_blog_index(posts: list[dict]) -> str:
    items = "\n".join(
        f'      <li><a href="/blog/{p["slug"]}/">{html.escape(p["title"])}</a><small>{ru_date(p["date"])}</small>'
        f'<p>{html.escape(p["description"])}</p></li>' for p in posts)
    ld = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "@id": f"{HOST}/blog/#blog",
        "name": "Блог AUREUS | Нейросети",
        "url": f"{HOST}/blog/",
        "inLanguage": "ru",
        "publisher": {"@type": "Organization", "@id": ORG, "name": "AUREUS | Нейросети"},
        "blogPost": [{"@type": "BlogPosting", "headline": p["title"], "url": f"{HOST}/blog/{p['slug']}/",
                      "datePublished": p["date"]} for p in posts],
    }
    social = SOCIAL.format(key=(posts[0].get("bot_key") if posts else None) or "skills3")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Блог AUREUS | Нейросети: разборы работы с нейросетями</title>
<meta name="description" content="Блог AUREUS | Нейросети (@aureus_ai_hub): как собираем ролики, автоматизации и рабочие связки на Claude Code и ChatGPT. Разборы с цифрами и затыками.">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<link rel="canonical" href="{HOST}/blog/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AUREUS | Нейросети">
<meta property="og:title" content="Блог AUREUS | Нейросети">
<meta property="og:url" content="{HOST}/blog/">
<meta property="og:image" content="{HOST}/assets/aureus_logo_final_1254.png">
<meta property="og:locale" content="ru_RU">
<link rel="icon" type="image/png" href="/assets/aureus_avatar_mark_512.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=2)}
</script>
</head>
<body>
<header class="wrap top"><a class="brand" href="/">AUREUS | Нейросети</a><a class="tg" href="{CHANNEL}">@aureus_ai_hub</a></header>
<main class="wrap">
  <h1>Блог</h1>
  <ol class="posts">
{items}
  </ol>
</main>
<footer class="wrap">
  <span class="tag">ADVANCING INTELLIGENCE</span>
  AUREUS | Нейросети · <a href="{CHANNEL}">t.me/aureus_ai_hub</a>
{social}
</footer>
</body>
</html>
"""


def build_sitemap(posts: list[dict]) -> str:
    newest = max([STATIC_LASTMOD] + [p.get("modified", p["date"]) for p in posts])
    rows = []
    for path, prio, freq in SITEMAP_STATIC:
        lm = newest if path in ("/", "/llms.txt", "/blog/") else STATIC_LASTMOD
        rows.append((HOST + path, lm, freq, prio))
    for p in posts:
        rows.append((f"{HOST}/blog/{p['slug']}/", p.get("modified", p["date"]), "monthly", "0.8"))
    body = "\n".join(
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{lm}</lastmod>\n    <changefreq>{f}</changefreq>\n    <priority>{pr}</priority>\n  </url>"
        for u, lm, f, pr in rows)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'


def update_llms(text: str, posts: list[dict]) -> str:
    block = "\n".join(f"- [{p['title']}]({HOST}/blog/{p['slug']}/): {ru_date(p['date'])}" for p in posts)
    m = re.search(r"^## Блог\n(.*?)(?=^## )", text, re.S | re.M)
    if not m:
        sys.exit("в llms.txt нет раздела «## Блог»")
    return text[: m.start(1)] + "\n" + block + "\n\n" + text[m.end(1):]


def update_home(text: str, posts: list[dict]) -> str:
    rows = "\n".join(
        f'      <li><a href="/blog/{p["slug"]}/">{html.escape(p["title"])}</a><small>{ru_date(p["date"])}</small></li>'
        for p in posts[:LATEST_ON_HOME])
    return replace_between(text, "<!-- blog:latest -->", "<!-- /blog:latest -->", rows)


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?", help="md-файл статьи; без него только пересборка индексов")
    ap.add_argument("--slug")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--description", help="мета-описание 140–160 знаков; без него берётся первый абзац")
    ap.add_argument("--bot-key", help="ключ гейта бота: skills3, courses… Без него берётся из ссылки в тексте")
    ap.add_argument("--allow-commands", action="store_true", help="пропустить блоки кода и команды установки")
    ap.add_argument("--keep-footer", action="store_true", help="оставить последнюю строку «AUREUS | Нейросети · …»")
    ap.add_argument("--dry", action="store_true", help="показать, что будет записано, ничего не трогая")
    ap.add_argument("--send", action="store_true",
                    help="после сборки отправить статью в IndexNow (только после push, когда сайт в сети)")
    a = ap.parse_args()

    posts = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else []
    writes = {}

    if a.src:
        if not a.slug or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", a.slug):
            sys.exit("--slug обязателен: латиница, цифры и дефисы, например claude-code-3-skilla-montazh")
        md = pathlib.Path(a.src).read_text(encoding="utf-8").strip("﻿\n ")
        title, _, body = md.partition("\n")
        title, body = title.lstrip("# ").strip(), body.strip()
        if not a.allow_commands and (hit := COMMAND_RX.search(body)):
            sys.exit(f"в статье команда или блок кода ({hit.group(0).strip()!r}). Публичная версия идёт без команд установки, "
                     "их место в гайде за подписку. Убери или запусти с --allow-commands")
        if not a.keep_footer:
            body = re.sub(r"\n+AUREUS \| Нейросети ·[^\n]*\s*$", "", body)
        body = retag_bot(body, a.bot_key)
        key = a.bot_key or (m.group(1).rpartition("_")[0] if (m := re.search(r"MaximToshaBot\?start=([A-Za-z0-9_]+)", body)) else None)
        old = next((p for p in posts if p["slug"] == a.slug), None)
        desc = a.description or (old["description"] if old else auto_description(body))
        if not 140 <= len(desc) <= 160:
            print(f"⚠ описание {len(desc)} знаков, норма 140–160: {desc}")
        meta = {"slug": a.slug, "title": title, "date": old["date"] if old else a.date, "description": desc,
                "bot_key": key, "source": str(pathlib.Path(a.src).resolve())}
        if old:
            meta["modified"] = a.date
        posts = [p for p in posts if p["slug"] != a.slug] + [meta]
        writes[ROOT / "blog" / a.slug / "index.html"] = build_post(meta, md_to_html(body))

    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    writes[REGISTRY] = json.dumps(posts, ensure_ascii=False, indent=2) + "\n"
    writes[ROOT / "blog" / "index.html"] = build_blog_index(posts)
    writes[ROOT / "sitemap.xml"] = build_sitemap(posts)
    writes[ROOT / "llms.txt"] = update_llms((ROOT / "llms.txt").read_text(encoding="utf-8"), posts)
    writes[ROOT / "index.html"] = update_home((ROOT / "index.html").read_text(encoding="utf-8"), posts)

    for path, content in writes.items():
        rel = path.relative_to(ROOT).as_posix()
        if a.dry:
            print(f"[dry] {rel}: {len(content)} знаков")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"записан {rel}")
    print(f"статей в блоге: {len(posts)}")

    if a.src and not a.dry:  # IndexNow после каждого поста; без --send только показывает запрос
        sys.path.insert(0, str(ROOT / "tools"))
        import indexnow
        indexnow.submit(indexnow.post_urls(a.slug), send=a.send)


if __name__ == "__main__":
    main()
