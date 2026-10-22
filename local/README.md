# local/ — 自分の組織用の規約・テンプレを置く場所（git 管理外）

このフォルダの中身は `local/README.md` 以外 `.gitignore` されている。`git pull` で本体を更新しても、ここに置いたものは上書きされない。

| ファイル | 役割 | 読まれ方 |
|---|---|---|
| `slide-rules.local.md` | 自組織の規約（本体 `references/slide-rules.md` への追加・上書き） | スキルは本体の規約を読んだ後にこれを読む。両方に当たる規則はこちらが優先 |
| `forbid.txt` | 外に出してはいけない語（顧客名・案件コードなど。1 行 1 語、`re:` で正規表現） | `python3 scripts/check_deck.py deck.html --forbid local/forbid.txt` |
| `old-colors.txt` | 自組織で使わなくなったレガシー色（1 行 1 色、行頭に HEX 6 桁。後ろに説明を書いてよい。読めない行は WARN） | `check_deck.py` が指定なしで読み、見つけたら FAIL。他社の書式で組むときは `--brand none` で外す |
| `templates/` | 自組織のパーツ集・スキン・差し込み先の資料（`.pptx` / `.potx`）と `skin.json` | 本体の `templates/` の代わりに、または加えて使う |
| `examples/` | 自組織で作った参考デッキ | 似た資料を作るときの手本 |

## 書き方の目安

- `slide-rules.local.md` は本体と同じ書式（節番号は `L1`, `L2`, … のように本体とぶつからない接頭辞を付ける）。「なぜ」を 1 行添えると、次に読む人（と AI）が規則を外さない
- 本体の規約と矛盾する規則は、矛盾する本体の節番号を書く（例「§7.3 の代わりに、当社ではブレットは『・』」）
- **汎用化できる規則はここに溜めず、本体への PR にする**（出し方は `CONTRIBUTING.md`）。顧客名・案件固有の値を含む規則だけをここに残す
- デッキで Jinba に触れたくないときは、`slide-rules.local.md` に「Jinba に触れない」と1行書く（`references/jinba-context.md` §3）
