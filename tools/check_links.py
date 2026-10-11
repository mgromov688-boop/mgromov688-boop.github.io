"""Проверка ссылок сайта AUREUS: живы ли, ведут ли «на нас», стоят ли ссылки «на нас» на каждой странице.

    python tools/check_links.py            # с сетью
    python tools/check_links.py --offline  # только наличие ссылок «на нас» и внутренние адреса

Обходит index.html, blog/**/*.html, llms.txt, sitemap.xml.
Статусы: OK · НЕ ПРОВЕРЕНО (площадка отдаёт антибот-страницу, по ответу не понять, жив ли профиль) · ОШИБКА.
Код возврата 1, если есть ОШИБКА. «Не проверено» ошибкой не считается, но печатается отдельной строкой в итоге:
молчание о непроверенном было бы ложным зелёным.
"""
import pathlib, re, sys, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = "https://mgromov688-boop.github.io"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36",
      "Accept-Language": "ru,en;q=0.8"}

# Ссылки «на нас»: на каждой HTML-странице должна быть каждая из них.
OURS = {
    "Telegram-канал": r"https://t\.me/aureus_ai_hub(?![\w/])",
    "бот с меткой start": r"https://t\.me/MaximToshaBot\?start=[A-Za-z0-9_]+",
    "YouTube": r"https://www\.youtube\.com/@aureus_ai_hub",
    "Instagram": r"https://www\.instagram\.com/aureus_ai_hub/?",
    "TikTok": r"https://www\.tiktok\.com/@aureus_ai_hub",
    "Threads": r"https://www\.threads\.com/@aureus_ai_hub",
}
# Что должно быть в ответе, чтобы ссылка считалась ведущей именно на нас.
EXPECT = [
    (r"^https://t\.me/aureus_ai_hub", ["AUREUS"]),
    (r"^https://t\.me/MaximToshaBot", ["Aureus", "MaximToshaBot"]),
    (r"^https://www\.youtube\.com/(@aureus_ai_hub|channel/UCxvb_2dgvJiUAKXavV8NHvQ)", ["aureus_ai_hub", "AUREUS"]),
]
ANTIBOT = ("instagram.com", "tiktok.com", "threads.com", "threads.net")
OLD = re.compile(r"ClaudeCodich|claudecodich", re.I)
SKIP = ("fonts.googleapis.com", "fonts.gstatic.com", "schema.org", "sitemaps.org", "api.indexnow.org")


def sources():
    files = [ROOT / "index.html", ROOT / "llms.txt", ROOT / "sitemap.xml"] + sorted((ROOT / "blog").rglob("*.html"))
    return [f for f in files if f.is_file()]


def links(text: str) -> set[str]:
    found = set(re.findall(r'(?:href|src)="([^"]+)"', text))
    found |= set(re.findall(r"https://[^\s\"'<>)\]]+", text))
    return {u.rstrip(".,;") for u in found if not u.startswith(("#", "mailto:", "data:"))}


def local_target(path: str) -> pathlib.Path | None:
    p = ROOT / path.split("#")[0].split("?")[0].lstrip("/")
    for c in (p, p / "index.html"):
        if c.is_file():
            return c
    return None


def check_remote(u: str) -> tuple[str, str]:
    try:
        req = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            code, final, body = r.status, r.geturl(), r.read(3_000_000).decode("utf-8", "ignore")  # YouTube кладёт имя канала после 800 КБ
    except urllib.error.HTTPError as e:
        if any(d in u for d in ANTIBOT):
            return "НЕ ПРОВЕРЕНО", f"{e.code}, антибот площадки"
        return "ОШИБКА", f"HTTP {e.code}"
    except Exception as e:
        return "ОШИБКА", str(e)[:70]
    redirected = f" → {final}" if final.rstrip("/") != u.rstrip("/") else ""
    if code not in (200, 301):
        return "ОШИБКА", f"HTTP {code}{redirected}"
    if "telegra.ph" in u and "<title>Telegraph</title>" in body:
        return "ОШИБКА", "200, но страница Telegraph пустая"
    for rx, words in EXPECT:
        if re.search(rx, u):
            hit = [w for w in words if w in body]
            return ("OK", f"200, имя «{hit[0]}» на странице{redirected}") if hit else \
                   ("ОШИБКА", f"200, но имени {words} на странице нет{redirected}")
    if any(d in u for d in ANTIBOT):
        return ("OK", "200, имя на странице") if "aureus_ai_hub" in body else \
               ("НЕ ПРОВЕРЕНО", "200, страница без имени (антибот или вход)")
    if "/aureus_ai_hub" in u or "MaximToshaBot" in u:
        return ("OK", "200") if re.search("aureus|MaximToshaBot", body, re.I) else ("НЕ ПРОВЕРЕНО", "200, имени нет")
    return "OK", f"{code}{redirected}"


def main():
    offline = "--offline" in sys.argv
    errors, unverified = [], []
    all_links: dict[str, set[str]] = {}

    print("== Ссылки «на нас» на каждой странице ==")
    for f in sources():
        rel = f.relative_to(ROOT).as_posix()
        text = f.read_text(encoding="utf-8")
        for u in links(text):
            all_links.setdefault(u, set()).add(rel)
        if OLD.search(text) and rel != "llms.txt":
            errors.append(f"{rel}: старый адрес ClaudeCodich")
            print(f"ОШИБКА {rel}: старый адрес ClaudeCodich")
        if f.suffix != ".html":
            continue
        missing = [name for name, rx in OURS.items() if not re.search(rx, text)]
        if missing:
            errors.append(f"{rel}: нет ссылок {missing}")
            print(f"ОШИБКА {rel}: нет {', '.join(missing)}")
        else:
            print(f"OK     {rel}: все {len(OURS)} ссылок на месте")

    print("\n== Внутренние адреса ==")
    for u, where in sorted(all_links.items()):
        path = u[len(HOST):] if u.startswith(HOST) else (u if u.startswith("/") else None)
        if path is None or path.startswith(("/prompts/", "/guide/")):
            continue
        if local_target(path):
            print(f"OK     {path}")
        else:
            errors.append(f"нет файла для {path} ({', '.join(sorted(where))})")
            print(f"ОШИБКА {path}: нет в папке сайта ({', '.join(sorted(where))})")

    if not offline:
        print("\n== Внешние адреса ==")
        remote = sorted(u for u in all_links if u.startswith("http") and not any(s in u for s in SKIP)
                        and (not u.startswith(HOST) or u.startswith((HOST + "/prompts/", HOST + "/guide/"))))
        for u in remote:
            status, note = check_remote(u)
            where = ", ".join(sorted(all_links[u]))
            print(f"{status:<12} {u[:105]} | {note} | {where}")
            if status == "ОШИБКА":
                errors.append(f"{u}: {note}")
            elif status == "НЕ ПРОВЕРЕНО":
                unverified.append(u)
        print(f"\nвнешних адресов {len(remote)}")

    print(f"\nИТОГ: ошибок {len(errors)}, не проверено {len(unverified)}")
    for u in unverified:
        print(f"  не проверено: {u}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
