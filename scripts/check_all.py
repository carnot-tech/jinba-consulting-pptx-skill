#!/usr/bin/env python3
"""check_all.py — check_deck.py と check_layout.mjs を1回で回し、指摘をページごとにまとめて表示する。

使い方:
  python3 scripts/check_all.py mydeck.html                    # 同じフォルダか作業フォルダに sources.md があれば照合も行う
  python3 scripts/check_all.py mydeck.html --sources sources.md

出力は「全体の指摘」→「ページごとの指摘（FAIL を先に）」→ タイトル一覧。指摘の § は rules.py --sec で引ける。
終了コードは FAIL があれば 1。
"""
import os
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    deck = args[0]
    sources = None
    if "--sources" in args:
        sources = args[args.index("--sources") + 1]
    else:
        for cand in (Path(deck).resolve().parent / "sources.md", Path.cwd() / "sources.md"):
            if cand.exists():
                sources = str(cand)
                break
    cd_cmd = [sys.executable, str(HERE / "check_deck.py"), deck] + (["--sources", sources] if sources else [])
    cd = subprocess.run(cd_cmd, capture_output=True, text=True)
    cl = subprocess.run(["node", str(HERE / "check_layout.mjs"), deck], capture_output=True, text=True)
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
    if cl.returncode not in (0, 1) and not cl.stdout.strip():
        print("check_layout.mjs を実行できない（playwright が無い）: " + (cl.stderr.strip()[:300] or "原因不明"))
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
    print(f"\n{nf} FAIL / {nw} WARN" + ("（出典の照合: " + sources + "）" if sources else "（出典の照合なし: sources.md が見つからない）"))
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    main()
