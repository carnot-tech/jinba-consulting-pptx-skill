"""snapshot.py の自己テスト。

pdftoppm が無い環境ではトレースバックではなく分かりやすい
エラーメッセージで止まること（#49）、ある環境では PDF と
まとめ画像が作れることを確かめる。ブラウザは CHROME_PATH の
スタブで代用し、Chromium 本体は要らない。

  python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import PIL  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "scripts" / "snapshot.py"

# --print-to-pdf= に最小の 1 ページ PDF を書くブラウザの代わり。
STUB = """#!/bin/sh
PATH=/usr/bin:/bin
for a in "$@"; do case "$a" in --print-to-pdf=*) pdf="${a#--print-to-pdf=}";; esac; done
printf '%%PDF-1.4\\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\\n2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\\n3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\\ntrailer << /Root 1 0 R >>\\n%%%%EOF\\n' > "$pdf"
"""

DECK = "<html><body><section><h1>Test</h1></section></body></html>"


@unittest.skipIf(os.name == "nt", "ブラウザの代わりに POSIX のシェルスタブを使うため")
class SnapshotMissingPdftoppm(unittest.TestCase):
    """pdftoppm が無いときはトレースバックを吐かずに止まる（#49）"""

    def _run(self, d, with_pdftoppm):
        bindir = Path(d) / "bin"
        bindir.mkdir()
        chrome = bindir / "chrome-stub"
        chrome.write_text(STUB, encoding="utf8")
        chrome.chmod(0o755)
        deck = Path(d) / "deck.html"
        deck.write_text(DECK, encoding="utf8")
        path = str(bindir)
        if with_pdftoppm:
            found = shutil.which("pdftoppm")
            if not found:
                self.skipTest("pdftoppm が要る")
            path = str(Path(found).parent) + os.pathsep + path
        env = {**os.environ, "PATH": path, "CHROME_PATH": str(chrome)}
        r = subprocess.run([sys.executable, str(SNAPSHOT), str(deck)],
                           capture_output=True, text=True, env=env)
        return r, deck

    def test_missing_pdftoppm_explains_instead_of_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            r, deck = self._run(d, with_pdftoppm=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("Traceback", r.stderr)
            self.assertNotIn("FileNotFoundError", r.stderr)
            self.assertIn("pdftoppm", r.stderr)
            self.assertIn("poppler", r.stderr)
            # PDF 自体は先に作られている（画像化だけが止まる）
            self.assertTrue(deck.with_suffix(".pdf").exists())

    @unittest.skipUnless(shutil.which("pdftoppm"), "pdftoppm が要る")
    @unittest.skipUnless(HAS_PIL, "Pillow が要る")
    def test_with_pdftoppm_makes_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            r, deck = self._run(d, with_pdftoppm=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(deck.with_suffix(".pdf").exists())
            self.assertEqual(len(list(deck.parent.glob("deck_sheet-*.png"))), 1)
