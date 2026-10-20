"""機械チェックの自己テスト（標準ライブラリのみ）。

指摘を機械チェックに足したら、ここに「直していない版で FAIL が出る」「直した版で出ない」の
両方を1件ずつ足す。直していない版で発火しないチェックは、測れていないのと同じ。

  python3 -m unittest discover -s tests
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check_deck.py"
GOOD = (ROOT / "tests" / "fixtures" / "good_deck.html").read_text(encoding="utf8")


def run(html, *extra):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "deck.html"
        p.write_text(html, encoding="utf8")
        extra = [str(Path(d) / a[1:]) if a.startswith("@") else a for a in extra]
        for a in extra:
            if a.endswith(".txt"):
                Path(a).write_text("# 架空の禁止語\nサンプル商事\nre:PJ-\\d{3}\n", encoding="utf8")
        r = subprocess.run([sys.executable, str(CHECK), str(p), *extra], capture_output=True, text=True)
    return r.returncode, [l for l in r.stdout.splitlines() if l.startswith("FAIL")]


def warns(html):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "deck.html"
        p.write_text(html, encoding="utf8")
        r = subprocess.run([sys.executable, str(CHECK), str(p)], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.startswith("WARN")]


def inject(old, new):
    assert old in GOOD, old
    return GOOD.replace(old, new, 1)


class GoodDeck(unittest.TestCase):
    def test_good_deck_passes(self):
        code, fails = run(GOOD)
        self.assertEqual((code, fails), (0, []))

    def test_templates_pass_in_template_mode(self):
        for f in ("freeform_parts_16x9.html", "freeform_parts_more_16x9.html"):
            r = subprocess.run([sys.executable, str(CHECK), str(ROOT / "templates" / f), "--template"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f + r.stdout[-400:])


class Placeholders(unittest.TestCase):
    def test_body_placeholder_fires(self):
        code, fails = run(inject("承認待ちは平均3日", "Text 1"))
        self.assertEqual(code, 1)
        self.assertTrue(any("本文にテンプレのプレースホルダー" in f for f in fails), fails)

    def test_part_label_chip_fires(self):
        code, fails = run(inject('<div class="date">現状</div>', '<div class="date">パーツ06｜前提→帰結の2カラム</div>'))
        self.assertTrue(any("プレースホルダー" in f for f in fails), fails)

    def test_type_name_title_fires(self):
        code, fails = run(inject("<h1>1部門で2か月試行し、効果を確かめてから全社へ広げる</h1>", "<h1>軸のある表</h1>"))
        self.assertTrue(any("型名のまま" in f for f in fails), fails)


class OneSentencePerBlock(unittest.TestCase):
    def test_two_sentences_in_card_fires(self):
        code, fails = run(inject("• 例外だけ承認者に回す", "• 例外だけ承認者に回す。規程外の申請は差し戻す"))
        self.assertTrue(any("2文以上" in f for f in fails), fails)

    def test_period_inside_brackets_is_ignored(self):
        code, fails = run(inject("• 例外だけ承認者に回す", "• 例外（金額超過。科目不明）だけ承認者に回す"))
        self.assertFalse(any("2文以上" in f for f in fails), fails)

    def test_single_sentence_with_trailing_period_passes(self):
        code, fails = run(inject("• 例外だけ承認者に回す", "• 例外だけ承認者に回す。"))
        self.assertFalse(any("2文以上" in f for f in fails), fails)


def run_warns(html):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "deck.html"
        p.write_text(html, encoding="utf8")
        r = subprocess.run([sys.executable, str(CHECK), str(p)], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.startswith("WARN")]


class NumberConsistency(unittest.TestCase):
    """slide-rules §7.6 数値の平仄: 同じ指標がページ間で違う値なら WARN。"""

    def deck(self, p2, p5):
        return inject("承認待ちは平均3日", p2).replace("営業部", p5, 1)

    def test_same_label_different_value_fires(self):
        warns = run_warns(self.deck("承認者数は12人", "承認者数は15人"))
        self.assertTrue(any("数値の平仄疑い" in w and "承認者数" in w for w in warns), warns)

    def test_same_value_in_other_notation_passes(self):
        warns = run_warns(self.deck("承認者数は1.2万人", "承認者数 12,000人"))   # 桁の書き方が違っても値が同じなら可
        self.assertFalse(any("数値の平仄疑い" in w for w in warns), warns)

    def test_amount_with_scale_fires(self):
        warns = run_warns(self.deck("売上高は120億円", "売上高 118億円"))   # 金額・割合など単位を問わず比べる
        self.assertTrue(any("数値の平仄疑い" in w and "売上高" in w for w in warns), warns)

    def test_same_amount_in_other_scale_passes(self):
        warns = run_warns(self.deck("売上高は1.2億円", "売上高 120,000,000円"))
        self.assertFalse(any("数値の平仄疑い" in w for w in warns), warns)

    def test_float_rounding_does_not_fire(self):
        warns = run_warns(self.deck("売上高は1.1億円", "売上高 110,000,000円"))   # 1.1×1e8 の float 誤差を食い違いにしない
        self.assertFalse(any("数値の平仄疑い" in w for w in warns), warns)

    def test_different_year_passes(self):
        warns = run_warns(self.deck("2024年の承認者数は12人", "2026年の承認者数は15人"))   # 時点が違えば別の指標
        self.assertFalse(any("数値の平仄疑い" in w for w in warns), warns)


class ForbiddenTerms(unittest.TestCase):
    def test_term_in_body_fires_without_echoing_it(self):
        code, fails = run(inject("営業部", "サンプル商事の営業部"), "--forbid", "@terms.txt")
        self.assertTrue(any("禁止語" in f for f in fails), fails)
        self.assertFalse(any("サンプル商事" in f for f in fails), fails)

    def test_term_in_html_comment_fires(self):
        code, fails = run(inject("</main>", "<!-- PJ-123 向けの下書き --></main>"), "--forbid", "@terms.txt")
        self.assertTrue(any("コメント/属性" in f for f in fails), fails)

    def test_no_list_no_check(self):
        code, fails = run(inject("営業部", "サンプル商事の営業部"))
        self.assertEqual(code, 0)


def run_out(html):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "deck.html"
        p.write_text(html, encoding="utf8")
        r = subprocess.run([sys.executable, str(CHECK), str(p)], capture_output=True, text=True)
    return r.stdout


class Charset(unittest.TestCase):
    def test_missing_charset_fires(self):
        html = re.sub(r"<meta[^>]*charset[^>]*>", "", GOOD, count=1)
        self.assertNotEqual(html, GOOD)
        code, fails = run(html)
        self.assertTrue(any("charset" in f for f in fails), fails)

    def test_good_deck_has_charset(self):
        code, fails = run(GOOD)
        self.assertFalse(any("charset" in f for f in fails), fails)


class TitleConnector(unittest.TestCase):
    T = "<h1>1部門で2か月試行し、効果を確かめてから全社へ広げる</h1>"

    def test_connector_start_warns(self):
        out = run_out(inject(self.T, "<h1>まずは1部門で2か月試行し、効果を確かめてから全社へ広げる</h1>"))
        self.assertIn("接続詞で始まる", out)

    def test_tsugini_as_verb_phrase_does_not_warn(self):
        out = run_out(inject(self.T, "<h1>次に進む条件は、1部門で2か月試行して効果を確かめることである</h1>"))
        self.assertNotIn("接続詞で始まる", out)

    def test_word_starting_with_mata_does_not_warn(self):
        out = run_out(inject(self.T, "<h1>またがる2部門で試行し、効果を確かめてから全社へ広げる</h1>"))
        self.assertNotIn("接続詞で始まる", out)


class ProductionMeta(unittest.TestCase):
    """SKILL.md「本スキル使用の注釈」: ツール名は最終ページ（裏表紙）の出典行だけ。他ページは FAIL。"""
    BODY = "承認待ちは平均3日"

    def test_tool_name_on_content_page_fails(self):
        code, fails = run(inject(self.BODY, self.BODY + "<p>本資料は consulting-pptx-skill で作成</p>"))
        self.assertTrue(any("制作メタ" in f for f in fails), fails)

    def test_tool_name_on_back_cover_passes(self):
        code, fails = run(GOOD)   # fixture の裏表紙には出典行に注釈が入っている
        self.assertFalse(any("制作メタ" in f for f in fails), fails)

    def test_credit_sentence_on_content_page_only_warns(self):
        html = inject(self.BODY, self.BODY + "<p>本資料は生成AIツールで作成</p>")
        self.assertFalse(any("制作メタ" in f for f in run(html)[1]))
        self.assertTrue(any("で作成" in w for w in warns(html)))

    def test_disclaimer_with_de_sakusei_does_not_fail(self):
        code, fails = run(inject(self.BODY, self.BODY + "<p>本資料は2026年9月時点の公開情報で作成</p>"))   # 免責文は制作メタではない
        self.assertFalse(any("制作メタ" in f for f in fails), fails)

    def test_github_url_as_source_only_warns(self):
        code, fails = run(inject(self.BODY, self.BODY + "<p>出典: github.com/example/repo</p>"))
        self.assertFalse(any("制作メタ" in f for f in fails), fails)


def _has_playwright():
    import os
    return (ROOT / "node_modules" / "playwright").exists() or bool(os.environ.get("PLAYWRIGHT_MODULE_DIR"))


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class EmptyArea(unittest.TestCase):
    def layout(self, html):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "deck.html"
            p.write_text(html, encoding="utf8")
            r = subprocess.run(["node", str(ROOT / "scripts" / "check_layout.mjs"), str(p)],
                               capture_output=True, text=True, cwd=ROOT)
        return r.returncode, r.stdout

    def test_good_deck_has_no_empty_page(self):
        code, out = self.layout(GOOD)
        self.assertEqual(code, 0, out)

    def test_half_empty_page_fires(self):
        html = re.sub(r'\s*<tr><td class="ax">2026年7月</td>.*?変わらず</td></tr>', "", GOOD, flags=re.S)
        html = html.replace("\n          <li>1人あたりの申請件数が2倍になる</li>\n          <li>承認の遅れが立替者の不満になる</li>", "")
        self.assertNotEqual(html, GOOD)
        code, out = self.layout(html)
        self.assertEqual(code, 1, out)
        self.assertIn("p3: 版面の", out)


if __name__ == "__main__":
    unittest.main()


class DashAndHeads(unittest.TestCase):
    """§6 非該当「—」は連結ではない／§4.49 基本パーツ集のカラム見出し .colh も対象"""
    def test_label_dash_join_warns(self):
        w = warns(inject("承認待ちは平均3日", "承認待ち — 平均3日"))
        self.assertTrue(any("ダッシュ" in l for l in w), w)

    def test_standalone_na_dash_is_ignored(self):
        w = warns(inject("承認待ちは平均3日", "承認待ちは平均3日</p><p>—</p><p>—（関与しない）"))
        self.assertFalse(any("ダッシュ" in l for l in w), w)

    def test_colh_conjunction_head_warns(self):
        w = warns(inject("承認待ちは平均3日", '承認待ちは平均3日<div class="colh">だから、全社展開を急ぐ</div>'))
        self.assertTrue(any("接続詞" in l for l in w), w)


class HarveyAndSummary(unittest.TestCase):
    """¾ハーベイボールの中心点抜け（FAIL）／エグゼクティブサマリーの羅列（WARN）"""
    BAD_Q3 = "<style>.hb.q3 i{clip-path:polygon(50% 0,100% 0,100% 100%,0 100%,0 50%)}</style>"
    GOOD_Q3 = "<style>.hb.q3 i{clip-path:polygon(50% 50%,50% 0,100% 0,100% 100%,0 100%,0 50%)}</style>"

    def test_q3_without_center_fails(self):
        code, fails = run(GOOD.replace("</head>", self.BAD_Q3 + "</head>", 1))
        self.assertTrue(any("ハーベイボール" in l for l in fails), fails)

    def test_q3_with_center_passes(self):
        code, fails = run(GOOD.replace("</head>", self.GOOD_Q3 + "</head>", 1))
        self.assertFalse(any("ハーベイボール" in l for l in fails), fails)

    FLAT = ('<section class="s"><h1>エグゼクティブサマリー</h1><ul><li>需要はある</li><li>利益は出る</li></ul>'
            '<div class="foot"><span>9</span></div></section>')
    NESTED = ('<section class="s"><h1>エグゼクティブサマリー</h1><ul><li>需要はある<ul><li>調査で確認</li>'
              '<li>価格も通る</li></ul></li></ul><div class="foot"><span>9</span></div></section>')

    def test_flat_summary_warns(self):
        w = warns(GOOD.replace("</body>", self.FLAT + "</body>", 1))
        self.assertTrue(any("エグゼクティブサマリー" in l for l in w), w)

    def test_nested_summary_passes(self):
        w = warns(GOOD.replace("</body>", self.NESTED + "</body>", 1))
        self.assertFalse(any("入れ子のブレット" in l for l in w), w)


def _has_pptx():
    try:
        import pptx  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_pptx(), "python-pptx が入っていると実行される")
class PptxLayout(unittest.TestCase):
    """check_deck_layout.py: 図形に隠れた文字・中身の無い箱（線は箱と取り違えない）"""

    def _deck(self, build):
        from pptx import Presentation
        from pptx.util import Inches
        from pptx.enum.shapes import MSO_SHAPE
        prs = Presentation()
        prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
        s = prs.slides.add_slide(prs.slide_layouts[6])
        build(s, Inches, MSO_SHAPE)
        d = tempfile.mkdtemp()
        p = Path(d) / "deck.pptx"
        prs.save(p)
        sys.path.insert(0, str(ROOT / "scripts"))
        import check_deck_layout
        return [k for _, k, _ in check_deck_layout.check(str(p))]

    @staticmethod
    def _solid(shape):
        shape.fill.solid()
        return shape

    def test_text_under_opaque_box_fires(self):
        def build(s, In, M):
            tb = s.shapes.add_textbox(In(1), In(1), In(4), In(1))
            tb.text_frame.text = "隠れている文字"
            self._solid(s.shapes.add_shape(M.RECTANGLE, In(0.9), In(0.9), In(4.2), In(1.2)))
        self.assertIn("hidden", self._deck(build))

    def test_visible_text_and_thin_line_do_not_fire(self):
        def build(s, In, M):
            tb = s.shapes.add_textbox(In(1), In(1), In(4), In(1))
            tb.text_frame.text = "見えている文字"
            self._solid(s.shapes.add_shape(M.RECTANGLE, In(1), In(3), In(1.3), In(0.01)))
        kinds = self._deck(build)
        self.assertNotIn("hidden", kinds)
        self.assertNotIn("empty", kinds)

    def test_empty_filled_box_fires(self):
        def build(s, In, M):
            self._solid(s.shapes.add_shape(M.RECTANGLE, In(1), In(1), In(2), In(1)))
        self.assertIn("empty", self._deck(build))


class MemberFeedbackChecks(unittest.TestCase):
    """メンバーの作業記録から足した検査：文末の「。」／ブレット記号の混在／表のページの連続／操作用の部品"""

    def page(self, n, body, title="検査の見本として置いたページのタイトル"):
        return f'<section class="s"><h1>{title}</h1>{body}<div class="foot"><span>{n}</span></div></section>'

    def test_trailing_period_warns_and_clean_passes(self):
        bad = self.page(9, "<ul><li>添付漏れを提出前に警告する。</li></ul>")
        ok = self.page(9, "<ul><li>添付漏れを提出前に警告する</li></ul>")
        self.assertTrue(any("§7.25" in l for l in warns(GOOD.replace("</body>", bad + "</body>", 1))))
        self.assertFalse(any("§7.25" in l for l in warns(GOOD.replace("</body>", ok + "</body>", 1))))

    def test_mixed_bullet_marks_warn(self):
        bad = self.page(9, "<div>• 添付漏れを警告する</div><div>● 勘定科目を提示する</div>")
        ok = self.page(9, "<div>• 添付漏れを警告する</div><div>• 勘定科目を提示する</div>")
        self.assertTrue(any("§7.3" in l for l in warns(GOOD.replace("</body>", bad + "</body>", 1))))
        self.assertFalse(any("§7.3" in l for l in warns(GOOD.replace("</body>", ok + "</body>", 1))))

    def test_three_table_pages_in_a_row_warn(self):
        t = "<table><tr><th>観点</th><th>内容</th></tr><tr><td>費用</td><td>年額で比べる</td></tr></table>"
        three = "".join(self.page(9 + k, t) for k in range(3))
        two = "".join(self.page(9 + k, t) for k in range(2))
        self.assertTrue(any("§4.96" in l for l in warns(GOOD.replace("</body>", three + "</body>", 1))))
        self.assertFalse(any("§4.96" in l for l in warns(GOOD.replace("</body>", two + "</body>", 1))))

    def test_buttons_must_hide_in_print(self):
        bad = self.page(9, "<button>次へ</button>")
        hidden = bad + "<style>@media print{button{display:none}}</style>"
        self.assertTrue(any("§1" in l for l in warns(GOOD.replace("</body>", bad + "</body>", 1))))
        self.assertFalse(any("§1:" in l for l in warns(GOOD.replace("</body>", hidden + "</body>", 1))))


class WeeklyFeedback20261012(unittest.TestCase):
    """10/12 回収分：改行済みタイトルの字数 WARN／正本から差し込んだ定型ページ／構成変更後に残った P.n"""

    def page(self, n, body, title="検査の見本として置いたページのタイトル", cls="s"):
        return f'<section class="{cls}"><h1>{title}</h1>{body}<div class="foot"><span>{n}</span></div></section>'

    LONG = "提出時の確認と承認経路の見直しで、差し戻しと待ち時間を減らし、承認待ちを当日に縮める"

    def test_long_title_without_break_warns(self):
        w = warns(GOOD.replace("</body>", self.page(9, "<p>本文</p>", self.LONG) + "</body>", 1))
        self.assertTrue(any("p7: タイトル 全角換算" in l for l in w), w)

    def test_title_broken_with_br_does_not_warn(self):
        t = self.LONG.replace("減らし、", "減らし、<br>", 1)
        w = warns(GOOD.replace("</body>", self.page(9, "<p>本文</p>", t) + "</body>", 1))
        self.assertFalse(any("p7: タイトル 全角換算" in l for l in w), w)

    def test_std_page_skips_text_checks(self):
        body = "<p>当社は2020年に創業した。東京に本社を置く。</p>"
        code, fails = run(GOOD.replace("</body>", self.page(9, body) + "</body>", 1))
        self.assertTrue(any("2文以上" in f for f in fails), fails)
        code, fails = run(GOOD.replace("</body>", self.page(9, body, cls="s std") + "</body>", 1))
        self.assertFalse(any("2文以上" in f for f in fails), fails)

    def test_page_ref_beyond_deck_warns(self):
        bad = self.page(9, "<p>詳細は → P.12</p>")
        ok = self.page(9, "<p>詳細は → P.3</p>")
        self.assertTrue(any("P.12" in l for l in warns(GOOD.replace("</body>", bad + "</body>", 1))))
        self.assertFalse(any("ページ数" in l for l in warns(GOOD.replace("</body>", ok + "</body>", 1))))


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class LayoutFeedback20261012(unittest.TestCase):
    """check_layout の WARN：並べた要素の揃い（§4.51）／片側の空き（§4.54）／ハイライトの数（§4.57）"""

    def layout(self, body, cls="s"):
        page = (f'<section class="{cls}"><h1>検査の見本として置いたページのタイトル</h1>{body}'
                '<div class="foot"><span>9</span></div></section>')
        html = GOOD.replace("</body>", page + "</body>", 1)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "deck.html"
            p.write_text(html, encoding="utf8")
            r = subprocess.run(["node", str(ROOT / "scripts" / "check_layout.mjs"), str(p)],
                               capture_output=True, text=True, cwd=ROOT, encoding="utf8")
        return [l for l in r.stdout.splitlines() if l.startswith("p7") or "p7:" in l]

    COL = '<div class="cmp"><h3>{h}</h3><ul><li>{t}</li><li>{t}</li></ul></div>'

    def two_cols(self, cols):
        c = "".join(self.COL.format(h=h, t="申請の内容を確認して承認者に回す") for h in ("現状", "導入後"))
        return f'<div style="display:grid;grid-template-columns:{cols};gap:24px;height:380px">{c}</div>'

    def test_unequal_contrast_columns_warn(self):
        out = self.layout(self.two_cols("1fr 1.4fr"))
        self.assertTrue(any("§4.51" in l for l in out), out)

    def test_equal_contrast_columns_pass(self):
        out = self.layout(self.two_cols("1fr 1fr"))
        self.assertFalse(any("§4.51" in l for l in out), out)

    def test_right_side_gap_warns(self):
        body = '<div style="width:50%;height:380px"><ul><li>申請の内容を確認する</li></ul><div style="height:300px;border:1px solid #333"></div></div>'
        self.assertTrue(any("右側" in l for l in self.layout(body)))
        self.assertFalse(any("右側" in l for l in self.layout(self.two_cols("1fr 1fr"))))

    def test_two_highlighted_rows_warn(self):
        row = '<tr><td>費用</td><td>年額で比べる</td></tr>'
        hl = '<tr><td style="background:#eee">費用</td><td style="background:#eee">年額で比べる</td></tr>'
        t = lambda rows: f'<table style="height:380px"><tr><th>観点</th><th>内容</th></tr>{rows}</table>'
        self.assertTrue(any("§4.57" in l for l in self.layout(t(hl + row + hl))))
        self.assertFalse(any("§4.57" in l for l in self.layout(t(hl + row + row))))

    def test_std_page_skips_layout_checks(self):
        body = '<div style="width:50%;height:380px"><ul><li>会社概要</li></ul><div style="height:300px;border:1px solid #333"></div></div>'
        self.assertFalse(any("右側" in l for l in self.layout(body, cls="s std")))


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class TableStretchAndLegend(LayoutFeedback20261012):
    """check_layout：表を縦に引き伸ばさない（§4.12 FAIL）／凡例はグラフの見出しの上に右揃え（§5.18 WARN）"""

    ROWS = '<tr><th>部門</th><th>件数</th></tr><tr><td>営業部</td><td>月に約120件</td></tr><tr><td>管理部</td><td>月に約40件</td></tr>'
    CHART = '<svg viewBox="0 0 400 200" style="height:70mm"><rect x="20" y="40" width="80" height="160" fill="#5A3921"/><rect x="160" y="100" width="80" height="100" fill="#C5A681"/></svg>'
    LEGEND = '<div class="legend"><span><i style="display:inline-block;width:4mm;height:4mm;background:#5A3921"></i>本社</span><span><i style="display:inline-block;width:4mm;height:4mm;background:#C5A681"></i>拠点</span></div>'

    def test_stretched_table_fails(self):
        out = self.layout(f'<table style="height:420px">{self.ROWS}</table>')
        self.assertTrue(any("引き伸ばされている" in l for l in out), out)

    def test_natural_table_passes(self):
        out = self.layout(f'<table>{self.ROWS}</table>')
        self.assertFalse(any("引き伸ば" in l for l in out), out)

    def test_legend_below_chart_warns(self):
        out = self.layout(f'<div>{self.CHART}{self.LEGEND}</div>')
        self.assertTrue(any("凡例がグラフの下" in l for l in out), out)

    def test_legend_above_chart_passes(self):
        out = self.layout(f'<div>{self.LEGEND}{self.CHART}</div>')
        self.assertFalse(any("凡例がグラフの下" in l for l in out), out)

    def test_row_header_th_table_is_checked(self):
        rows = '<tr><th>部門</th><th>件数</th></tr><tr><th>営業部</th><td>月に約120件</td></tr><tr><th>管理部</th><td>月に約40件</td></tr>'
        out = self.layout(f'<table style="height:420px">{rows}</table>')
        self.assertTrue(any("引き伸ばされている" in l for l in out), out)

    def test_natural_table_with_list_cells_passes(self):
        rows = ('<tr><th>部門</th><th>課題</th></tr>'
                '<tr><td>営業部</td><td><ul><li>入力の二重化</li><li>集計の手作業</li></ul></td></tr>'
                '<tr><td>管理部</td><td><ul><li>承認の待ち</li><li>差し戻し</li></ul></td></tr>')
        out = self.layout(f'<table>{rows}</table>')
        self.assertFalse(any("引き伸ば" in l or "行ぶん高い" in l for l in out), out)

    def test_lg_size_class_is_not_a_legend(self):
        out = self.layout(f'<div>{self.CHART}<div class="text-lg">図の読み方の補足</div></div>')
        self.assertFalse(any("凡例がグラフの下" in l for l in out), out)

    def test_legend_under_single_tile_is_not_below_chart(self):
        tile = '<div style="background:#5A3921;color:#fff;width:60mm;height:30mm">月に約120件の問い合わせ</div>'
        out = self.layout(f'<div>{tile}{self.LEGEND}</div>')
        self.assertFalse(any("凡例がグラフの下" in l for l in out), out)

    def test_legend_directly_in_section_below_chart_warns(self):
        out = self.layout(f'{self.CHART}{self.LEGEND}')
        self.assertTrue(any("凡例がグラフの下" in l for l in out), out)

    # 親クラスのテストを二重に回さない
    test_unequal_contrast_columns_warn = test_equal_contrast_columns_pass = None
    test_right_side_gap_warns = test_two_highlighted_rows_warn = test_std_page_skips_layout_checks = None


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class ColumnRuleAlignment(LayoutFeedback20261012):
    """check_layout：左右2列の最初の横罫の高さを揃える（§4.21 WARN）"""

    AXH = '<div><div style="height:38px;border-bottom:1.8px solid #333;font-weight:700">工数の推移</div><div style="height:200px;background:#C5A681"></div></div>'
    TBL = ('<table style="border-collapse:collapse"><tr><td style="border-top:1.8px solid #333">営業部</td><td style="border-top:1.8px solid #333">月に約120件</td></tr>'
           '<tr><td>管理部</td><td>月に約40件</td></tr></table>')
    HDR = '<div style="height:38px;border-bottom:1.8px solid #333;font-weight:700">部門ごとの件数</div>'

    def cols(self, left, right):
        return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px"><div>{left}</div><div>{right}</div></div>'

    def test_headerless_table_next_to_axis_title_warns(self):
        out = self.layout(self.cols(self.AXH, self.TBL))
        self.assertTrue(any("最初の横罫" in l for l in out), out)

    def test_table_with_same_height_header_passes(self):
        out = self.layout(self.cols(self.AXH, self.HDR + self.TBL.replace("border-top:1.8px solid #333", "")))
        self.assertFalse(any("最初の横罫" in l for l in out), out)



class BotFeedback20261019(unittest.TestCase):
    """check_deck：文字化け（FAIL）・ページ番号の連番（FAIL）・1項目だけの箇条・本文のですます・締めのページ・keep-all・番号つき項目名（WARN）"""

    def test_garbled_text_fails(self):
        code, fails = run(inject("確認作業が1日1時間を超える", "確認作業が1日1�間を超える"))
        self.assertTrue(any("文字化け" in l for l in fails), fails)

    def test_page_number_gap_fails(self):
        code, fails = run(inject("<span>3</span>", "<span>5</span>"))
        self.assertTrue(any("連番でない" in l for l in fails), fails)
        self.assertFalse(any("連番でない" in l for l in run(GOOD)[1]))

    def test_single_item_list_warns(self):
        html = inject("<li>月末に承認が集中する</li>", "</ul><ul><li>月末に承認が集中する</li></ul><ul>")
        self.assertTrue(any("1つだけの箇条" in l for l in warns(html)))
        self.assertFalse(any("1つだけの箇条" in l for l in warns(GOOD)))

    def test_body_desu_masu_warns(self):
        html = inject("確認作業が1日1時間を超える", "確認作業が1日1時間を超えます")
        self.assertTrue(any("本文がですます調" in l for l in warns(html)))
        self.assertFalse(any("本文がですます調" in l for l in warns(GOOD)))

    def test_closing_slide_is_not_desu_masu_fail(self):
        last = GOOD.rfind('<section class="s cover">')
        html = GOOD[:last] + GOOD[last:].replace("<section class=\"s cover\">", "<section class=\"s cover\"><h1>ありがとうございました</h1>", 1)
        code, fails = run(html)
        self.assertFalse(any("ですます" in l for l in fails), fails)

    def test_keep_all_warns(self):
        html = inject("</style>", "h1{word-break:keep-all}</style>")
        self.assertTrue(any("keep-all" in l for l in warns(html)))

    def test_numbered_labels_mismatch_warns(self):
        html = inject("確認作業が1日1時間を超える", "①提出前の確認").replace("月末に承認が集中する", "①事前チェック", 1)
        html = html.replace("<span>3</span>", "<span>3</span><i>①事前チェック</i>", 1)
        self.assertTrue(any("番号つきの項目名" in l for l in warns(html)))

    def test_mixed_parts_header_label_passes(self):
        # 基本パーツ（.bar/.date）と追加パーツ（.kicker → new_deck で .hdr/.date）の混在は正規のデッキ
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "mixed.html"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "new_deck.py"),
                            "--parts", "b01,b02,b05,m05,b06,m10,b09,m20,b10", "-o", str(out)],
                           capture_output=True, check=True)
            r = subprocess.run([sys.executable, str(CHECK), str(out)], capture_output=True, text=True, encoding="utf8")
        self.assertFalse(any("右上のラベル" in l for l in r.stdout.splitlines()), r.stdout[-600:])
        self.assertFalse(any("右上のラベル" in l for l in warns(GOOD)))

    def test_missing_header_label_warns(self):
        html = inject('<div class="date">打ち手</div>', '<div class="date"></div>')
        self.assertTrue(any("右上のラベル" in l for l in warns(html)), warns(html))


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class LayoutBotFeedback20261019(LayoutFeedback20261012):
    """check_layout：箱からのはみ出し（FAIL）・箱の中の空き・下の空き30%・同じ作りで違う大きさ・文の途中の太字・混在要素の文字の重なり（WARN）"""

    def test_text_overflowing_box_fails(self):
        body = '<div style="width:120px;height:40px;overflow:hidden;background:#EFEEE8;white-space:nowrap">申請の内容を確認して承認者に回す処理を自動化する</div><div style="height:300px;border:1px solid #333">図</div>'
        self.assertTrue(any("箱の外に" in l for l in self.layout(body)))

    def test_text_inside_box_passes(self):
        body = '<div style="width:600px;background:#EFEEE8">申請の内容を確認して承認者に回す</div><div style="height:300px;border:1px solid #333">図</div>'
        self.assertFalse(any("箱の外に" in l for l in self.layout(body)))

    def test_empty_box_warns(self):
        body = '<div style="height:380px;background:#EFEEE8;padding:8px"><p>申請の内容を確認する</p></div>'
        self.assertTrue(any("箱の中が" in l for l in self.layout(body)))

    def test_equal_height_sibling_boxes_pass(self):
        full = "".join(f"<p>申請の内容を確認する手順その{i}</p>" for i in range(9))
        body = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;height:380px">'
                f'<div class="cd" style="background:#EFEEE8">{full}</div><div class="cd" style="background:#EFEEE8"><p>申請の内容を確認する</p></div></div>')
        self.assertFalse(any("箱の中が" in l for l in self.layout(body)))

    def test_bottom_space_over_30_warns(self):
        body = '<div style="height:370px;border:1px solid #333"><p>申請の内容を確認する</p></div>'
        out = self.layout(body)
        self.assertTrue(any("30%超" in l for l in out), out)

    def test_same_role_different_size_warns(self):
        body = ('<ul><li style="font-size:14px">申請の内容を確認する</li><li style="font-size:18px">承認者に回して結果を返す</li></ul>'
                '<div style="height:300px;border:1px solid #333">図</div>')
        self.assertTrue(any("違う大きさ" in l for l in self.layout(body)))

    def test_mid_sentence_bold_warns(self):
        li = "<li>申請の<b>内容</b>を確認し<b>承認者</b>に回して<b>結果</b>を返す</li>"
        body = f'<ul>{li}<li>月末に承認が集中する</li></ul><div style="height:300px;border:1px solid #333">図</div>'
        self.assertTrue(any("途中の太字" in l for l in self.layout(body)))

    def test_overlap_in_mixed_element_warns(self):
        body = ('<div style="position:relative;height:340px;border:1px solid #333"><p style="position:absolute;top:10px;left:10px">申請の<b>内容</b>を確認する</p>'
                '<p style="position:absolute;top:12px;left:14px">承認者に回して結果を返す</p></div>')
        self.assertTrue(any("文字が重なっている" in l for l in self.layout(body)))


@unittest.skipUnless(_has_pptx() and _has_playwright(), "python-pptx と playwright が要る")
class PptxVideoAndExternal(unittest.TestCase):
    """html_to_pptx：<video> を動画として埋め込む／--external で section.internal を除く"""

    def test_video_embedded_and_internal_skipped(self):
        import shutil
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg が要る")
        from pptx import Presentation
        with tempfile.TemporaryDirectory() as d:
            mp4 = Path(d) / "clip.mp4"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x180:d=1", "-pix_fmt", "yuv420p", str(mp4)], check=True)
            extra = ('<section class="s"><h1>画面の操作を動画で示す</h1><video src="clip.mp4" style="width:320px;height:180px"></video>'
                     '<div class="foot"><span>9</span></div></section>'
                     '<section class="s internal"><h1>社内用の確認事項を残しておく</h1><p>社内用</p></section>')
            p = Path(d) / "deck.html"
            p.write_text(GOOD.replace("</body>", extra + "</body>", 1), encoding="utf8")
            out = Path(d) / "deck.pptx"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "html_to_pptx.py"), str(p), str(out), "--external"],
                           capture_output=True, text=True, check=True)
            prs = Presentation(str(out))
            n_html = GOOD.count("<section")
            self.assertEqual(len(prs.slides), n_html + 1)
            xml = "".join(sl.part.blob.decode("utf8", "ignore") for sl in prs.slides)
            self.assertIn("p:videoFile", xml.replace("a:videoFile", "p:videoFile"))


class TypeIdLeftover(unittest.TestCase):
    """check_deck：パーツの英語の型ID（「05  chart_insight」）が残っていたら FAIL"""

    def test_type_id_fails(self):
        code, fails = run(inject("<span>3</span>", "<span>3</span><i>05  chart_insight</i>"))
        self.assertTrue(any("型ID" in l for l in fails), fails)

    def test_good_deck_has_no_type_id(self):
        self.assertFalse(any("型ID" in l for l in run(GOOD)[1]))

    def test_table_number_and_snake_case_is_not_type_id(self):
        # 表の「05」「user_id」のような並びは型IDではない
        code, fails = run(inject("<span>3</span>", "<span>3</span><table><tr><td>05</td><td>user_id</td></tr></table>"))
        self.assertFalse(any("型ID" in l for l in fails), fails)

    def test_single_word_type_id_fails(self):
        for tid in ("34  gantt", "15  matrix_2x2"):
            code, fails = run(inject("<span>3</span>", f"<span>3</span><i>{tid}</i>"))
            self.assertTrue(any("型ID" in l for l in fails), (tid, fails))


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class BarAxisAndColors(LayoutFeedback20261012):
    """check_layout：棒グラフの項目名が軸の線より上（§5.26）・下端のずれ・凡例なしの色分け（§5.5）"""

    def chart(self, labels_below=True, colors=("#322014",) * 4, legend=""):
        wrap = "position:relative;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%"
        lab = "position:absolute;top:calc(100% + 8px);left:0;right:0;text-align:center" if labels_below else "margin-top:8px;text-align:center"
        bars = "".join(f'<div style="{wrap}"><div>{v}</div><div style="width:70%;height:{v}%;background:{c}"></div><div style="{lab}">部門{i}</div></div>'
                       for i, (v, c) in enumerate(zip((30, 50, 70, 90), colors)))
        return (f'{legend}<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px;height:300px;'
                f'border-bottom:2px solid #333;margin-bottom:52px">{bars}</div>')

    def test_labels_above_axis_warn(self):
        out = self.layout(self.chart(labels_below=False))
        self.assertTrue(any("軸の線より上" in l for l in out), out)

    def test_labels_below_axis_pass(self):
        out = self.layout(self.chart())
        self.assertFalse(any("軸の線より上" in l or "下端が" in l for l in out), out)

    def test_colors_without_legend_warn(self):
        out = self.layout(self.chart(colors=("#322014", "#C5A681", "#5A3921", "#322014")))
        self.assertTrue(any("凡例が無い" in l for l in out), out)

    def test_colors_with_legend_pass(self):
        out = self.layout(self.chart(colors=("#322014", "#C5A681", "#5A3921", "#322014"), legend='<div class="legend">凡例</div>'))
        self.assertFalse(any("凡例が無い" in l for l in out), out)


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class RowSlackAndHeadingSize(LayoutFeedback20261012):
    """check_layout：表の行の間延び（§4.12）・見出しが下の文字より小さい（§6・§4.21）"""

    ROWS = "".join(f'<tr><td style="padding:{{p}};line-height:{{lh}}">部門{i}</td><td style="padding:{{p}};line-height:{{lh}}">月に約{i}0件を処理する</td></tr>' for i in range(1, 4))

    def test_loose_rows_warn(self):
        out = self.layout("<table>" + self.ROWS.format(p="5mm 2mm", lh="1.7") + "</table>")
        self.assertTrue(any("間延び" in l for l in out), out)

    def test_tight_rows_pass(self):
        out = self.layout("<table>" + self.ROWS.format(p="2.5mm 2mm", lh="1.4") + "</table>")
        self.assertFalse(any("間延び" in l for l in out), out)

    def test_small_heading_warns(self):
        body = '<h3 style="font-size:12px">部門ごとの件数</h3><div><p style="font-size:18px">営業部は月に約120件を処理する</p></div>'
        self.assertTrue(any("その下の文字より小さい" in l for l in self.layout(body)))

    def test_big_heading_passes(self):
        body = '<h3 style="font-size:20px">部門ごとの件数</h3><div><p style="font-size:15px">営業部は月に約120件を処理する</p><p style="font-size:30px">72%</p></div>'
        self.assertFalse(any("その下の文字より小さい" in l for l in self.layout(body)))


class StructureF(unittest.TestCase):
    """要点版と正本のずれ・出典の照合・check_all の動作"""

    def test_digest_refs_exist_in_canon(self):
        digest = (ROOT / "references" / "rules-digest.md").read_text(encoding="utf8")
        refs = sorted(set(re.findall(r"§(\d+\.\d+)", digest)))
        self.assertTrue(refs)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rules.py"), "--sec", *refs], capture_output=True, text=True)
        self.assertNotIn("見つからない", r.stderr, r.stderr)

    def test_digest_has_all_phases(self):
        digest = (ROOT / "references" / "rules-digest.md").read_text(encoding="utf8")
        for ph in ("plan", "build", "chart", "table", "process", "text", "check"):
            self.assertIn(f"## {ph}", digest)

    def test_sources_missing_number_warns(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "sources.md"
            src.write_text("# 出典\n- 月に約120件 社内集計\n", encoding="utf8")
            deck = Path(d) / "deck.html"
            deck.write_text(GOOD, encoding="utf8")
            r = subprocess.run([sys.executable, str(CHECK), str(deck), "--sources", str(src)], capture_output=True, text=True)
        self.assertIn("出典の控えに無い数字", r.stdout)

    def test_sources_file_required(self):
        with tempfile.TemporaryDirectory() as d:
            deck = Path(d) / "deck.html"
            deck.write_text(GOOD, encoding="utf8")
            r = subprocess.run([sys.executable, str(CHECK), str(deck), "--sources", str(Path(d) / "nope.md")], capture_output=True, text=True)
        self.assertIn("出典の控え", r.stdout)
        self.assertEqual(r.returncode, 1)

    @unittest.skipUnless(_has_playwright(), "playwright が要る")
    def test_check_all_groups_by_page(self):
        with tempfile.TemporaryDirectory() as d:
            deck = Path(d) / "deck.html"
            deck.write_text(GOOD, encoding="utf8")
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_all.py"), str(deck)], capture_output=True, text=True, cwd=d)
        self.assertIn("FAIL /", r.stdout)
        self.assertIn("== タイトル一覧", r.stdout)


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class LayoutFeedback20261020(LayoutFeedback20261012):
    """check_layout：文字と罫線の重なり・同じ作りの箱の左端のずれ・行のリストの間延び・左右の行のずれ（WARN）"""

    def test_text_over_rule_warns(self):
        body = ('<div style="height:40px;border-bottom:2px solid #333">指標名、単位</div>'
                '<div style="margin-top:-18px;font-size:20px;font-weight:700">48.5</div><div style="height:300px;border:1px solid #333">図</div>')
        self.assertTrue(any("罫線に重なっている" in l for l in self.layout(body)))

    def test_text_clear_of_rule_passes(self):
        body = '<div style="height:40px;border-bottom:2px solid #333">指標名、単位</div><div style="margin-top:12px;font-size:20px">48.5</div><div style="height:300px;border:1px solid #333">図</div>'
        self.assertFalse(any("罫線に重なっている" in l for l in self.layout(body)))

    def test_box_left_edge_misaligned_warns(self):
        box = '<div class="lf" style="border:1px solid #999;padding:6px;margin-left:{m}px;width:300px">申請の内容を確かめる</div>'
        body = "".join(box.format(m=m) for m in (100, 130, 112)) + '<div style="height:250px;border:1px solid #333">図</div>'
        self.assertTrue(any("左端が" in l for l in self.layout(body)))

    def test_box_left_edge_aligned_passes(self):
        box = '<div class="lf" style="border:1px solid #999;padding:6px;margin-left:100px;width:300px">申請の内容を確かめる</div>'
        body = box * 3 + '<div style="height:250px;border:1px solid #333">図</div>'
        self.assertFalse(any("左端が" in l for l in self.layout(body)))

    ROW = '<div style="border-bottom:1px solid #ccc;padding:{p};display:flex;align-items:center">部門{i}は月に約{i}0件を処理する</div>'

    def test_stretched_row_list_warns(self):
        rows = "".join(self.ROW.format(p="9mm 0", i=i) for i in range(1, 5))
        self.assertTrue(any("行のリストの上下が間延び" in l for l in self.layout(f"<div>{rows}</div>")))

    def test_tight_row_list_passes(self):
        rows = "".join(self.ROW.format(p="3mm 0", i=i) for i in range(1, 5))
        self.assertFalse(any("行のリストの上下が間延び" in l for l in self.layout(f"<div>{rows}</div>")))

    def test_rows_misaligned_across_columns_warns(self):
        left = "".join(self.ROW.format(p="3mm 0", i=i) for i in range(1, 4))
        right = "".join(self.ROW.format(p="3mm 0" if i != 1 else "8mm 0", i=i) for i in range(1, 4))
        body = f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px"><div>{left}</div><div>{right}</div></div>'
        self.assertTrue(any("行の位置が" in l for l in self.layout(body)))


class MetaTitle(unittest.TestCase):
    """check_deck：作業の説明のタイトル（「〜を3つに分ける」）を WARN"""

    def test_meta_title_warns(self):
        html = inject("差し戻しの削減と承認の自動化で、承認待ちを当日に縮める", "承認が遅れる理由を3つに分ける")
        self.assertTrue(any("作業の説明" in l for l in warns(html)))

    def test_claim_title_passes(self):
        self.assertFalse(any("作業の説明" in l for l in warns(GOOD)))


class CoverPlaceholder(unittest.TestCase):
    """check_deck：表紙・裏表紙に見本の文言（当社・会社名・連絡先・「表紙」のラベル）が残っていたら FAIL"""

    def test_back_cover_placeholder_fails(self):
        last = GOOD.rfind('<section class="s cover">')
        html = GOOD[:last] + GOOD[last:].replace('<section class="s cover">', '<section class="s cover"><div>当社</div>', 1)
        self.assertTrue(any("見本の文言" in l for l in run(html)[1]))

    def test_cover_type_label_fails(self):
        html = GOOD.replace('<section class="s cover">', '<section class="s cover"><div>表紙</div>', 1)
        self.assertTrue(any("見本の文言が残っている「表紙」" in l for l in run(html)[1]))

    def test_good_deck_cover_passes(self):
        self.assertFalse(any("見本の文言" in l for l in run(GOOD)[1]))


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class UnevenWrap(LayoutFeedback20261012):
    """check_layout：並べた見出しのうち一部だけが折れている（WARN）"""

    def cols(self, titles):
        cell = '<div><h3 style="font-size:20px;font-weight:700;margin:0">{t}</h3><p>説明の文</p></div>'
        return ('<div style="display:grid;grid-template-columns:repeat(4,160px);gap:20px">'
                + "".join(cell.format(t=t) for t in titles) + '</div><div style="height:260px;border:1px solid #333">図</div>')

    def test_one_heading_wrapped_warns(self):
        out = self.layout(self.cols(["土台づくり", "試行", "本番化", "成果検証と全社への拡大判断"]))
        self.assertTrue(any("折れている" in l for l in out), out)

    def test_all_one_line_passes(self):
        out = self.layout(self.cols(["土台づくり", "試行", "本番化", "拡大判断"]))
        self.assertFalse(any("折れている" in l for l in out), out)


CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class HeadlessShell(unittest.TestCase):
    """PDF 化は Chromium headless shell で行い、Chrome 本体と同じ出力になること"""

    def test_chrome_path_overrides(self):
        import os
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "find_browser.py")], capture_output=True, text=True,
                           env={**os.environ, "CHROME_PATH": "/opt/custom/chrome"})
        self.assertEqual(r.stdout.strip(), "/opt/custom/chrome")

    @unittest.skipUnless(Path(CHROME_APP).exists(), "Chrome 本体が要る（比較の基準）")
    def test_headless_shell_pdf_matches_chrome(self):
        import shutil
        sys.path.insert(0, str(ROOT / "scripts"))
        from find_browser import headless_shell
        hs = headless_shell()
        if not hs or not shutil.which("pdftoppm"):
            self.skipTest("headless shell（npm run setup）と pdftoppm が要る")
        from PIL import Image, ImageChops
        with tempfile.TemporaryDirectory() as d:
            deck = Path(d) / "deck.html"
            deck.write_text(GOOD, encoding="utf8")
            outs = {}
            for name, exe in (("hs", hs), ("chrome", CHROME_APP)):
                pdf = Path(d) / f"{name}.pdf"
                subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", str(deck)],
                               capture_output=True, check=True, timeout=120)
                subprocess.run(["pdftoppm", "-r", "40", "-png", str(pdf), str(Path(d) / name)], check=True)
                outs[name] = sorted(Path(d).glob(f"{name}-*.png"))
            self.assertEqual(len(outs["hs"]), len(outs["chrome"]))
            for a, b in zip(outs["hs"], outs["chrome"]):
                ia, ib = Image.open(a).convert("L"), Image.open(b).convert("L")
                self.assertEqual(ia.size, ib.size)
                diff = ImageChops.difference(ia, ib)
                changed = sum(1 for v in diff.getdata() if v > 40) / (ia.size[0] * ia.size[1])
                self.assertLess(changed, 0.005, f"{a.name} が Chrome 本体と {changed:.2%} 違う")


class CountTitles(unittest.TestCase):
    """check_deck：数で束ねたタイトル（「3つの」「3本の」「3点」）が3枚以上なら FAIL（§4.103）"""

    def test_three_count_titles_fail(self):
        html = GOOD
        for old, new in (("差し戻しの削減と承認の自動化で、承認待ちを当日に縮める", "承認の遅れは3つの壁で起きている"),):
            html = html.replace(old, new, 1)
        html = html.replace("</body>", "".join(f'<section class="s"><h1>{t}</h1><div class="foot"><span>9</span></div></section>'
                                                for t in ("来期は3本柱で進める", "本日は3点を承認いただきたい")) + "</body>", 1)
        self.assertTrue(any("数で束ねたタイトル" in l for l in run(html)[1]))

    def test_good_deck_passes(self):
        self.assertFalse(any("数で束ねたタイトル" in l for l in run(GOOD)[1] + warns(GOOD)))


class PartVariant(unittest.TestCase):
    """new_deck.py：b09:axb で軸ボックスの表になる"""

    def test_axb_variant(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "new_deck.py"), "--show", "b09:axb"], capture_output=True, text=True)
        self.assertIn('<table class="axb"', r.stdout)

    def test_unknown_variant_fails(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "new_deck.py"), "--show", "b09:zzz"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)


@unittest.skipUnless(_has_playwright(), "npm run setup で playwright を入れると実行される")
class DividerAboveHeader(LayoutFeedback20261012):
    """check_layout：表の列の区切り線・行の軸の縦線が見出しの行まで伸びている（WARN。§6）"""

    def table(self, head_divider):
        th = "border-bottom:2px solid #333;" + ("border-left:1px dotted #999;" if head_divider else "")
        rows = "".join(f'<tr><td>部門{i}</td><td style="border-left:1px dotted #999">月に約{i}0件</td><td style="border-left:1px dotted #999">担当{i}名</td></tr>' for i in range(1, 4))
        return (f'<table style="border-collapse:collapse"><tr><th style="border-bottom:2px solid #333">部門</th><th style="{th}">件数</th>'
                f'<th style="{th}">担当</th></tr>{rows}</table><div style="height:250px;border:1px solid #333">図</div>')

    def test_divider_in_header_warns(self):
        self.assertTrue(any("縦の線が見出しの行まで" in l for l in self.layout(self.table(True))))

    def test_divider_only_in_body_passes(self):
        self.assertFalse(any("縦の線が見出しの行まで" in l for l in self.layout(self.table(False))))

    def axis_table(self, head_line):
        th0 = "border-bottom:2px solid #333;" + ("border-right:2px solid #333;" if head_line else "")
        rows = "".join(f'<tr><td style="border-right:2px solid #333;font-weight:700">部門{i}</td><td>月に約{i}0件</td><td>担当{i}名</td></tr>' for i in range(1, 4))
        return (f'<table style="border-collapse:collapse"><tr><th style="{th0}">部門</th><th style="border-bottom:2px solid #333">件数</th>'
                f'<th style="border-bottom:2px solid #333">担当</th></tr>{rows}</table><div style="height:250px;border:1px solid #333">図</div>')

    def test_axis_line_in_header_warns(self):
        self.assertTrue(any("縦の線が見出しの行まで" in l for l in self.layout(self.axis_table(True))))

    def test_axis_line_only_in_body_passes(self):
        self.assertFalse(any("縦の線が見出しの行まで" in l for l in self.layout(self.axis_table(False))))
