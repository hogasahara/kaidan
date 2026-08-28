#!/usr/bin/env python3
"""stories/ と catalog.yaml から GitHub Pages 用の静的サイトを docs/ に生成する。

- docs/index.html      蔵書目録(トップページ)
- docs/s/<slug>.html   各話の閲覧ページ
- docs/style.css       共通スタイル(ダークモード対応)
"""
import html
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "stories"
DOCS = ROOT / "docs"

SITE_TITLE = "kaidan"
SITE_SUBTITLE = "ネットロア怪談 蒐集庫"
REPO_URL = "https://github.com/hogasahara/kaidan"

# 2chのレスヘッダらしい行(レス番号+日付)を検出して控えめに表示する
_RES_HEADER = re.compile(
    r"^\s*\d+.*(?:(?:19|20)\d{2}/\d{1,2}/\d{1,2}|\d{2}/\d{2}/\d{2}\b)"
)

STYLE = """\
:root {
  --bg: #f7f5f0;
  --fg: #2b2a28;
  --muted: #8a857c;
  --line: #e2ddd3;
  --accent: #8c1c13;
  --card: #fffdf8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #131313;
    --fg: #d6d2c9;
    --muted: #7d7970;
    --line: #2a2a2a;
    --accent: #c25b4e;
    --card: #1a1a1a;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: "Hiragino Mincho ProN", "Yu Mincho", "Noto Serif JP", serif;
  line-height: 2;
  font-size: 16px;
  overflow-wrap: anywhere;
}
.wrap { max-width: 40rem; margin: 0 auto; padding: 1.4rem 1.2rem 4rem; }
a { color: inherit; }
header.site { margin: 1.5rem 0 2.2rem; }
header.site h1 {
  font-size: 1.5rem; letter-spacing: .3em; margin: 0;
  font-weight: 600;
}
header.site h1 a { text-decoration: none; }
header.site p { margin: .2rem 0 0; color: var(--muted); font-size: .8rem; letter-spacing: .15em; }

/* --- 目録 --- */
ul.catalog { list-style: none; margin: 0; padding: 0; }
ul.catalog li {
  border-bottom: 1px solid var(--line);
  padding: 0;
}
ul.catalog a {
  display: block; text-decoration: none; padding: .9rem .2rem;
}
ul.catalog a:active { background: var(--card); }
.story-title { font-size: 1.05rem; }
.meta {
  font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
  color: var(--muted); font-size: .72rem; letter-spacing: .05em;
  line-height: 1.6; margin-top: .15rem;
}
.meta .tag { margin-right: .6em; }
h2.section {
  font-size: .85rem; color: var(--muted); letter-spacing: .3em;
  font-weight: 600; margin: 2.5rem 0 .5rem; border-bottom: 1px solid var(--line);
  padding-bottom: .4rem;
}
ul.wanted { list-style: none; margin: 0; padding: 0; color: var(--muted); font-size: .85rem; }
ul.wanted li { padding: .4rem .2rem; }

/* --- 作品ページ --- */
article h1 {
  font-size: 1.45rem; font-weight: 600; letter-spacing: .1em;
  margin: 0 0 .3rem;
}
article .meta { margin-bottom: 2.2rem; }
article .meta a { color: var(--muted); }
.body p { margin: 1.4em 0; }
.body .res {
  display: block;
  font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
  color: var(--muted); font-size: .72rem; line-height: 1.5;
  margin: 2.4em 0 1.2em;
}
.note {
  font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
  background: var(--card); border: 1px solid var(--line);
  padding: .6rem .9rem; border-radius: .4rem;
  font-size: .8rem; color: var(--muted); margin: 0 0 2rem;
}
nav.pager {
  display: flex; justify-content: space-between; gap: 1rem;
  margin-top: 3.5rem; border-top: 1px solid var(--line); padding-top: 1.2rem;
  font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
  font-size: .85rem;
}
nav.pager a { text-decoration: none; color: var(--accent); max-width: 45%; }
nav.pager .home { color: var(--muted); }
footer.site {
  margin-top: 4rem; border-top: 1px solid var(--line); padding-top: 1rem;
  font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
  color: var(--muted); font-size: .72rem; line-height: 1.7;
}
"""

