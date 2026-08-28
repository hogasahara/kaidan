# kaidan — ネットロア怪談 蒐集庫

洒落怖(「死ぬ程洒落にならない怖い話を集めてみない?」)に代表される、
掲示板発の短編怪談・ネットロアを蒐集するリポジトリ。

まとめサイトは分散していて、多くは十分にメンテナンスされないまま消えていく
(実際、老舗の syarecowa.moo.jp もすでに移転している)。
ここでは **本文そのもの** と **来歴(初出・取得元・取得日時)** をセットで保存し、
取得元が消えても話が残るようにする。

## 構成

```
catalog.yaml   蒐集カタログ。集めたい話と取得元をここに登録する
stories/       正規化した本文(YAML frontmatter 付き Markdown)
raw/           取得時の生データ(APIレスポンスJSON / 生HTML)。再現性と検証用
INDEX.md       蔵書目録(自動生成)
tools/         蒐集ツール
.github/       GitHub Actions(Pages への自動デプロイ)
```

各 `stories/*.md` の frontmatter には、タイトル・別名・タグ・初出情報・
取得元URL・取得日時・本文の文字数と SHA-256 が入る。

## 使い方

依存は Python 3.11+ と PyYAML のみ。

```sh
# catalog.yaml の未取得エントリをすべて取得し、INDEX.md を更新
python3 tools/collect.py

# 特定の話だけ / 再取得
python3 tools/collect.py --only hasshaku-sama --force

# 索引だけ作り直す
python3 tools/build_index.py

# 閲覧サイト(docs/)だけ作り直す
python3 tools/build_site.py
```

## スマホで読む(GitHub Pages)

`tools/build_site.py` が `docs/` に静的な閲覧サイトを生成する
(明朝体・ダークモード対応・前後の話へのナビ付き。JS不使用)。

公開は GitHub Actions(`.github/workflows/pages.yml`)が行う。
push のたびに Actions 上でサイトを生成して `actions/deploy-pages` でデプロイするので、
`docs/` はコミットしない(ローカル確認用に生成されるだけ)。

初回のみ、リポジトリの **Settings → Pages → Source** が
**GitHub Actions** になっていることを確認する
(ワークフローが自動で有効化を試みるが、失敗した場合はここを一度切り替える)。

公開先: `https://<ユーザー名>.github.io/kaidan/`

## 話を追加する

`catalog.yaml` の `stories:` にエントリを1つ足して `collect.py` を実行する。

取得元は2種類:

- **`type: wordpress`** — WordPress 製まとめサイト(dangi.link 等)。
  REST API (`/wp-json/wp/v2`) から本文をきれいに取得できる。
  `post_id` を指定するのが確実。省略すると slug → タイトル完全一致検索で特定を試みる。
- **`type: url`** — それ以外の任意のページ。生HTMLを `raw/` に保存し、
  本文抽出はヒューリスティック(`extraction: heuristic` が付くので手で整形推奨)。
  Shift_JIS / EUC-JP の古いサイトも文字コードを自動判定する。

取得元がまだ見つかっていない話は `status: wanted` で登録しておくと、
INDEX.md の「未収集」欄に載る。

## 主な取得元

- [dangi.link(洒落怖"超"まとめ)](https://dangi.link/) — 旧 syarecowa.moo.jp の移転先。
  元祖洒落怖スレ Part1〜 のまとめ。2chのレス番号・投稿日付きの原文が残っている。

## 取り扱いについて

収録しているのは匿名掲示板に投稿された文章であり、著作権は各投稿者にある。
このリポジトリは散逸しつつある話を保存するための個人的なアーカイブとして運用し、

- 本文は改変せず、レス番号・投稿日などの来歴ごと保存する
- 取得元サイトを必ず記録し、クレジットする
- 取得は間隔を空けて行い、取得元に負荷をかけない(`tools/collect.py` は1.5秒間隔)

権利者からの申し出があれば該当する話は削除する。
