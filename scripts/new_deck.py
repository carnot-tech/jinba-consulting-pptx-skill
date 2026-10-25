#!/usr/bin/env python3
"""
new_deck.py — 2つのパーツ集から必要なパーツだけを取り出し、1本の自由記述デッキ（HTML）を組み立てる。

  python3 scripts/new_deck.py --parts b01,b02,m05,b06,m10,b09,b10 --title "資料名" -o mydeck.html

  b01〜b30 = templates/freeform_parts_16x9.html（基本パーツ集）のパーツ番号
  m01〜m35 = templates/freeform_parts_more_16x9.html（追加パーツ集）のパーツ番号
  番号は references/archetype-catalog.md と assets/SlideCatalog_16x9.pdf のページ順（基本 P.1〜30、追加 P.31〜65 → m01〜m35）

出力は単体HTML。2つのパーツ集はCSSの設計が違う（基本＝.s / 追加＝.slide）ので、
基本パーツ集の要素セレクタ（h1・table・th・td など）は .s 配下に、追加パーツ集の * / body は .slide 配下に
スコープして結合する。両方のトークン（:root）は同じ値なので、配色・書体は自動で揃う。
ページ番号（フッター）は並び順で振り直す。表紙（b01）・章扉（b04）・裏表紙（b10）は番号を振らない。

  --list   よく使う部品（規約を満たすことを確かめた20種類）の番号・型名・使いどころを表示して終了
  --all    --list と一緒に付けると、残りの型も含めた62型すべてを表示する
  --show b09,m05   指定した部品の HTML（section だけ）を表示して終了。パーツ集の原本は開かない
"""
import argparse, pathlib, re, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = ROOT / "templates" / "freeform_parts_16x9.html"
MORE = ROOT / "templates" / "freeform_parts_more_16x9.html"


def read(p):
    return p.read_text(encoding="utf-8")


def split_css(html):
    """先頭のHTMLコメント内に「<style>」の文字列があるので、コメント終了（-->）以降の実タグを探す。"""
    start = html.find("-->")
    i = html.index("<style>", start if start >= 0 else 0) + len("<style>")
    j = html.index("</style>", i)
    return html[i:j]


def sections(html, cls):
    """<section class="cls ..."> ... </section> を順に返す（入れ子なし前提）。"""
    return re.findall(rf'<section class="{cls}[^"]*">.*?</section>', html, flags=re.S)


