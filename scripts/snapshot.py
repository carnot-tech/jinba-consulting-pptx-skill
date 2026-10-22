#!/usr/bin/env python3
"""snapshot.py — HTML デッキを PDF にし、目視用に4ページずつ1枚にまとめた画像を作る。

使い方:
  python3 scripts/snapshot.py mydeck.html            # mydeck.pdf と mydeck_sheet-1.png, -2.png, ... を出力
  python3 scripts/snapshot.py mydeck.html --per 2    # 1枚に2ページ（細部を見たいとき）

全ページを見る精度は保ったまま、画像を読む回数を減らすための道具。崩れが疑わしいページは
--page 5 で1ページだけ大きく出して確かめる。
依存: Chromium headless shell（`npm run setup` で入る。CHROME_PATH で Chrome 本体にも切り替えられる。探し方は find_browser.py）、
pdftoppm（poppler）、Pillow。
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_browser import find_browser  # noqa: E402


def chrome():
    b = find_browser()
    if not b:
        sys.exit("ブラウザが見つからない。`npm run setup`（headless shell を入れる）か、CHROME_PATH で指定する")
    return b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--per", type=int, default=4, choices=(1, 2, 4, 6))
    ap.add_argument("--page", type=int, help="このページだけを大きく出す")
    ap.add_argument("--dpi", type=int, default=90)
    a = ap.parse_args()
    deck = Path(a.deck).resolve()
    pdf = deck.with_suffix(".pdf")
    # 前回の実行で残ったまとめ画像を消す（ページ数が減ったときに古い sheet が紛れ込まないように）
    for old in deck.parent.glob(f"{deck.stem}_sheet-*.png"):
        old.unlink()
    subprocess.run([chrome(), "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", str(deck)],
                   capture_output=True, check=True)
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("Pillow が必要: pip3 install pillow")
    with tempfile.TemporaryDirectory() as td:
        rng = ["-f", str(a.page), "-l", str(a.page)] if a.page else []
        dpi = a.dpi * 2 if a.page else a.dpi
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", *rng, str(pdf), f"{td}/p"], check=True)
        pages = sorted(Path(td).glob("p-*.png"))
        ims = [Image.open(p).convert("RGB") for p in pages]
        if not ims:
            sys.exit(f"{pdf} から画像を作れなかった（--page {a.page} がページ数を超えている）" if a.page
                     else f"{pdf} にページが無い（HTML にスライドがあるか確かめる）")
        if a.page:
            out = deck.with_name(f"{deck.stem}_page-{a.page}.png")
            ims[0].save(out)
            print(out)
            return
        cols = 1 if a.per == 1 else 2
        rows = a.per // cols
        w, h = ims[0].size
        outs = []
        for k in range(0, len(ims), a.per):
            chunk = ims[k:k + a.per]
            sheet = Image.new("RGB", (w * cols, h * rows), "white")
            d = ImageDraw.Draw(sheet)
            for i, im in enumerate(chunk):
                x, y = (i % cols) * w, (i // cols) * h
                sheet.paste(im, (x, y))
                d.rectangle([x, y, x + w - 1, y + h - 1], outline="#999999")
                d.text((x + 6, y + 4), f"P{k + i + 1}", fill="#d00000")
            out = deck.with_name(f"{deck.stem}_sheet-{k // a.per + 1}.png")
            sheet.save(out)
            outs.append(out)
    print(f"{pdf}（{len(ims)}ページ）")
    for o in outs:
        print(o)


if __name__ == "__main__":
    main()
