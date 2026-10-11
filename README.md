# AUREUS | Нейросети · сайт-визитка

Корень user-site GitHub Pages: https://mgromov688-boop.github.io/ (репозиторий `mgromov688-boop.github.io`).
Задача: чтобы канал AUREUS | Нейросети (@aureus_ai_hub) находили Bing, Google и нейросети.

- `index.html`: визитка, JSON-LD Organization + WebSite + ItemList гайдов
- `llms.txt`, `robots.txt`, `sitemap.xml`: для поисковиков и AI-ботов
- `b0b27684987cf21da5b83d0bc573b099.txt`: ключ IndexNow
- `blog/`: статьи, собираются скриптом

## Новая статья

```
python tools/new_post.py статья.md --slug latinica-cherez-defis --date 2026-10-12 --description "140–160 знаков" --bot-key skills3
python tools/site_check.py
```

`--send` в конце команды отправит статью в IndexNow (только после push). Отдельно: `python tools/indexnow.py --slug <slug> --send`
или `python tools/indexnow.py --send` (все адреса sitemap). Без `--send` скрипт только печатает запрос.

Ссылки: `python tools/check_links.py` проверяет, что ссылки живые и что все 6 ссылок «на нас» стоят на каждой странице.
`googlec4cd04ac9e675f2f.html` — подтверждение Google Search Console, не удалять.

`new_post.py` пишет `blog/<slug>/index.html` и обновляет `blog/index.html`, блок «Блог» на главной, `sitemap.xml`, `llms.txt`, `tools/posts.json`.
Команды установки в публичной статье скрипт не пропускает. Ссылка на бота получает метку `_site`.

Просмотр локально: `node tools/serve.mjs` → http://localhost:8765/

Не класть в корень папки `prompts/` и `guide/`: эти адреса отдают соседние репозитории.
