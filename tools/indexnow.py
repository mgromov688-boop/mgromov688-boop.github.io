"""IndexNow: сообщить Bing, Yandex и другим поисковикам о новых адресах сайта.

    python tools/indexnow.py                         # показать запрос по всем адресам sitemap, без отправки
    python tools/indexnow.py --slug claude-code-3-skilla-montazh   # статья + /blog/ + /sitemap.xml
    python tools/indexnow.py <url> [<url> ...]       # свои адреса
    ... --send                                       # отправить по-настоящему (только после push, когда ключ виден в сети)

Без --send ничего не отправляется. Перед отправкой скрипт сверяет, что файл ключа уже отдаётся сайтом:
иначе IndexNow ответит 403 и запомнит отказ.
"""
import argparse, json, pathlib, re, sys, urllib.request, xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = "mgromov688-boop.github.io"
BASE = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"


def key() -> str:
    files = [p for p in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem)]
    if len(files) != 1:
        sys.exit(f"файлов-ключей IndexNow в корне {len(files)}, нужен ровно один")
    k = files[0].read_text(encoding="utf-8").strip()
    if k != files[0].stem:
        sys.exit("ключ внутри файла не совпадает с его именем")
    return k


def sitemap_urls() -> list[str]:
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [e.text for e in ET.parse(ROOT / "sitemap.xml").getroot().findall("s:url/s:loc", ns)]


def post_urls(slug: str) -> list[str]:
    return [f"{BASE}/blog/{slug}/", f"{BASE}/blog/", f"{BASE}/sitemap.xml"]


def submit(urls: list[str], send: bool = False) -> int:
    k = key()
    bad = [u for u in urls if not u.startswith(BASE + "/")]
    if bad:
        sys.exit(f"IndexNow принимает только адреса своего хоста, чужие: {bad}")
    payload = {"host": HOST, "key": k, "keyLocation": f"{BASE}/{k}.txt", "urlList": urls}
    print("IndexNow запрос:", json.dumps(payload, ensure_ascii=False, indent=2))
    if not send:
        print("не отправлено: нужен --send (после push сайта)")
        return 0
    try:
        with urllib.request.urlopen(payload["keyLocation"], timeout=20) as r:
            live = r.read().decode("utf-8", "ignore").strip()
    except Exception as e:
        sys.exit(f"файл ключа ещё не отдаётся сайтом ({e}). Сначала push и сборка Pages, потом --send")
    if live != k:
        sys.exit("файл ключа на сайте отличается от локального")
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    meaning = {200: "принято", 202: "принято, ключ ещё проверяется", 400: "неверный запрос", 403: "ключ не найден на сайте",
               422: "адреса не с этого хоста", 429: "слишком часто"}.get(code, "неизвестный ответ")
    print(f"IndexNow ответ: {code} ({meaning}), адресов {len(urls)}")
    return 0 if code in (200, 202) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--slug", help="статья блога: отправит её, /blog/ и /sitemap.xml")
    ap.add_argument("--send", action="store_true", help="отправить по-настоящему")
    a = ap.parse_args()
    urls = a.urls or (post_urls(a.slug) if a.slug else sitemap_urls())
    sys.exit(submit(urls, a.send))


if __name__ == "__main__":
    main()