def scope_css(css, prefix, section_classes=()):
    """トップレベルのセレクタをすべて prefix（.s / .slide）配下にスコープする。
    - :root / html / body / @page などはそのまま
    - .deck / .skin-* はセクションの祖先なのでそのまま
    - 先頭が prefix で始まる（.s / .slide…）ものはそのまま
    - 先頭のクラスが section 要素自身に付くクラス（cover / chap / slide--dense …）なら prefix と結合（.s.cover）
    - それ以外は「prefix セレクタ」（子孫）にする
    @media の中は再帰的に処理する。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    i = 0
    n = len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            out.append(css[i:])
            break
        sel = css[i:j]
        depth = 1
        k = j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        body = css[j + 1 : k - 1]
        s = sel.strip()
        if s.startswith("@media") or s.startswith("@supports"):
            out.append(f"{sel}{{{scope_css(body, prefix, section_classes)}}}")
        elif s.startswith("@"):
            out.append(f"{sel}{{{body}}}")
        else:
            parts = []
            for one in s.split(","):
                t = one.strip()
                if not t:
                    continue
                head = re.split(r"[\s>+~]", t, maxsplit=1)[0]
                if t.startswith(":root") or t.startswith("html") or t == "body" or t.startswith("body ") or t.startswith("body.") or head.startswith(".deck") or head.startswith(".skin-"):
                    parts.append(t)
                elif head == prefix or head.startswith(prefix + ".") or head.startswith(prefix + ":") or head.startswith(prefix + "-") or t.startswith(prefix + " "):
                    parts.append(t)
                elif head.startswith(".") and head.split(":")[0].lstrip(".").split(".")[0] in section_classes:
                    parts.append(f"{prefix}{t}")
                elif t == "*":
                    parts.append(f"{prefix} *")
                else:
                    parts.append(f"{prefix} {t}")
            out.append(f"{', '.join(parts)}{{{body}}}")
        i = k
    return "".join(out)


def section_classes(html, cls):
    """<section class="cls xxx"> に付いている cls 以外のクラス名（cover / chap / slide--dense …）。"""
    found = set()
    for m in re.finditer(rf'<section class="{cls}([^"]*)"', html):
        for c in m.group(1).split():
            found.add(c)
    return found


def part_names(html, cls):
    """section 直前のコメント（パーツNN: 名前）があればそれを、なければ h1 から名前を拾う。"""
    cm = re.findall(r"<!-- ═══ パーツ(\d+): ([^（═\n]+)", html)
    if len(cm) == len(sections(html, cls)):
        return [n.strip() for _, n in cm]
    names = []
    for sec in sections(html, cls):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", sec, flags=re.S)
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        if not t:
            m2 = re.search(r'class="(?:big|cover-title)[^"]*"[^>]*>(.*?)<', sec, flags=re.S)
            t = (m2.group(1).strip() if m2 else "") or "（表紙／裏表紙）"
        names.append(t)
    return names


# よく使う部品。規約（slide-rules.md）と機械チェックを満たすことを確かめた20種類。
# 資料の順番ではなく、ページが見せる材料の関係で分けてある。形を決めてから、その形の部品を引く。
# 合わなければ --all の型を見るか、規約の範囲で自由に組む。
CORE = [
    (None, "資料の枠（要るものだけ置く）", ""),
    ("b01", "表紙", "資料名・日付・作成者"),
    ("m01", "エグゼクティブサマリー", "冒頭で結論と論点を一望させる。各行に P.n 参照"),
    ("b02", "全体マップ", "論点と該当ページの対応を1枚で示す（サマリーと重ねない）"),
    ("b27", "章扉（アジェンダ再掲）", "本文11枚以上で章を区切る。現在の章だけ強調"),
    ("b10", "裏表紙", "締め（出典行に制作クレジット1行）"),
    (None, "数字で事実を見せる", ""),
    ("m05", "単一チャート＋含意", "1つの棒グラフで事実を示し、右に意味合い（項目比較・時系列）"),
    ("m06", "積み上げ棒", "内訳・構成の比較（全体の中の一部を見せる）"),
    ("m07", "寄与度ブリッジ", "増減の要因を起点→着地で示す"),
    ("b07", "大型数値の表＋読み取り", "数値を行に並べ、右に読み取り"),
    (None, "項目を同じ観点で比べる", ""),
    ("b09:axb", "軸ボックスの表", "行の名前（領域・役割・課題・打ち手など）を左の塗りの箱で示し、右に観点の列を並べる。行ごとに何を・誰が・いつ・効果を比べるとき"),
    ("b09", "線だけの表", "行の名前が年度・数字など短く、箱にするほどでないとき"),
    ("m10", "選択肢の比較表", "複数案を評価軸で比べ、推す案を示す"),
    ("m15", "2×2マトリクス", "2つの物差しで候補を位置づけ、選ぶ（軸の名前と両端を書く）"),
    (None, "分ける・つなぐ（分解と因果）", ""),
    ("m25", "イシューツリー", "問いを答えを決める要素に分解する"),
    ("b06", "前提→帰結の2カラム", "左に事実・表、右に「だから何が起きるか」。強い因果に三角"),
    ("b26", "課題と打ち手の2カラム", "課題と打ち手を行で対応させる"),
    ("b11", "主張パネル＋図", "左の濃色パネルに論点の主張、右に図表（章の各論）"),
    (None, "進め方と決めること", ""),
    ("m20", "提言の柱", "互いに独立した打ち手を並べる。数は材料で決める。打ち手ごとに中身・担当・時期を比べるなら軸ボックスの表"),
    ("m28", "プロセスの段階", "手順・段階を横に並べる"),
    ("m33", "ロードマップ", "時期ごとに具体的な中身があるとき（中身が薄ければ、打ち手の表に時期の列を足す）"),
    ("m35", "意思決定ページ", "この会議で決める事項があるときだけ。サマリーで言い切れるなら置かない"),
]


VARIANTS = {"axb"}  # 部品の変形（b09:axb＝軸ボックスの表）


def apply_variant(sec, var):
    """変形の class を、その部品の最初の table に付ける"""
    if not var:
        return sec
    if var not in VARIANTS:
        sys.exit(f"変形の指定が不正: :{var}（使えるもの: {', '.join(sorted(VARIANTS))}）")
    if re.search(r"<table\b[^>]*\bclass=\"", sec):
        return re.sub(r'(<table\b[^>]*\bclass=")', rf"\g<1>{var} ", sec, count=1)
    return re.sub(r"<table\b", f'<table class="{var}"', sec, count=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parts", help="例: b01,b02,m05,b09,b10")
    ap.add_argument("--title", default="資料名")
    ap.add_argument("-o", "--out", default="mydeck.html")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--show", help="例: b09,m05（その部品の section の HTML だけを表示する）")
    a = ap.parse_args()

    base_html, more_html = read(BASE), read(MORE)
    base_secs, more_secs = sections(base_html, "s"), sections(more_html, "slide")

    if a.show:
        for tok in a.show.split(","):
            m = re.match(r"^([bm])(\d{1,2})(?::(\w+))?$", tok.strip().lower())
            if not m:
                sys.exit(f"パーツ指定が不正: {tok}")
            pool = base_secs if m.group(1) == "b" else more_secs
            idx = int(m.group(2))
            if not 1 <= idx <= len(pool):
                sys.exit(f"範囲外: {tok}")
            print(f"<!-- {tok.strip().lower()} -->\n{apply_variant(pool[idx - 1], m.group(3))}\n")
        return

    if (a.list or not a.parts) and not a.all:
        if not a.parts and not a.list:
            print("--parts で並び順を指定する（例: --parts b01,m01,b09:axb,m05,b10）。一覧:", file=sys.stderr)
        print("（ページごとに形を決めてから引く。並びは資料の順番ではない）")
        for pid, nm, use in CORE:
            print(f"\n■ {nm}" if pid is None else f"{pid}  {nm}：{use}")
        print("\n（ほかの型は --list --all。どれも合わなければ規約の範囲で自由に組む）")
        return

    if a.list or not a.parts:
        for i, nm in enumerate(part_names(base_html, "s"), 1):
            print(f"b{i:02d}  {nm}")
        for i, nm in enumerate(part_names(more_html, "slide"), 1):
            print(f"m{i:02d}  {nm}")
        return

    picked = []
    for tok in a.parts.split(","):
        tok = tok.strip().lower()
        m = re.match(r"^([bm])(\d{1,2})(?::(\w+))?$", tok)
        if not m:
            sys.exit(f"パーツ指定が不正: {tok}（b01〜b{len(base_secs):02d} / m01〜m{len(more_secs):02d}。変形は b09:axb）")
        kind, idx = m.group(1), int(m.group(2))
        pool = base_secs if kind == "b" else more_secs
        if not 1 <= idx <= len(pool):
            sys.exit(f"範囲外: {tok}")
        picked.append((kind, apply_variant(pool[idx - 1], m.group(3))))

    # ページ番号を振り直す（表紙・裏表紙＝ b01 / b10 は番号なし）
    page = 0
    body = []
    for kind, sec in picked:
        is_cover = kind == "b" and ('class="s cover"' in sec or 'class="s chap"' in sec)  # 表紙・裏表紙・章扉は番号なし（slide-rules §4.45）
        if not is_cover:
            page += 1
        if kind == "b":
            sec = re.sub(r'(<div class="foot"><b>)[^<]*(</b><span>)[^<]*(</span>)',
                         lambda mm: f"{mm.group(1)}{a.title}{mm.group(2)}{'' if is_cover else page}{mm.group(3)}", sec)
            sec = re.sub(r'(<div class="logo">)[^<]*(</div>)', rf"\g<1>{a.title}\g<2>", sec)
        else:
            sec = re.sub(r'(<footer class="footer">.*?</span><span>)\d*(</span>)', rf"\g<1>{page}\g<2>", sec, flags=re.S)
            # 見出し様式を基本パーツ集に揃える（slide-rules §4.19）: kicker をロゴ＋右上チップのバーに置き換える
            km = re.search(r'<div class="kicker">(.*?)</div>', sec, flags=re.S)
            kick = re.sub(r"<[^>]+>", "", km.group(1)).strip() if km else ""
            # 見本の型ID（「05  chart_insight」）は、基本パーツ集の見本（「パーツ09｜軸のある表」）と同じ伏せ字の形にする。
            # 書き換え忘れは check_deck が伏せ字として FAIL にする（右上のラベルは、そのページの話題を日本語で書く）
            tm = re.match(r"^(\d{2})\s+([a-z][a-z0-9_]*)$", kick)
            if tm:
                kick = f"パーツ{tm.group(1)}｜{tm.group(2)}"
            bar = f'<div class="hdr"><div class="logo">{a.title}</div><div class="date">{kick}</div></div>'
            sec = re.sub(r'<div class="kicker">.*?</div>', bar, sec, count=1, flags=re.S)
        body.append(sec)

    base_css = scope_css(split_css(base_html), ".s", section_classes(base_html, "s"))
    more_css = scope_css(split_css(more_html), ".slide", section_classes(more_html, "slide"))
    # :root は両方残す（色・書体は同値。追加パーツ集側は版面の余白変数も持つ）

    out = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>{a.title}</title>
<!-- scripts/new_deck.py で生成。基本パーツ集（.s）と追加パーツ集（.slide）のCSSをスコープして結合してある。
     規約: references/slide-rules.md ／ 納品前: python3 scripts/check_deck.py {a.out} → FAIL 0 -->
<style>
/* ===== 基本パーツ集（templates/freeform_parts_16x9.html）===== */
{base_css}
/* ===== 追加パーツ集（templates/freeform_parts_more_16x9.html）===== */
{more_css}
/* ===== 追加パーツ集の見出しバーを基本パーツ集と同じ様式にする（.slide は zoom:0.8 なので px は 1/0.8 倍） ===== */
.slide .hdr{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:0;padding-bottom:10px;margin-bottom:6px}}
.slide .hdr .logo{{font-family:var(--font-serif);font-weight:600;font-size:30px;color:var(--navy);line-height:1.1;visibility:hidden}}  /* 本文ページの上部は右上のラベルだけ（§4.62） */
.slide .hdr .date{{font-size:12.5px;letter-spacing:.15em;color:var(--muted)}}
.slide .title{{margin-top:14px}}
/* ===== 系統間の文字スケールも揃える（.s基準の実効サイズ: タイトル22pt・列見出し14.5pt・本文11.5pt。§6
   .slide は zoom:0.8 なので authored px = 実効pt ÷ 0.6） ===== */
.slide .title{{font-size:36.6px}}
.slide .ism-col-label{{font-size:24.2px}}
.slide .ism-issue, .slide .ism-solution-text{{font-size:19.2px}}
/* ===== 画面表示は zoom でなく transform で縮小する =====
   zoomの画面描画・ボックス寸法はエンジン/ビューア依存（一部のビューアで .slide だけ大きく見える）。
   画面では箱を .s と同じ 338.67mm に固定し、中身は1600×900座標系のまま0.8倍。
   印刷は従来の zoom 方式のまま（transform＋1600px実レイアウトはChromeの印刷
   shrink-to-fit を誘発して全ページが縮むため、printには適用しない） */
@media not print{{
  .slide{{width:338.67mm;height:190.5mm;zoom:1;aspect-ratio:auto}}
  .slide .sinner{{inset:auto;left:0;top:0;width:1600px;height:900px;
    padding:var(--margin-y) var(--margin-x);box-sizing:border-box;
    transform:scale(0.8);transform-origin:top left}}
}}
/* ===== 画面幅がスライド幅（338.67mm）より狭いときは等比で縮める（下の script が .fitwrap で包む） =====
   印刷・PDF・check_layout（いずれも印刷メディア）では縮小を外して原寸に戻す。
   パーツ集側の .fitwrap 指定は結合時に .s の内側へスコープされて効かないので、ここで指定する */
@media print{{
  .fitwrap{{width:auto!important;height:auto!important;margin:0!important;overflow:visible!important}}
  .fitwrap>.s, .fitwrap>.slide{{transform:none!important}}
}}
</style></head><body>
<main class="deck skin-warm">
{chr(10).join(body)}
</main>
<script>
(function () {{
  var printing = window.matchMedia ? window.matchMedia("print") : null;
  function fit() {{
    var avail = Math.max(1, document.documentElement.clientWidth - 24);
    document.querySelectorAll(".deck > .s, .deck > .slide, .fitwrap > .s, .fitwrap > .slide").forEach(function (el) {{
      if (!el.offsetWidth) return;  // 隠したスライド（社外版の .internal など）は包まない
      var wrap = el.parentElement;
      if (!wrap.classList.contains("fitwrap")) {{
        var cs = getComputedStyle(el);
        wrap = document.createElement("div");
        wrap.className = "fitwrap";
        wrap.style.overflow = "hidden";
        wrap.style.margin = cs.marginTop + " auto " + cs.marginBottom;
        el.parentNode.insertBefore(wrap, el);
        wrap.appendChild(el);
        el.style.margin = "0";
      }}
      el.style.transform = "";
      var s = (printing && printing.matches) ? 1 : Math.min(1, avail / el.offsetWidth);
      el.style.transformOrigin = "top left";
      el.style.transform = s < 1 ? "scale(" + s + ")" : "";
      wrap.style.width = el.offsetWidth * s + "px";
      wrap.style.height = el.offsetHeight * s + "px";
    }});
  }}
  window.addEventListener("resize", fit);
  fit();
}})();
</script>
</body></html>
"""
    # ファイル名は NFC に揃える（macOS は濁点を分けた形で保存することがあり、Windows で文字化けして見える — slide-rules §8）
    a.out = unicodedata.normalize("NFC", a.out)
    pathlib.Path(a.out).write_text(out, encoding="utf-8")
    print(f"wrote {a.out}: {len(picked)} slides（番号付き {page} ページ）")


if __name__ == "__main__":
    main()
