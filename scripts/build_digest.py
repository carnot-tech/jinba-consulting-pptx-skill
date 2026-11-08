#!/usr/bin/env python3
"""build_digest.py — 規約（slide-rules.md と、そこから分けた pptx.md・pitch.md）から要点版 references/rules-digest.md を作る。

要点版の文は手で書かない。工程ごとに載せる項の番号（ITEMS）だけをここで決め、各項の太字の1文（無ければ最初の1文）を規約から取る。
番号が節だけ（"6"・"8"）なら、その節の太字で始まる箇条・表の行・チェック項目を並べる。pptx・pitch は要点版を作らず、rules.py が節の全文を出す。
規約を直したら、このスクリプトを回して rules-digest.md を作り直す（tests が古いままの要点版を FAIL にする）。

  python3 scripts/build_digest.py           # references/rules-digest.md を書き直す
  python3 scripts/build_digest.py --check   # 書き直しが要るなら終了コード 1
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402

OUT = rules.DIGEST

# 工程ごとに載せる項（並びは表示の順）
ITEMS = {
    "plan": "0 2.1 2.2 2.3 2.4 2.6 2.8 2.9 2.10 2.11 2.12 2.19 2.23 2.25 2.26 3 4.1 4.13 4.29 4.45 4.96 4.100 4.71 4.103 4.106 4.107 4.89 5.13 7.16",
    "build": "1 4.4 4.51 4.49 4.12 4.13 4.19 4.8 4.21 4.27 4.47 4.50 4.54 4.57 4.87 4.91 4.95 4.37 5.3 5.5 5.13",
    "chart": "2.10 3 5.5 5.10 5.11 5.12 5.18 5.26",
    "table": "4.10 4.12 4.51 4.102 5.2 7.24 7.25 6",
    "process": "4.26 4.27 4.77 4.88 4.79 4.87 4.98 5.17",
    "text": "7.2 7.3 7.4 7.6 7.7 7.9 7.13 7.14 7.19 7.29 7.32 7.33 7.34 7.35",
    "check": "5.13 8",
}

INTRO = {
    "plan": "構成を決める（目的・ストーリーライン・ページの並び）。",
    "build": "ページを組む（キャンバス・配置・2カラム・余白と塗り）。",
    "chart": "グラフ・図のページ（ボックス・色・凡例・枠線・チャートの形）。",
    "table": "表・行リストのページ（表と軸・表の作法）。",
    "process": "流れ・工程・ツリーのページ。",
    "text": "文章を仕上げる（文・ラベル・用語・数字の書き方）。",
    "check": "出す前の確認（機械では測れない項目と、目視の基準）。機械チェックの指摘は、メッセージに出る § を `--sec` で引く。",
}


def lead(text):
    """項の頭の1文。太字があれば太字の中、無ければ最初の「。」まで"""
    t = re.sub(r"^(\d+\.|-|\|)\s*", "", text.strip())
    m = re.match(r"\*\*(.+?)\*\*", t)
    s = m.group(1) if m else re.split(r"(?<=。)", t)[0]
    s = s.strip().rstrip("。")
    return s.replace("**", "") if s.count("**") % 2 else s


def phase_lines(ph, head, secs):
    out = []
    for ref in ITEMS[ph].split():
        sec, _, k = ref.partition(".")
        if k:
            it = rules.items(secs[sec]).get(k)
            if not it:
                sys.exit(f"規約に無い項: §{ref}（build_digest.py の ITEMS を直す）")
            out.append(f"- §{ref} {lead(it[0])}")
            continue
        num, lines = sec, secs[sec]
        # 番号の無い節（§0・§3・§6・§8）: 太字で始まる箇条・表の行・チェック項目
        for ln in lines:
            if ln.startswith("- [ ]"):
                out.append("- " + ln[5:].strip())
            elif ln.startswith("- **"):
                out.append(f"- §{num} {lead(ln)}")
            elif ln.startswith("| ") and num != "8" and not re.match(r"^\|\s*(-+|項目?|観点|論点|資料の種類)\s*\|", ln):
                cells = [c.strip() for c in ln.strip("|").split("|")]
                if len(cells) >= 2 and cells[0] and not set(cells[1]) <= set("-: "):
                    out.append(f"- §{num} {cells[0]}: {lead(cells[1])}")
    return out


def build():
    head, secs = rules.load()
    parts = ["# 規約の要点（工程ごと）", "",
             "`scripts/rules.py --phase <工程>` が表示する要点版。**`scripts/build_digest.py` が規約から作るので手で直さない。** "
             "各行は正典の項の頭の1文で、条件・例外・理由は `rules.py --sec N.M` で引く。食い違えば正典が勝つ。"]
    for ph in ITEMS:
        parts += ["", f"## {ph}", "", INTRO.get(ph, ""), ""] + phase_lines(ph, head, secs)
    return "\n".join(parts).rstrip() + "\n"


def main():
    text = build()
    if "--check" in sys.argv:
        cur = OUT.read_text(encoding="utf8") if OUT.exists() else ""
        if cur != text:
            print("rules-digest.md が規約と合っていない。python3 scripts/build_digest.py で作り直す", file=sys.stderr)
            sys.exit(1)
        return
    OUT.write_text(text, encoding="utf8")
    print(f"書いた: {OUT}（{len(text.encode())} bytes）")


if __name__ == "__main__":
    main()
