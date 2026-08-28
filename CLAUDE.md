# CLAUDE.md — 引き継ぎ文書

このリポジトリは、洒落怖(「死ぬ程洒落にならない怖い話を集めてみない?」)に代表される
掲示板発のネットロア怪談を蒐集・保存する **個人アーカイブ** である。
オーナーは主に iOS から利用し、閲覧は GitHub Pages
(https://hogasahara.github.io/kaidan/)で行う。

## 依頼の性質と、変わらないゴール

オーナーの指示はフワッとしていることが多い。例:

- 「リゾートバイトみたいな別の作品あったと思うけどどんなだったか?探せるか?」
- 「部屋から双眼鏡で公園?を見てて怪異を見つける話ってあったと思うけど探せるか?」
- 「適当なランキングサイトの上位20くらいから未収録の作品を探してみよう」

記憶違い(場所・小道具・タイトル)が混ざっている前提で探すこと。
**探した後にやることは常に同じ**: 本文を取得して `stories/*.md` を作り、サイトに収録する。

## 定型ワークフロー

1. 話を特定する(下記「探し方」)
2. `catalog.yaml` の `stories:` にエントリを追加(`post_id` を必ずピン留めする)
3. `python3 tools/collect.py` を実行(依存は PyYAML のみ)
   - `stories/<slug>.md` と `raw/<slug>.json` が生成され、INDEX.md と docs/ も自動再生成される
4. 生成された md の冒頭を読んで **本当にその話か確認する**(レスヘッダ・書き出し・キーワード)
5. コミットして push。**main にマージされると GitHub Actions が Pages にデプロイする**
   (詳細は後述「ブランチとデプロイ」)

## 探し方

### 第一の道具: dangi.link の WordPress REST API

dangi.link は旧 syarecowa.moo.jp(元祖洒落怖まとめ)の公式移転先。
2ch のレス番号・投稿日・ID 付きの原文がそのまま残っている。API が公開されている:

```
# 検索(タイトルだけでなく本文もヒットする。フワッとした依頼に最適)
https://dangi.link/wp-json/wp/v2/posts?search=双眼鏡&per_page=30&_fields=id,slug,link,title

# slug 完全一致 / 記事ID直指定
https://dangi.link/wp-json/wp/v2/posts?slug=八尺様&_fields=...
https://dangi.link/wp-json/wp/v2/posts/20162?_fields=id,link,title,date,content,categories
```

- 「双眼鏡 公園」のような依頼は、**モチーフ語で search** して候補を絞り、
  各候補の本文冒頭を確認して同定する。あらすじを1〜2行付けて候補をオーナーに提示するとよい
- 記事カテゴリに「Part 121」「名作」「洒落怖殿堂」など初出スレと評価が入っている。
  collect.py が自動で frontmatter に記録する
- **同名・類似タイトルの亜種が大量にある**ので注意。例: 「猿夢」の原典は id 332 で、
  「猿夢を見た」「猿夢系」等は別物。「くねくね」原典は id 3566(「黄色いくねくね」等は亜種)。
  search はタイトル完全一致を優先し、投稿日が通説と合うか確認する

### ランキングサイト・他のまとめから探すとき

1. WebSearch や URL 取得でタイトルのリストを得る
2. `INDEX.md`(または `catalog.yaml`)と突き合わせて未収録タイトルを列挙
3. 各タイトルを dangi.link API で探す。見つかればいつも通り収録
4. dangi.link に無ければ、原文を載せている別サイトを探し、
   `type: url` ソース(生HTML保存+ヒューリスティック抽出)で取得。
   抽出結果は `extraction: heuristic` が付くので、md を開いて手で整形すること
5. どうしても原文が見つからない話は `status: wanted` で登録する(INDEX の未収集欄に載る)。
   既存の wanted: リゾートバイト、異世界エレベーター

### 収録の品質基準

- 本文は**改変しない**。レスヘッダ(番号・日付・ID)も来歴として残す
- タイトル・別名(表記ゆれ)・タグ・一言 note を catalog に書く。
  note に書く事実(初出年など)は本文のレスヘッダ等で裏が取れるものだけにする
- 投稿日は collect.py が本文冒頭から自動抽出する(`original_post_date`)

## リポジトリ構成

```
catalog.yaml     蒐集カタログ(唯一の手書きデータ。ここが起点)
stories/*.md     本文。YAML frontmatter に来歴・出典・SHA-256
raw/*.json       取得時の生APIレスポンス(検証用。消さない)
INDEX.md         蔵書目録(自動生成。手で編集しない)
tools/collect.py     取得・正規化(実行すると index と site も再生成)
tools/build_index.py INDEX.md 生成
tools/build_site.py  docs/ に閲覧サイト生成(明朝体・ダークモード対応・JS不使用)
.github/workflows/pages.yml  main への push で Pages にデプロイ
docs/            ビルド成果物。.gitignore 済みで**コミットしない**
```

## ブランチとデプロイ

- 開発は指定されたブランチで行い、公開は **main へのマージで** 行う。
  `github-pages` environment の保護ルールにより **main 以外からはデプロイできない**
  (開発ブランチから push しても deploy ジョブが即失敗する。これは正常)
- マージ済みブランチに積み増ししない。追加作業は
  `git fetch origin main && git checkout -B <ブランチ名> origin/main` で作り直してから
- オーナーが「マージ」と言ったら PR を作ってマージまで行ってよい(前例あり)

## この実行環境の落とし穴(実測済み)

- `web.archive.org` と `kowabana.jp` はプロキシに遮断されて到達できない。
  dangi.link は http/https とも到達可能
- 取得は必ず間隔を空ける(collect.py は 1.5 秒/リクエスト。手書きスクリプトでも守る)
- ヘッドレス Chromium(/opt/pw-browsers/chromium)は **ウィンドウ最小幅 ≈500px** のため、
  `--window-size=390,...` で撮ると本文が右にはみ出して見える。**実際のレイアウトは正常**。
  スクリーンショット確認は幅 600 以上で撮ること

## 取り扱い方針(README にも記載)

収録物は匿名掲示板投稿のアーカイブで、著作権は各投稿者にある。
無改変・来歴保存・出典クレジットを守り、権利者から申し出があれば該当作を削除する。
公開範囲に関わる変更(リポジトリの可視性など)はオーナーに確認する。