PAGE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<div class="wrap">
{body}
<footer class="site">
収録作品は匿名掲示板に投稿された文章のアーカイブです。著作権は各投稿者にあります。
出典は各ページに記載。<a href="{repo}">リポジトリ</a>
</footer>
</div>
</body>
</html>
"""


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def read_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    body = text[end + 5:]
    # 生成時に付けた「# タイトル」見出しは本文から除く
    body = re.sub(r"^\s*# .*\n", "", body, count=1)
    return fm, body.strip("\n")


def reading_minutes(chars: int) -> int:
    return max(1, round(chars / 600))


def story_meta_html(fm: dict) -> str:
    parts = []
    if fm.get("original_post_date"):
        parts.append(esc(fm["original_post_date"]))
    for t in fm.get("tags") or []:
        parts.append(f'<span class="tag">#{esc(t)}</span>')
    parts.append(f"約{reading_minutes(fm.get('chars', 0))}分")
    return " ・ ".join(parts)


def body_html(body: str) -> str:
    """空行で段落、単一改行は<br>。レスヘッダ行は控えめな書体にする。"""
    out = []
    for block in re.split(r"\n{2,}", body):
        lines = []
        for line in block.split("\n"):
            if _RES_HEADER.match(line):
                lines.append(f'<span class="res">{esc(line)}</span>')
            else:
                lines.append(esc(line))
        out.append("<p>" + "<br>\n".join(lines) + "</p>")
    return "\n".join(out)


def build_story_page(fm: dict, body: str, prev_fm, next_fm) -> str:
    src = fm.get("source", {})
    meta = story_meta_html(fm)
    if src.get("url"):
        meta += f' ・ <a href="{html.escape(src["url"])}">出典: {esc(src.get("site", "取得元"))}</a>'

    note = f'<div class="note">{esc(fm["note"])}</div>' if fm.get("note") else ""

    pager = ['<nav class="pager">']
    pager.append(
        f'<a href="{prev_fm["slug"]}.html">← {esc(prev_fm["title"])}</a>' if prev_fm else "<span></span>"
    )
    pager.append('<a class="home" href="../index.html">目録</a>')
    pager.append(
        f'<a href="{next_fm["slug"]}.html">{esc(next_fm["title"])} →</a>' if next_fm else "<span></span>"
    )
    pager.append("</nav>")

    content = f"""\
<header class="site"><p><a href="../index.html" style="text-decoration:none">{SITE_TITLE} ─ {SITE_SUBTITLE}</a></p></header>
<article>
<h1>{esc(fm["title"])}</h1>
<div class="meta">{meta}</div>
{note}
<div class="body">
{body_html(body)}
</div>
</article>
{"".join(pager)}"""
    return PAGE.format(title=f"{fm['title']} | {SITE_TITLE}", root="../", repo=REPO_URL, body=content)


def build_index_page(stories: list[dict], wanted: list[dict]) -> str:
    items = []
    for fm in stories:
        items.append(
            f'<li><a href="s/{fm["slug"]}.html">'
            f'<span class="story-title">{esc(fm["title"])}</span>'
            f'<div class="meta">{story_meta_html(fm)}</div></a></li>'
        )
    body = f"""\
<header class="site">
<h1><a href="index.html">{SITE_TITLE}</a></h1>
<p>{SITE_SUBTITLE} ── {len(stories)}話</p>
</header>
<ul class="catalog">
{chr(10).join(items)}
</ul>"""
    if wanted:
        rows = "".join(
            f"<li>{esc(e['title'])}" + (f" ── {esc(e['note'])}" if e.get("note") else "") + "</li>"
            for e in wanted
        )
        body += f'\n<h2 class="section">未収集</h2>\n<ul class="wanted">{rows}</ul>'
    return PAGE.format(title=f"{SITE_TITLE} — {SITE_SUBTITLE}", root="", repo=REPO_URL, body=body)


def main():
    catalog = yaml.safe_load((ROOT / "catalog.yaml").read_text(encoding="utf-8"))
    order = [e["slug"] for e in catalog["stories"]]
    wanted = [e for e in catalog["stories"] if e.get("status") == "wanted"]

    loaded = {}
    for path in STORIES.glob("*.md"):
        fm, body = read_frontmatter(path)
        loaded[fm["slug"]] = (fm, body)

    # catalog の並び順(=手で決めた順)を保ち、catalog外の話は末尾へ
    slugs = [s for s in order if s in loaded] + [s for s in loaded if s not in order]

    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "s").mkdir(parents=True)
    (DOCS / ".nojekyll").write_text("")
    (DOCS / "style.css").write_text(STYLE, encoding="utf-8")

    fms = [loaded[s][0] for s in slugs]
    for i, slug in enumerate(slugs):
        fm, body = loaded[slug]
        prev_fm = fms[i - 1] if i > 0 else None
        next_fm = fms[i + 1] if i + 1 < len(fms) else None
        (DOCS / "s" / f"{slug}.html").write_text(
            build_story_page(fm, body, prev_fm, next_fm), encoding="utf-8"
        )

    (DOCS / "index.html").write_text(build_index_page(fms, wanted), encoding="utf-8")
    print(f"docs/ を生成({len(slugs)}話+目録)")


if __name__ == "__main__":
    sys.exit(main())
