#!/usr/bin/env python3
"""check_all.py — check_deck.py と check_layout.mjs を1回で回し、指摘をページごとにまとめて表示する。

使い方:
  python3 scripts/check_all.py mydeck.html                    # デッキと同じフォルダに sources.md があれば照合も行う
  python3 scripts/check_all.py mydeck.html --sources sources.md

出力は「全体の指摘」→「ページごとの指摘（FAIL を先に）」→ タイトル一覧。指摘の § は rules.py --sec で引ける。
終了コードは FAIL があれば 1。どちらかの検査が途中で落ちた（node が無い・playwright が無い・Traceback など）ときは
エラー出力を見せて 2 で終わる（指摘0件として通さない）。
"""
import os
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 各検査が最後まで走ったときにだけ出す締めの行。これが無い／終了コードが合わない＝途中で落ちた
DONE = {
    "check_deck.py": (re.compile(r"^\d+ FAIL / \d+ WARN$", re.M), (0, 1)),
    "check_layout.mjs": (re.compile(r"^(\d+ layout FAIL|layout OK)", re.M), (0, 1)),
}


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd[0]} が見つからない（PATH を確認）: {e}")


def finished(name, p):
    pat, codes = DONE[name]
    return p.returncode in codes and bool(pat.search(p.stdout or ""))


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    deck = args[0]
    sources = None
    if "--sources" in args:
        k = args.index("--sources")
        if k + 1 >= len(args) or args[k + 1].startswith("--"):
            sys.exit("--sources のあとに出典の控えのファイル名を書く（例: --sources sources.md）")
        sources = args[k + 1]
    else:
        # デッキと同じフォルダの控えだけを使う（作業フォルダの sources.md は別のデッキの控えのことがある）
        cand = Path(deck).resolve().parent / "sources.md"
        if cand.exists():
            sources = str(cand)
    cd_cmd = [sys.executable, str(HERE / "check_deck.py"), deck] + (["--sources", sources] if sources else [])
    cd = run(cd_cmd)
    cl = run(["node", str(HERE / "check_layout.mjs"), deck, "--all"])  # 表示の上限を外し、21件目以降のページも一覧に出す
    broken = [(name, p) for name, p in (("check_deck.py", cd), ("check_layout.mjs", cl)) if not finished(name, p)]
    for name, p in broken:
        print(f"{name} が最後まで動いていない（終了コード {p.returncode}）。この結果は使えない:", file=sys.stderr)
        print("  " + ((p.stderr or "").strip()[-800:] or "（エラー出力なし）").replace("\n", "\n  "), file=sys.stderr)
    if broken:
        sys.exit(2)
    lines = [l for l in (cd.stdout + "\n" + cl.stdout).splitlines() if l.startswith(("FAIL", "WARN"))]
    titles = cd.stdout.split("=== タイトル一覧", 1)[1].split("\n\n", 1)[0] if "=== タイトル一覧" in cd.stdout else ""
    pages, glob = OrderedDict(), []
    for l in lines:
        kind, msg = l[:4], l[5:].strip()
        m = re.match(r"^p(\d+)[:：]\s*(.*)$", msg)
        if m:
            pages.setdefault(int(m.group(1)), []).append((kind, m.group(2)))
        else:
            glob.append((kind, msg))
    nf = sum(1 for l in lines if l.startswith("FAIL"))
    nw = len(lines) - nf
    if glob:
        print("== デッキ全体")
        for k, m in sorted(glob, key=lambda x: x[0] != "FAIL"):
            print(f"  {k}  {m}")
    for n in sorted(pages):
        print(f"== p{n}")
        for k, m in sorted(pages[n], key=lambda x: x[0] != "FAIL"):
            print(f"  {k}  {m}")
    if titles:
        print("\n== タイトル一覧" + titles)
    print(f"\n{nf} FAIL / {nw} WARN" + ("（出典の照合: " + sources + "）" if sources else "（出典の照合なし: デッキと同じフォルダに sources.md が無い。別の場所なら --sources で指定）"))
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    main()
