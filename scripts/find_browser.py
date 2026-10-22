#!/usr/bin/env python3
"""find_browser.py — PDF 化・描画に使うブラウザの実行ファイルを探す（snapshot.py などから使う）。

探す順番:
  1. 環境変数 CHROME_PATH（Chrome 本体などに切り替えたいとき）
  2. Playwright の Chromium headless shell（`npx playwright install --only-shell chromium` で入る。軽く、出力は Chrome 本体と同じ）
  3. Chrome 本体・Chromium（入っていれば）

  python3 scripts/find_browser.py   # 見つかった実行ファイルの場所を表示する
"""
import glob
import os
import re
import shutil
import sys
from pathlib import Path


def _playwright_dirs():
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env and env != "0":
        yield Path(env)
    home = Path.home()
    yield home / "Library" / "Caches" / "ms-playwright"          # macOS
    yield home / ".cache" / "ms-playwright"                      # Linux
    if os.environ.get("LOCALAPPDATA"):
        yield Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"  # Windows


def headless_shell():
    """Playwright の headless shell のうち、いちばん新しい版の実行ファイル"""
    found = []
    for d in _playwright_dirs():
        for exe in ("chrome-headless-shell", "chrome-headless-shell.exe", "headless_shell"):
            found += glob.glob(str(d / "chromium_headless_shell-*" / "*" / exe))
    def ver(p):
        m = re.search(r"chromium_headless_shell-(\d+)", p)
        return int(m.group(1)) if m else 0
    found = [p for p in found if os.access(p, os.X_OK)]
    return max(found, key=ver) if found else None


CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def find_browser():
    env = os.environ.get("CHROME_PATH")
    if env:
        return env
    hs = headless_shell()
    if hs:
        return hs
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
        w = shutil.which(c)
        if w:
            return w
    return None


if __name__ == "__main__":
    b = find_browser()
    if not b:
        sys.exit("ブラウザが見つからない。`npm run setup`（headless shell を入れる）か、CHROME_PATH で指定する")
    print(b)
