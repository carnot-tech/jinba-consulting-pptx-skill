#!/usr/bin/env python3
"""rules.py — 規約の正典 references/slide-rules.md から、いまの工程に要る節だけを取り出して表示する。

規約は1つのファイル（正本）のまま。全文を最初に読み込む代わりに、工程ごとにこのスクリプトで引く。
--phase の既定は要点版（references/rules-digest.md の該当工程。数千字）。節全体が要るときだけ --full を付ける。

使い方:
  python3 scripts/rules.py --phase plan        # 構成を決める（§0・§2・§3・§4 のデッキ構造まわり）
  python3 scripts/rules.py --phase build       # ページを組む（§1・§4 の配置と余白）
  python3 scripts/rules.py --phase chart       # グラフ・図のページ（§5）
  python3 scripts/rules.py --phase table       # 表・行リストのページ（§4 表と軸・§6）
  python3 scripts/rules.py --phase process     # 流れ・工程・ツリーのページ（§4 プロセス・図の型）
  python3 scripts/rules.py --phase text        # 文章を仕上げる（§7）
  python3 scripts/rules.py --phase check       # 検査と直し（§8）
  python3 scripts/rules.py --phase pptx        # PPTX にする・既存の PPTX に差し込む（§8.6・§8.7）
  python3 scripts/rules.py --phase pitch       # 登壇用のピッチ（§9）
  python3 scripts/rules.py --sec 4.12 5.26     # 検査の指摘に出た項だけを引く
  python3 scripts/rules.py --phases            # 工程と節の対応表
"""
import argparse
import re
import sys
from pathlib import Path

RULES = Path(__file__).resolve().parent.parent / "references" / "slide-rules.md"
DIGEST = Path(__file__).resolve().parent.parent / "references" / "rules-digest.md"

# 工程 → 読む範囲。"§N" は節全体、"§4:見出しの一部" は §4 の小見出し単位、"head" は冒頭（用語・資料の種類の表）
PHASES = {
    "plan": ["head", "§0", "§2", "§3", "§4:1枚に載せるもの", "§4:デッキ全体の構造", "§4:締め・相談", "§4:課題整理・事例"],
    "build": ["§1", "§4:(冒頭)", "§4:左右2カラム", "§4:余白・塗り"],
    "chart": ["§5"],
    "table": ["§4:表と軸", "§6"],
    "process": ["§4:プロセス・図の型"],
    "text": ["§7"],
    "check": ["§8"],
    "pptx": ["§8.6", "§8.7"],
    "pitch": ["§9"],
}


def load():
    lines = RULES.read_text(encoding="utf8").split("\n")
    head, secs, cur = [], {}, None
    for ln in lines:
        m = re.match(r"^## (\d+(?:\.\d+)?)\.?\s", ln)
        if m:
            cur = m.group(1)
            secs[cur] = []
        if cur is None:
            head.append(ln)
        else:
            secs[cur].append(ln)
    return head, secs


def subsections(sec_lines):
    """節の中を ### 小見出しで分ける。最初の ### より前は「(冒頭)」"""
    out, name = {"(冒頭)": []}, "(冒頭)"
    for ln in sec_lines:
        if ln.startswith("### "):
            name = ln[4:].strip()
            out[name] = []
        out[name].append(ln)
    return out


def items(sec_lines):
    """節の中の番号つき項目（行頭の「N. 」）を、続きの行（字下げ・空行まで）ごと切り出す"""
    res, cur = {}, None
    for ln in sec_lines:
        m = re.match(r"^(\d+)\. ", ln)
        if m:
            cur = m.group(1)
            res[cur] = [ln]
        elif cur and (ln.startswith(" ") or ln.startswith("\t")):
            res[cur].append(ln)
        elif cur and ln.strip() == "":
            cur = None
    return res


def pick(spec, head, secs):
    if spec == "head":
        return "\n".join(head)
    m = re.match(r"^§(\d+(?:\.\d+)?)(?::(.+))?$", spec)
    num, sub = m.group(1), m.group(2)
    if num not in secs:
        return ""
    if not sub:
        return "\n".join(secs[num])
    subs = subsections(secs[num])
    hit = [k for k in subs if (sub == k or sub in k)]
    title = secs[num][0]
    return "\n".join([title] + sum((subs[k] for k in hit), []))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", action="append", choices=sorted(PHASES))
    ap.add_argument("--sec", nargs="+", help="例: 4.12 5.26 7.3（§N.M の項だけ）／ 6（節全体）")
    ap.add_argument("--phases", action="store_true")
    ap.add_argument("--full", action="store_true", help="--phase で要点版でなく節全体を表示する")
    a = ap.parse_args()
    head, secs = load()
    if a.phases or not (a.phase or a.sec):
        for k, v in PHASES.items():
            print(f"{k:8} {' '.join(v)}")
        return
    out = []
    digest = {}
    if DIGEST.exists():
        name = None
        for ln in DIGEST.read_text(encoding="utf8").split("\n"):
            m = re.match(r"^## (\w+)\s*$", ln)
            if m:
                name = m.group(1)
                digest[name] = []
            elif name:
                digest[name].append(ln)
    for ph in a.phase or []:
        if not a.full and ph in digest:
            out.append(f"<!-- rules.py --phase {ph}（要点版。詳しくは --sec N.M / --phase {ph} --full） -->\n" + "\n".join(digest[ph]).strip())
            continue
        out.append(f"<!-- rules.py --phase {ph} --full -->")
        out += [pick(s, head, secs) for s in PHASES[ph]]
    for s in a.sec or []:
        s = s.lstrip("§")
        if s in secs:
            out.append("\n".join(secs[s]))
            continue
        m = re.match(r"^(\d+)\.(\d+)$", s)
        if not m or m.group(1) not in secs:
            print(f"見つからない: §{s}", file=sys.stderr)
            continue
        it = items(secs[m.group(1)]).get(m.group(2))
        if not it:
            print(f"見つからない: §{s}", file=sys.stderr)
            continue
        out.append(f"§{s}\n" + "\n".join(it))
    print("\n\n".join(x for x in out if x.strip()))


if __name__ == "__main__":
    main()
