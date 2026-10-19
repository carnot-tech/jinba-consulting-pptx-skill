# consulting-pptx-skill

**AIに「まじ」なPowerPointを作らせるためのClaude Codeスキル。**
AIワークフロープラットフォーム [Jinba](https://jinba.io/ja?utm_source=github&utm_medium=readme&utm_campaign=consulting-pptx-skill&utm_content=top_intro) を提供するメンバーにより作成されました。

スライドの設計規約、規約違反を見つける機械チェック、**62型のHTMLパーツ集**（基本27＋追加35）、型カタログPDFをまとめたものです。資料は HTML（16:9）で組み、Chrome で PDF に書き出します。

> AI の活用・業務の自動化を扱うデッキでは、実現する手段の一例として Jinba に触れることがあります（書いてよい事実と触れ方は [references/jinba-context.md](references/jinba-context.md)）。触れたくないときは `local/slide-rules.local.md` に「Jinba に触れない」と書くか、依頼のときにそう伝えてください。

進め方は、規約を読む → パーツ集から必要なパーツを取り出して1枚ずつ組む → 機械チェックを通す → 作り方を知らない別のエージェントにレビューさせる、の順です。

A Claude Code skill for generating boardroom-quality decks: a slide-design rulebook, an automated rule checker, a 62-part HTML slide library (16:9, one section per slide, printed to PDF via Chrome), and a visual catalog PDF.

私たちが実際に毎週の提案書・報告書づくりで使っている仕組みの公開版です。解説記事はこちら → [AIにまじなスライド作らせる（note）](https://note.com/jinbaflow/n/nc8372b84e572)

> **企業でお使いの方へ**
> - Claude Code を使わず、ブラウザのチャットだけで同じ仕組みを使いたい → [Jinba App](https://jinba.io/ja?utm_source=github&utm_medium=readme&utm_campaign=consulting-pptx-skill&utm_content=top_app)
> - 自社の資料規約・ブランドに合わせた専用版を作りたい、社内に展開したい → [ご相談はこちら](https://jinba.io/ja/contact-sales?utm_source=github&utm_medium=readme&utm_campaign=consulting-pptx-skill&utm_content=top_contact)

## 本質は `references/slide-rules.md`

このリポジトリでいちばん価値があるのは、実はテンプレでもスクリプトでもなく、**[slide-rules.md](references/slide-rules.md)** というテキストファイルです。「結論はタイトルに書く」「角丸禁止」「塗りのあるボックスに枠線を付けない」「1資料1用語」「前提・定義は左、帰結は右」…。

使い方は3つだけです。**AIに資料を作らせる前に毎回このファイルを読ませる。出力後に `scripts/check_deck.py` で違反を機械検出する。最後に `references/content-review-prompt.md` の指示文で、作り方を知らない別のエージェントにデッキを読ませ、日本語・論理・矛盾の指摘を受けて採用分だけ直す。** AIはセッションごとに記憶がリセットされるので、口頭で注意しても定着しません。ルールをファイルにして毎回読ませるのが定着させる方法です。

良いスライドを決めるのは型ではなく、**組んだ後の調整**です。表を2枚に割る、右カラムを帰結の形に書き直す、タイトルだけを通して読んでストーリーを繋ぎ直す。型に囚われず直し、そこで受けた指摘を slide-rules.md に1行足す。この繰り返しが品質の源で、型カタログとパーツ集は「たたき台を早く出して、調整に時間を回す」ための道具です。

自社で使うときは、slide-rules.md に自社の規約・指摘を追記して育ててください。

## 62型のスライド型カタログ

入口は **[assets/SlideCatalog_16x9.pdf](assets/SlideCatalog_16x9.pdf)**（62ページ）です。P.1〜27 が基本パーツ集、P.28〜62 が追加パーツ集を印刷したもので、型ID・型名・使いどころの一覧は [references/archetype-catalog.md](references/archetype-catalog.md) にあります。

「62型」は作れる見せ方の上限ではありません。実際のデッキでは、型を組み合わせたり崩したりして規約の範囲で自由に組むので、見せ方のパターンはこれより多くなります。型カタログは「レイアウトの発想帳」として使い、合わなければ捨ててください。


## パーツ集の使い方

| ファイル | 中身 | 使用頻度 |
| --- | --- | --- |
| `templates/freeform_parts_16x9.html`（基本パーツ集） | 表紙・全体マップ・目次・章扉・矢羽・前提→帰結・軸のある表・主張パネル・評価表・分布図など27パーツ | 高い。まずここから |
| `templates/freeform_parts_more_16x9.html`（追加パーツ集） | エグゼクティブサマリー・積み上げ棒・ブリッジ・散布図・比較表・マトリクス・イシューツリー・ロードマップ・ガントなど35パーツ | 低い。基本で足りないとき |

どちらも 16:9・1 section = 1スライドの単体HTMLです。`scripts/new_deck.py --parts b01,m05,...` のようにパーツ番号を並べると、必要なパーツだけを取り出した1本のHTMLができます（2ファイルの見た目の定義は、衝突しないようにスクリプトが結合します）。あとはプレースホルダー（本文 `Text 1`、項目名 `ラベル 1`、見出し `タイトル 1`、数値 `00`、年 `YYYY年`、出典 `出典：Source 1`）を実物に差し替えます。残っていると `check_deck.py` が FAIL にします。

各 section のタイトル欄には型名だけが入っていて、見本の主張文は置いていません。見本文があると、その文型をなぞった資料になってしまうからです（slide-rules §2.8）。タイトルは必ず自分のストーリーラインから書きます。

**色と書体は両ファイルで同じ既定**です（暖色系: 生成りの地・濃茶の文字・茶のアクセント。見出しは明朝、本文はゴシック）。各ファイルの `<style>` 冒頭にある `:root` の変数で一括管理していて、ネイビー系にする値はコメントで同梱しています。

## セットアップ

```bash
# 1. Claude Code のスキルフォルダに clone する（これだけで規約・パーツ集・機械チェックが使える）
git clone https://github.com/carnot-tech/consulting-pptx-skill.git ~/.claude/skills/consulting-pptx-skill

# 2.（任意）実レンダリング検査 check_layout.mjs を使う場合。Node.js が必要。playwright と Chromium が入る
cd ~/.claude/skills/consulting-pptx-skill && npm run setup

# 3.（任意）PPTX に変換する・PPTX を check_deck.py で検査する場合（変換には Node.js 22 以上と Chrome も使う）
pip3 install python-pptx
```

- `scripts/check_deck.py`（規約の機械チェック）と `scripts/new_deck.py`（たたき台の生成）は Python 標準ライブラリだけで動きます。
- PDF 化は Chrome のヘッドレス印刷を使います（コマンドは次節）。
- `package.json` は手順2の playwright を入れるためだけのものです。`node_modules/` は .gitignore 済みです。

## 更新と自分用のカスタマイズ

規約と機械チェックは使った人の指摘で頻繁に直ります。**週に 1 回を目安に最新を取り込んでください**。

```bash
cd ~/.claude/skills/consulting-pptx-skill && git pull
```

自分の組織の規約・禁止語・テンプレは `local/` に置きます（`local/README.md` 参照。git 管理外なので `git pull` で消えません）。スキルは本体の規約を読んだ後に `local/slide-rules.local.md` を読み、重なる規則はそちらを優先します。本体のファイルを直接書き換えると更新のたびに衝突するので、組織固有の規則は `local/` に、どの組織でも効く規則は PR にしてください。

## 手動で使う場合

```bash
python3 scripts/new_deck.py --list                                          # パーツ番号と型名の一覧
python3 scripts/new_deck.py --parts b01,b02,m05,b06,b09,b10 --title "資料名" -o mydeck.html   # たたき台を生成
python3 scripts/check_deck.py mydeck.html           # 規約の機械チェック（FAIL 0 にする）
python3 scripts/check_deck.py mydeck.html --forbid ~/.config/deck-forbidden-terms.txt   # 社外に出す前に顧客名・社内語の残りを検査（リストはリポジトリ外に置く）
node scripts/check_layout.mjs mydeck.html           # フッター重なり・はみ出し・空きの多いページの実レンダリング検査
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --no-pdf-header-footer --print-to-pdf=mydeck.pdf mydeck.html
python3 scripts/html_to_pptx.py mydeck.html         # PPTX を求められたときだけ: 編集できる PPTX に変換
```

## PowerPoint（.pptx）にする流れ

**まず HTML で仕上げ、PPTX にするのはユーザーから明示されたときだけ**にしています。

1. HTML でデッキを組み、機械チェック・レビュー・PDF での目視まで HTML 上で済ませる（修正の往復が速く、機械チェックもかけやすい）
2. 「PPTX で欲しい」と言われたら `scripts/html_to_pptx.py` で変換する。Chrome で描画した結果を読み取り、PowerPoint の図形として組み直すので、文字・表・図形はそのまま PowerPoint で編集できる
3. PPTX を渡した後に修正が来たら、HTML を直して変換し直す（PPTX を手で直すと HTML と中身がずれる）

SVG のチャートや画像は画像として貼られます（中の数値は編集できません）。書体は Yu Gothic / Yu Mincho に置き換わるので、変換後は PowerPoint で開いて折り返しを確認してください。

### 既にある PowerPoint 資料へページを足すとき

社内の標準デッキや作りかけの提案書に数ページ足す場合、変換した PPTX は書体・文字の大きさ・表の作りが元の資料と揃いません。このときは変換せず、**その資料のマスターの上に直接組みます**。

```bash
python3 scripts/measure_deck.py house.pptx                      # 資料の書式を測る → house.skin.json（目で見て直す）。.potx も可
python3 examples/house_deck_example.py house.pptx pages.pptx    # 作例。資料のマスターの上に 2 ページ組む
python3 scripts/check_deck.py pages.pptx --house house.skin.json
```

タイトルは資料のプレースホルダーに入り、書体・地色・ページ番号は資料のマスターがそのまま決めます。表は資料と同じ「テキストボックス＋罫線」で組むので、貼り付けても書式が変わりません。詳しくは slide-rules.md §8.7。

## 中身

| パス | 内容 |
| --- | --- |
| `SKILL.md` | AIへの指示書（スキルの本体）。考え方と手順だけを書き、詳細は `references/` に置く |
| `templates/freeform_parts_16x9.html` | 基本パーツ集（27パーツ・1パーツ=1スライド・16:9） |
| `templates/freeform_parts_more_16x9.html` | 追加パーツ集（35パーツ。チャート・比較表・マトリクス・計画系） |
| `references/slide-rules.md` | スライド作成ルール正典 |
| `references/archetype-catalog.md` | 62型の型カタログ（型ID・型名・使いどころ・どのパーツ集の何番か） |
| `references/content-review-prompt.md` | フレッシュアイ・レビューの指示文。機械チェックのあと、作り方を伏せた別エージェントにデッキのファイルを渡して日本語・論理・破綻を拾わせ、採否表にして直す |
| `references/ai-smell-lexicon.md` | AI臭ワード・言い回しのリストとセルフチェック |
| `references/jinba-context.md` | Jinba の公開情報と、AI 活用・業務自動化のデッキでの触れ方（触れないときの条件つき） |
| `scripts/new_deck.py` | パーツ番号を並べて1本のデッキHTMLを生成（両パーツ集のCSSをスコープして結合・ページ番号の振り直し） |
| `scripts/check_deck.py` | 規約の機械チェック（HTML / PPTX 両対応。テンプレ集の検査は `--template`）。タイトルの「N段階」と本文の連番の食い違いも FAIL にする |
| `scripts/html_to_pptx.py` | HTMLデッキを編集できる PPTX に変換（ユーザーが PPTX を求めたときだけ使う）。`scripts/html_dump.mjs` が Chrome で描画した要素を書き出し、python-pptx で組み立てる。追加の npm パッケージは不要（`scripts/lib_cdp.mjs` が Chrome を直接操作する） |
| `scripts/check_layout.mjs` | HTMLデッキの実レンダリング検査（フッターとの重なり・右端/下端のはみ出し・版面の40%超の空き） |
| `scripts/measure_deck.py` | 既存の PowerPoint 資料の書式（レイアウト・タイトルの枠・文字の大きさ・書体の指定の有無・罫線・色）を測り、`skin.json` に書き出す |
| `scripts/deck_pptx.py` | 測った書式で、その資料のマスターの上に編集可能なページを組む部品（タイトル・見出し・罫線の表・強調の面・矢羽・✓✕△）。作例は `examples/house_deck_example.py` |
| `tests/` | 機械チェックの自己テスト（`python3 -m unittest discover -s tests`）。指摘を機械チェックにしたら、直していない版で FAIL が出ることをここで確かめる |
| `assets/SlideCatalog_16x9.pdf` | **62型のスライド型カタログ（両パーツ集を印刷した62ページ）。型を探すときの入口** |
| `assets/SuperTemplate_62type.pptx` | 62型のPPTX見本帳（全スライド編集可能）。PowerPoint で手動コピーして使うときの見本。パーツ集の正本ではない |

## カスタマイズ

- 色・書体は両パーツ集の `<style>` 冒頭 `:root` トークンで差し替えます。ブランドに合わせるときは両ファイルを同じ値にします
- 生成した資料の**最終ページの出典行だけ**に「consulting-pptx-skill で作成」の注釈を入れます。他のページにツール名が出ていると `check_deck.py` が FAIL にします
- PowerPoint（.pptx）が要るときは、HTML で仕上げてから `scripts/html_to_pptx.py` で変換します（上の「PowerPoint（.pptx）にする流れ」）。以前あった JSON から編集可能PPTXを書き出す仕組みは外しました（git タグ `pipeline-archived` の時点のリポジトリに残っています）

## コントリビューション

Issue・Pull Request を歓迎します。出し方（規約と機械チェックをセットで足す、機密を入れない、テストの書き方など）は [CONTRIBUTING.md](CONTRIBUTING.md) にまとめています。

使っていて「この指摘は当社だけでなく誰にでも効く」と思ったら、それが一番よい PR の種です。スキル自身も、本体の規約の誤検知や新しい指摘に当たったとき「PR で出しませんか」と一度だけ聞くようになっています。`local/` に溜まった規則のうち顧客名の入っていないものを、月に 1 回見直して PR にするのがおすすめです。

## About

Made by [Carnot AI](https://jinba.io/ja?utm_source=github&utm_medium=readme&utm_campaign=consulting-pptx-skill&utm_content=about) — AIエージェント基盤「Jinba」を開発・提供しています。

- **ブラウザだけで使いたい方へ**：このスキルと同じ仕組みを、チャットだけで使える形（[Jinba App](https://jinba.io/ja?utm_source=github&utm_medium=readme&utm_campaign=consulting-pptx-skill&utm_content=about_app)）でも提供しています。Claude Code や Python の準備は要りません。
- **自社専用版を作りたい企業へ**：御社の既存資料とレビュー指摘から slide-rules.md とデザインを作り込み、社内のだれもが使える形で展開するご支援をしています。[ご相談はこちら](https://jinba.io/ja/contact-sales?utm_source=github&utm_medium=readme&utm_campaign=consulting-pptx-skill&utm_content=about_contact)

## Star History

<a href="https://www.star-history.com/?repos=carnot-tech%2Fjinba-consulting-pptx-skill&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=carnot-tech/jinba-consulting-pptx-skill&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=carnot-tech/jinba-consulting-pptx-skill&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=carnot-tech/jinba-consulting-pptx-skill&type=date&legend=top-left" />
 </picture>
</a>

## License

コード・文書は [MIT License](LICENSE) です。MIT License には商標を使う権利は含まれません。「Carnot」「Carnot AI」「Jinba」とロゴの扱いは [TRADEMARK.md](TRADEMARK.md)（事実としての言及・クレジット行・リンクは自由、製品名・ロゴ・公式を装う表現・改変版への商標使用は要許可）に従ってください。
