#!/usr/bin/env python3
"""catalog.yaml に登録された怪談を取得して stories/ に正規化保存する。

使い方:
    python3 tools/collect.py            # 未取得のエントリだけ取得
    python3 tools/collect.py --force    # 取得済みも再取得
    python3 tools/collect.py --only hasshaku-sama kunekune
依存: PyYAML
"""
import argparse
import datetime
import hashlib
import html
import html.parser
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "stories"
RAW = ROOT / "raw"
USER_AGENT = "kaidan-archive/0.1 (personal archiving; polite crawler)"
REQUEST_INTERVAL = 1.5  # 秒。取得元に負荷をかけない

_last_request = 0.0


def fetch(url: str, binary: bool = False):
    """礼儀正しく(間隔を空けて)URLを取得する。"""
    global _last_request
    wait = REQUEST_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        content_type = r.headers.get("Content-Type", "")
    _last_request = time.monotonic()
    if binary:
        return data, content_type
    return data, content_type


def fetch_json(url: str):
    data, _ = fetch(url)
    return json.loads(data)


# ---------------------------------------------------------------- HTML → テキスト

_BLOCK_END = re.compile(r"</(p|div|h[1-6]|li|blockquote|tr|table|section|article)>", re.I)
_BR = re.compile(r"<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)


def html_to_text(fragment: str) -> str:
    """HTML断片を、改行構造を保ったプレーンテキストにする。

    2ch由来の本文はレス番号ヘッダや字下げに意味があるため、
    行頭の空白(全角含む)は保持し、行末の空白だけ落とす。
    """
    s = _SCRIPT.sub("", fragment)
    s = _COMMENT.sub("", s)
    s = _BR.sub("\n", s)
    s = _BLOCK_END.sub("\n\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in s.split("\n")]
    s = "\n".join(lines)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip("\n") + "\n"


# ---------------------------------------------------------------- WordPress 取得

_category_cache: dict[str, dict[int, str]] = {}


def wp_category_names(api: str, ids: list[int]) -> list[str]:
    cache = _category_cache.setdefault(api, {})
    missing = [i for i in ids if i not in cache]
    if missing:
        q = ",".join(map(str, missing))
        try:
            cats = fetch_json(f"{api}/categories?include={q}&per_page=100&_fields=id,name")
            for c in cats:
                cache[c["id"]] = html.unescape(c["name"])
        except Exception as e:
            print(f"    (カテゴリ名の取得に失敗: {e})")
    return [cache[i] for i in ids if i in cache]


def wp_resolve_post(entry: dict) -> dict | None:
    """post_id → slug → 完全一致タイトル検索 の順で記事を特定する。"""
    src = entry["source"]
    api = src["api"].rstrip("/")
    fields = "_fields=id,slug,link,title,date,modified,content,categories"

    if "post_id" in src:
        return fetch_json(f"{api}/posts/{src['post_id']}?{fields}")

    title = entry["title"]
    q = urllib.parse.quote(src.get("post_slug", title))
    posts = fetch_json(f"{api}/posts?slug={q}&{fields}")
    if posts:
        return posts[0]

    q = urllib.parse.quote(title)
    posts = fetch_json(f"{api}/posts?search={q}&per_page=50&{fields}")
    exact = [p for p in posts if html.unescape(p["title"]["rendered"]).strip() == title]
    if len(exact) == 1:
        return exact[0]
    if exact:
        print(f"    タイトル完全一致が複数あります。catalog.yaml に post_id を指定してください:")
        for p in exact:
            print(f"      id={p['id']} {p['link']}")
    else:
        print(f"    記事を特定できませんでした(検索ヒット {len(posts)} 件、完全一致なし)")
    return None


def collect_wordpress(entry: dict) -> dict | None:
    src = entry["source"]
    api = src["api"].rstrip("/")
    post = wp_resolve_post(entry)
    if post is None:
        return None

    (RAW / f"{entry['slug']}.json").write_text(
        json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    text = html_to_text(post["content"]["rendered"])
    return {
        "text": text,
        "source_meta": {
            "site": src.get("site", urllib.parse.urlparse(api).netloc),
            "url": post["link"],
            "api": f"{api}/posts/{post['id']}",
            "post_id": post["id"],
            "post_date": post.get("date"),
            "categories": wp_category_names(api, post.get("categories", [])),
        },
    }


# ---------------------------------------------------------------- 汎用URL取得

_CHARSET_META = re.compile(rb"charset=[\"']?([\w-]+)", re.I)
_CONTENT_HINTS = [
    re.compile(r"<article\b.*?</article>", re.I | re.S),
    re.compile(r"<div[^>]+(?:id|class)=\"[^\"]*(?:entry-content|article-body|post-content|main-content)[^\"]*\".*?</div>", re.I | re.S),
    re.compile(r"<main\b.*?</main>", re.I | re.S),
    re.compile(r"<body\b.*?</body>", re.I | re.S),
]


def decode_html(data: bytes, content_type: str) -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = _CHARSET_META.search(data[:4096])
        enc = m.group(1).decode("ascii", "replace") if m else None
    for candidate in filter(None, [enc, "utf-8", "cp932", "euc-jp"]):
        try:
            return data.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")


def collect_url(entry: dict) -> dict | None:
    """まとめサイトなど任意のページ。生HTMLを必ず保存し、本文抽出は近似。"""
    url = entry["source"]["url"]
    data, content_type = fetch(url, binary=True)
    (RAW / f"{entry['slug']}.html").write_bytes(data)
    page = decode_html(data, content_type)
    fragment = page
    for pat in _CONTENT_HINTS:
        m = pat.search(page)
        if m:
            fragment = m.group(0)
            break
    return {
        "text": html_to_text(fragment),
        "source_meta": {
            "site": urllib.parse.urlparse(url).netloc,
            "url": url,
            "extraction": "heuristic",  # 手作業での整形を推奨
        },
    }


# ---------------------------------------------------------------- 保存

_DATE_FULL = re.compile(r"\b((?:19|20)\d{2})/(\d{1,2})/(\d{1,2})")
_DATE_2CH = re.compile(r"\b(\d{2})/(\d{2})/(\d{2})\b")  # 旧2ch形式 03/07/21


def original_post_date(text: str) -> str | None:
    """本文冒頭のレスヘッダから元の掲示板投稿日を拾う。"""
    head = text[:500]
    m = _DATE_FULL.search(head)
    if m:
        y, mo, d = m.groups()
    else:
        m = _DATE_2CH.search(head)
        if not m:
            return None
        y, mo, d = m.groups()
        y = "20" + y
    try:
        return datetime.date(int(y), int(mo), int(d)).isoformat()
    except ValueError:
        return None


def write_story(entry: dict, result: dict):
    text = result["text"]
    front = {
        "title": entry["title"],
        "slug": entry["slug"],
    }
    for key in ("aliases", "tags", "note", "origin"):
        if entry.get(key):
            front[key] = entry[key]
    posted = original_post_date(text)
    if posted:
        front["original_post_date"] = posted
    front["source"] = result["source_meta"]
    front["fetched_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    front["chars"] = len(text)
    front["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    out = STORIES / f"{entry['slug']}.md"
    out.write_text(f"---\n{fm}---\n\n# {entry['title']}\n\n{text}", encoding="utf-8")
    print(f"    -> {out.relative_to(ROOT)} ({len(text)}字)")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="このslugだけ取得")
    ap.add_argument("--force", action="store_true", help="取得済みでも再取得")
    args = ap.parse_args()

    catalog = yaml.safe_load((ROOT / "catalog.yaml").read_text(encoding="utf-8"))
    STORIES.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)

    ok = skipped = failed = 0
    for entry in catalog["stories"]:
        slug = entry["slug"]
        if args.only and slug not in args.only:
            continue
        if entry.get("status") == "wanted":
            if args.only:
                print(f"[{slug}] status: wanted(取得元未定)のためスキップ")
            skipped += 1
            continue
        out = STORIES / f"{slug}.md"
        if out.exists() and not args.force:
            skipped += 1
            continue

        print(f"[{slug}] {entry['title']} を取得中…")
        try:
            src_type = entry["source"]["type"]
            if src_type == "wordpress":
                result = collect_wordpress(entry)
            elif src_type == "url":
                result = collect_url(entry)
            else:
                print(f"    未対応の source type: {src_type}")
                result = None
            if result is None:
                failed += 1
                continue
            write_story(entry, result)
            ok += 1
        except Exception as e:
            print(f"    失敗: {e}")
            failed += 1

    print(f"\n取得 {ok} / スキップ {skipped} / 失敗 {failed}")
    if ok:
        # 索引を作り直す
        sys.path.insert(0, str(ROOT / "tools"))
        import build_index
        build_index.main()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
