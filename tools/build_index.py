#!/usr/bin/env python3
"""stories/ と catalog.yaml から INDEX.md(蔵書目録)を生成する。"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "stories"


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def main():
    catalog = yaml.safe_load((ROOT / "catalog.yaml").read_text(encoding="utf-8"))
    collected = {}
    for path in sorted(STORIES.glob("*.md")):
        fm = read_frontmatter(path)
        if fm:
            collected[fm["slug"]] = (fm, path)

    lines = [
        "# 蔵書目録",
        "",
        "`tools/build_index.py` が生成する。手で編集しない。",
        "",
        f"収集済み **{len(collected)}** 話",
        "",
        "| タイトル | 投稿日 | タグ | 文字数 | 取得元 |",
        "|---|---|---|---|---|",
    ]

    # catalog.yaml の並び順を保つ
    order = [e["slug"] for e in catalog["stories"]]
    wanted = []
    for entry in catalog["stories"]:
        slug = entry["slug"]
        if slug not in collected:
            if entry.get("status") == "wanted":
                wanted.append(entry)
            continue
        fm, path = collected[slug]
        src = fm.get("source", {})
        date = fm.get("original_post_date") or ""
        tags = " ".join(fm.get("tags") or [])
        link = f"[{src.get('site', '取得元')}]({src['url']})" if src.get("url") else ""
        rel = path.relative_to(ROOT)
        lines.append(
            f"| [{fm['title']}]({rel}) | {date} | {tags} | {fm.get('chars', '')} | {link} |"
        )
    # catalog に無いが stories/ にあるもの(手動追加)も載せる
    for slug, (fm, path) in collected.items():
        if slug in order:
            continue
        src = fm.get("source", {})
        link = f"[{src.get('site', '取得元')}]({src['url']})" if src.get("url") else ""
        lines.append(
            f"| [{fm['title']}]({path.relative_to(ROOT)}) | | "
            f"{' '.join(fm.get('tags') or [])} | {fm.get('chars', '')} | {link} |"
        )

    if wanted:
        lines += ["", "## 未収集(取得元を探している話)", ""]
        for entry in wanted:
            note = f" — {entry['note']}" if entry.get("note") else ""
            lines.append(f"- **{entry['title']}**{note}")

    (ROOT / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"INDEX.md を更新({len(collected)}話、未収集{len(wanted)}件)")


if __name__ == "__main__":
    sys.exit(main())
