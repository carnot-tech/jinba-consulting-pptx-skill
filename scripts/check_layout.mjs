#!/usr/bin/env node
// フォーマットの機械検査（レンダリングが必要な項目）— slide-rules §8 の目視QAを一部機械化
//   1. フッター（.foot / .footer）と本文要素の重なり
//   2. タイトル（h1 / .title）の右端はみ出し（nowrap + overflow:hidden の黙殺検出）
//   3. スライド外への要素はみ出し
//   4. 空きの多いページ（タイトル下〜フッター上の版面のうち、本文が占める縦の範囲の外側が40%超。上下に寄せた空きも数える）
//   5. 中身の無い列が残ったグリッド（項目を減らしたのに列数がそのまま）
//   8. 文字どうしの重なり（WARN）
//   9. 同じ役割（同じ要素・クラス・辺）の罫線の太さがデッキの中で揃っていない（WARN）
//   7. ページ下部の結論帯（クラス名に頼らず位置と形で拾う。WARN）
//   6. ページ間でタイトルの実際の大きさが揃っていない（パーツ集の混在で縮小がかからないページ）。本文の大きさのずれは WARN
//  10. 同じ作りの要素を横に並べたときの幅・高さ・上端のずれ（WARN。§4.51）
//  11. 版面の右側・左側の片方だけが大きく空いている（WARN。§4.54）
//  12. 塗りで立てたハイライトが1ページに2か所以上（WARN。§4.57）
//  13. 表の行を縦に引き伸ばしている（行の高さが中身より1.5行ぶん以上高い表は FAIL、1行ぶん以上は WARN。§4.12）
//  14. 凡例がグラフより下に置かれている（WARN。§5.18: 凡例はグラフの見出しの上に右揃えで置く）
//  15. 左右2列に並べたとき、列の最初の横罫（見出しの下罫・表の上罫）の高さがずれている（WARN。§4.21）
//  16. 塗り・枠のある大きな箱、縦の線で区切った列の中が半分以上空いている（WARN。§4.54・§4.12）。中身を上下に離して真ん中が30%超空く（WARN）・45%超（FAIL）
//  17. 文字が箱・セルの外にはみ出している（FAIL）
//  18. 同じ作りの本文の文字が違う大きさ・文の途中の太字が3か所以上（WARN。§4.19・§5.5）
//  19. 棒グラフ: 項目名が軸の線より上にある（棒が線から浮いている）・凡例なしで棒の色が分かれている（WARN。§5.26・§5.5）
//  20. 表の行の上下が間延びしている（行の高さから文字の高さを引いた余りが、文字の大きさの2.2倍超。WARN。§4.12）
//  21. 列・軸の見出しが、その下の本文や行見出しより小さい（WARN。§6・§4.21）
//  22. 文字が、ほかの要素の横罫（見出しの下罫・軸の線など）に重なっている（WARN）
//  23. 同じ作りの箱の左端が、揃うはずの位置から少しずれている（ツリーの段の始まりなど。WARN。§4.51）
//  24. 行のリスト（罫線で区切った行の並び）の間延び・左右2列の行の位置のずれ（WARN。§4.12・§4.51）
//  25. 並べた見出し・大きな数字のうち、一部だけが2行に折れている（WARN。§4.51・§2.13）
//  26. 表の列の区切り線・行の軸の縦線が、見出しの行まで伸びて見出しの下罫より上に出ている（WARN。§6）
//  28. PDF のページ数がスライドの枚数と合わない（FAIL）。タイトルが22ptから±10%超ずれる（FAIL。§2.1）
//  27. 並べた項目（箇条書き・同じ種類の縦の並び）の間が、余白・gap の決まりより文字の1.5倍超（WARN）・3倍超（FAIL）余分に空いている間延び（§4.12）
//   4 の補足: 版面の30%超が空いているときは WARN（40%超は FAIL）
// 正本から差し込んだ定型ページ（section に .std。§4.99）は、はみ出し以外の検査を飛ばす
// 使い方: node scripts/check_layout.mjs deck.html [--all]   （--all で指摘を全件表示。既定は FAIL・WARN 各20件まで。playwright 必須: リポ直下で `npm run setup`。PLAYWRIGHT_MODULE_DIR でも解決可）
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadPlaywright() {
  const cands = [
    process.env.PLAYWRIGHT_MODULE_DIR,
    path.join(process.cwd(), "node_modules", "playwright"),
    path.join(path.dirname(new URL(import.meta.url).pathname), "..", "node_modules", "playwright"),
  ].filter(Boolean);
  for (const c of cands) {
    try { return (await import(pathToFileURL(path.join(c, "index.mjs")).href)); } catch {}
    try { const m = await import(pathToFileURL(path.join(c, "index.js")).href); return m.default ?? m; } catch {}
  }
  return await import("playwright");
}

const file = process.argv.slice(2).find((a) => !a.startsWith("--"));
if (!file) { console.error("usage: node check_layout.mjs deck.html [--all]"); process.exit(2); }

const pw = await loadPlaywright();
const browser = await pw.chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
// 印刷レイアウトで検査（ビューポート追従スケーラーの影響を受けない）
await page.emulateMedia({ media: "print" });
await page.goto(pathToFileURL(path.resolve(file)).href);
await page.waitForTimeout(300);

const { issues, warns } = await page.evaluate(() => {
  const out = [];
  const warnOut = [];
  // 実際に描かれる文字の大きさ（zoom・transform 込み）。全角1文字の幅を測る
  const effSize = (el) => {
    const probe = document.createElement("span");
    probe.textContent = "あ";
    probe.style.cssText = "position:absolute;visibility:hidden;white-space:nowrap;padding:0;border:0;letter-spacing:0";
    el.appendChild(probe);
    const w = probe.getBoundingClientRect().width;
    probe.remove();
    return w;
  };
  const sizes = [];
  const borders = {};
  // 要素の直下にある文字の、実際に描かれた矩形（子要素の文字は含めない）
  const ownTextRects = (el) => {
    const rs = [];
    for (const nd of el.childNodes) {
      if (nd.nodeType !== 3 || !nd.textContent.trim()) continue;
      const rg = document.createRange();
      rg.selectNodeContents(nd);
      for (const r of rg.getClientRects()) if (r.width > 1 && r.height > 1) rs.push(r);
    }
    return rs;
  };
  const isFilled = (st) => { const bg = st.backgroundColor; return bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg); };
  const isBoxed = (st) => isFilled(st) || ["Top", "Right", "Bottom", "Left"].every((k) => parseFloat(st[`border${k}Width`]) > 0 && st[`border${k}Style`] !== "none");
  const slides = [...document.querySelectorAll("section.s, section.slide, .slide")];
  // ページの本文の実際の大きさ（中央値）。6 の揃いの検査と、4 の zoom の試算の上限で同じ測り方を使う
  const bodySize = (s) => {
    const body = [...s.querySelectorAll("li, td, p")].filter((el) => (el.textContent || "").trim().length > 8 && !el.closest(".src, .foot, .footer"));
    const bs = body.map(effSize).filter((v) => v > 0).sort((a, b) => a - b);
    return bs.length ? bs[Math.floor(bs.length / 2)] : 0;
  };
  const deckBody = (() => {
    const v = slides.filter((s) => !s.matches(".std, .cover, .chap, .back")).map(bodySize).filter((x) => x > 0).sort((a, b) => a - b);
    return v.length ? v[Math.floor(v.length / 2)] : 0;
  })();
  slides.forEach((s, i) => {
    const n = i + 1;
    const sr = s.getBoundingClientRect();
    const std = s.matches(".std");
    const foot = s.querySelector(".foot, .footer, footer");
    const fr = foot ? foot.getBoundingClientRect() : null;
    const els = [...s.querySelectorAll("*")].filter((el) => {
      if (foot && (el === foot || foot.contains(el))) return false;
      const st = getComputedStyle(el);
      if (st.display === "none" || st.visibility === "hidden") return false;
      return (el.textContent || "").trim().length > 0 || el.tagName === "IMG";
    });
    // 4. 版面の下側の空き（表紙・章扉・裏表紙は対象外）
    if (!std && !s.matches(".cover, .chap")) {
      const ttl = s.querySelector("h1, .title, .ttl");
      const top = ttl ? ttl.getBoundingClientRect().bottom : sr.top;
      const bottom = fr ? fr.top : sr.bottom;
      // 図形（svg・画像・塗りや罫線のある箱）も本文に数える
      const isShape = (el) => {
        if (/^(svg|img|canvas)$/i.test(el.tagName)) return true;
        const st = getComputedStyle(el);
        const bg = st.backgroundColor;
        const filled = bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg);
        const bordered = ["Top", "Right", "Bottom", "Left"].some((k) => parseFloat(st[`border${k}Width`]) > 0 && st[`border${k}Style`] !== "none");
        return filled || bordered || st.clipPath !== "none";
      };
      // 本文が占める縦の範囲（span）と、フッターへのはみ出し（over）を測る
      const spanNow = () => {
        let contentBottom = -Infinity, contentTop = Infinity, maxText = -Infinity;
        for (const el of els) {
          if (el === ttl || (ttl && ttl.contains(el))) continue;
          if (el.children.length > 0 && el.tagName !== "IMG" && el.tagName !== "svg") continue;
          const r = el.getBoundingClientRect();
          if (r.height === 0 || r.width === 0) continue;
          if (r.bottom > top + 1) maxText = Math.max(maxText, r.bottom);
          if (el.closest(".src, .bar")) continue; // 出典行・上部バーは本文に数えない
          if (r.bottom <= top + 1 || r.top >= bottom - 1) continue; // タイトルより上（右上のラベル等）・フッターより下は版面の外
          contentBottom = Math.max(contentBottom, r.bottom);
          contentTop = Math.min(contentTop, r.top);
        }
        for (const el of s.querySelectorAll("*")) {
          if (el.closest(".bar, .src") || (foot && foot.contains(el))) continue;
          if (el.closest("h1, .title, .ttl")) continue;
          if (!isShape(el)) continue;
          const r = el.getBoundingClientRect();
          if (r.height > 0 && r.bottom <= bottom + 1 && r.top >= top - 1) {
            contentBottom = Math.max(contentBottom, r.bottom);
            contentTop = Math.min(contentTop, r.top);
          }
        }
        return { span: contentBottom > contentTop ? contentBottom - contentTop : 0, over: maxText - bottom };
      };
      const area = bottom - top;
      const span = spanNow().span;
      const empty = area > 0 ? 1 - span / area : 0;
      // 器を拡大したときのはみ出し: 文字の下端だけでなく、器の中の全要素（表・図形・画像を含む）の外接矩形の右端・下端を見る
      const overflowOf = (box) => {
        const sr = s.getBoundingClientRect();
        let over = 0;
        for (const el of box.querySelectorAll("*")) {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          over = Math.max(over, r.bottom - bottom, r.right - sr.right);
        }
        return over;
      };
      // 本文の器を何倍にすれば空きが WARN の閾値（30%）を切るかを試算して添える。FAIL（40%超）のページも 30% を目標にする
      // 上限は 1.15 倍。ただし本文の大きさが、デッキの中央値の ±15%（6 の揃いの検査）を超えない倍率までにする
      const fitHint = () => {
        const limit = 0.3;
        const box = s.querySelector(":scope .c, :scope .sinner > .content");
        if (!box || area <= 0) return "";
        const orig = box.style.zoom;
        let best = null, sizeCap = false;
        // 拡大前からはみ出している分（別の FAIL で出る）は、器の中もページの文字も差し引いて比べる
        const base = Math.max(1, overflowOf(box) + 1);
        const baseOver = Math.max(1, spanNow().over + 1);
        for (const z of [1.05, 1.1, 1.15]) {
          box.style.zoom = String(z);
          const m = spanNow();
          if (m.over > baseOver || overflowOf(box) > base) break;
          if (deckBody && bodySize(s) / deckBody > 1.15) { sizeCap = true; break; }
          best = { z, empty: 1 - m.span / area };
          if (best.empty <= limit - 0.02) break;
        }
        box.style.zoom = orig;
        const name = box.classList.contains("c") ? ".c" : ".content";
        const pct = Math.round(limit * 100);
        if (!best && sizeCap) return ` 試算: 本文の器（${name}）を1.05倍にするだけで本文が他のページより15%超大きくなる。拡大では直らないので、配置を変えるか前後のページとまとめる。`;
        if (!best) return ` 試算: 本文の器（${name}）を1.05倍にするだけで版面からはみ出す。拡大では直らないので、配置を変えるか前後のページとまとめる。`;
        if (best.empty <= limit) return ` 試算: このページの本文の器（${name}）に zoom:${best.z} を付けると空き約${Math.round(best.empty * 100)}%（はみ出しなし）。`;
        const why = sizeCap ? "本文の大きさを他のページと揃えられる" : "はみ出さない";
        return ` 試算: 本文の器（${name}）を${why}上限の${best.z}倍にしても空き約${Math.round(best.empty * 100)}%で${pct}%を切らない。前後のページとまとめるか、形を変える（文字をさらに大きくすると、他のページと本文の大きさが揃わなくなる）。`;
      };
      if (empty > 0.4) {
        out.push(`p${n}: 版面の ${Math.round(empty * 100)}% が空いている（40%超。直し方は、文字を一段大きくする・配置を変える（右に意味合いの列を置く等）・前後のページと統合する。空きを埋めるために数字・事例・行を足さない。項目の間や列の高さを広げて埋めない — §4.12・§5.13）${fitHint()}`);
      } else if (empty > 0.3) {
        warnOut.push(`p${n}: 版面の ${Math.round(empty * 100)}% が空いている（30%超。「下が空きすぎ」と差し戻されやすい。文字を一段大きくする・配置を変える。空きを埋めるために中身を足さない — §5.13）${fitHint()}`);
      }
    }
    // 13. 表の行の縦の引き伸ばし（§4.12）: 行の高さのうち、一番高いセルの中身と上下の余白を超える分を1行の高さで割る
    // 見出し行（全セルが th）だけを除く。行見出しに th を使う行は対象に含める
    // 中身の高さは文字の行ボックスに、セル内のブロック要素（ul・p 等）の上下 margin を足して測る
    for (const t of std ? [] : s.querySelectorAll("table")) {
      const ratios = [];
      for (const r of [...t.rows].filter((r) => r.cells.length && ![...r.cells].every((c) => c.tagName === "TH"))) {
        const rh = r.getBoundingClientRect().height;
        let need = 0, line = 0;
        for (const c of r.cells) {
          const rg = document.createRange(); rg.selectNodeContents(c);
          const rs = [...rg.getClientRects()].filter((x) => x.height > 0 && x.width > 0);
          if (!rs.length) continue;
          let top = Math.min(...rs.map((x) => x.top)), bot = Math.max(...rs.map((x) => x.bottom));
          for (const ch of c.querySelectorAll("*")) {
            const cr = ch.getBoundingClientRect();
            if (!cr.height) continue;
            const ms = getComputedStyle(ch);
            top = Math.min(top, cr.top - Math.max(0, parseFloat(ms.marginTop) || 0));
            bot = Math.max(bot, cr.bottom + Math.max(0, parseFloat(ms.marginBottom) || 0));
          }
          const cs = getComputedStyle(c);
          need = Math.max(need, bot - top + parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom));
          line = Math.max(line, parseFloat(cs.fontSize) * 1.5);
        }
        if (rh > 0 && need > 0 && line > 0) ratios.push(Math.max(0, rh - need) / line);
      }
      if (ratios.length < 2) continue;
      ratios.sort((a, b) => a - b);
      const med = ratios[Math.floor(ratios.length / 2)];
      if (med >= 1.5) out.push(`p${n}: 表の行が中身より約${med.toFixed(1)}行ぶん高く、縦に引き伸ばされている（§4.12: 行の高さは中身なりにし、空くなら文字を一段大きくして縦中央に置く）`);
      else if (med >= 1.0) warnOut.push(`p${n}: 表の行が中身より約${med.toFixed(1)}行ぶん高い（§4.12: 引き伸ばしの疑い）`);
    }
    // 14. 凡例の位置（§5.18）: 凡例がグラフ（SVG・canvas、または同じ幅か高さで並ぶ2本以上の塗りの棒・セル）より下にある
    // 凡例の判定はクラス名のトークン単位（legend を含むか lg そのもの）。text-lg・col-lg-6 等は凡例とみなさない
    // グラフは凡例の親から3階層まで（section 自身を含む）で探す。数値タイル・カード1枚のような塗りの箱1つはグラフとみなさない
    const isLegend = (el) => [...(el.classList || [])].some((t) => /legend/i.test(t) || /^lg$/i.test(t));
    for (const lg of std ? [] : s.querySelectorAll("*")) {
      if (!isLegend(lg) || (lg.parentElement && lg.parentElement.closest("[class*=legend]"))) continue;
      const lr = lg.getBoundingClientRect();
      if (!lr.height) continue;
      let scope = lg.parentElement, chartBottom = null;
      for (let k = 0; k < 3 && scope && chartBottom === null; k++, scope = scope === s ? null : scope.parentElement) {
        let bot = -Infinity;
        const boxes = [];
        for (const e of scope.querySelectorAll("svg, canvas, div, span, i")) {
          if (lg.contains(e) || e.closest("table") || e.closest(".foot, .footer")) continue;
          const r = e.getBoundingClientRect();
          if (!r.width || !r.height) continue;
          if (/^(svg|canvas)$/i.test(e.tagName) && r.width > 60 && r.height > 40) { bot = Math.max(bot, r.bottom); continue; }
          const bg = getComputedStyle(e).backgroundColor;
          const filled = bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg) && !/rgb\(255, 255, 255\)/.test(bg);
          // 棒・ヒートマップのセルは文字が少ない（値ラベル程度）。文章の入った箱はグラフに数えない
          if (filled && (r.width > 30 || r.height > 30) && r.width < sr.width * 0.6 && (e.textContent || "").trim().length <= 8) boxes.push(r);
        }
        // 同じ幅（縦棒）か同じ高さ（横棒・セル）の塗りの箱が2つ以上あるときだけ、グラフとみなす
        const same = (a, b) => Math.abs(a - b) <= 1;
        const bars = boxes.filter((a) => boxes.some((b) => b !== a && (same(a.width, b.width) || same(a.height, b.height))));
        for (const r of bars) bot = Math.max(bot, r.bottom);
        if (isFinite(bot)) chartBottom = bot;
      }
      if (chartBottom !== null && lr.top >= chartBottom - 2) {
        warnOut.push(`p${n}: 凡例がグラフの下にある「${(lg.textContent || "").trim().replace(/\s+/g, " ").slice(0, 24)}」（§5.18: 凡例はグラフの見出しの上に右揃えで置く）`);
      }
    }
    // 5. 中身の無い列が残ったグリッド
    for (const g of std ? [] : s.querySelectorAll("*")) {
      const st = getComputedStyle(g);
      if (st.display !== "grid" || st.visibility === "hidden") continue;
      const tracks = st.gridTemplateColumns.split(" ").map(parseFloat).filter((v) => v > 0);
      const kids = [...g.children].filter((c) => getComputedStyle(c).display !== "none");
      if (tracks.length < 2 || kids.length === 0) continue;
      const gr = g.getBoundingClientRect();
      const scale = g.offsetWidth ? gr.width / g.offsetWidth : 1;
      const gap = (parseFloat(st.columnGap) || 0) * scale;
      let x = gr.left + (parseFloat(st.paddingLeft) || 0) * scale + (parseFloat(st.borderLeftWidth) || 0) * scale;
      const empty = [];
      tracks.forEach((w, k) => {
        const l = x, r = x + w * scale;
        const used = kids.some((c) => { const cr = c.getBoundingClientRect(); return cr.width > 0 && cr.left < r - 1 && cr.right > l + 1; });
        if (!used && w * scale > 20) empty.push(k + 1);
        x = r + gap;
      });
      if (empty.length) out.push(`p${n}: グリッドに中身の無い列が残っている（${tracks.length}列中 ${empty.join("・")}列目。列数を項目数に合わせる）`);
    }
    // 7. ページ下部の結論帯：版面の下3割に置いた、横幅7割以上・高さ15%以下の塗りか太い上罫のある文字の帯
    if (!std && !s.matches(".cover, .chap, .back")) {
      for (const el of s.querySelectorAll("div, p, section, aside")) {
        if (el.closest("table, .foot, .footer, footer, .src") || el === s) continue;
        if (!(el.textContent || "").trim()) continue;
        const r = el.getBoundingClientRect();
        if (r.width < sr.width * 0.7 || r.height > sr.height * 0.15 || r.height < 8) continue;
        const limit = fr ? fr.top : sr.bottom;
        if (r.top < sr.top + sr.height * 0.7 || r.bottom > limit + 2) continue;
        const st = getComputedStyle(el);
        const bg = st.backgroundColor;
        const filled = bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg);
        const ruled = parseFloat(st.borderTopWidth) >= 2 && st.borderTopStyle !== "none";
        if (!filled && !ruled) continue;
        // 柱＋土台の図（柱のグリッドや同じ帯が上に積まれている）は図の一部なので対象外
        const prev = el.previousElementSibling;
        if (prev && ((el.className && prev.className === el.className) ||
            (getComputedStyle(prev).display === "grid" && getComputedStyle(prev).gridTemplateColumns.split(" ").length >= 3))) continue;
        if (el.parentElement && el.parentElement.closest("div, p, section, aside") !== s && el.parentElement.getBoundingClientRect().width >= r.width && getComputedStyle(el.parentElement).backgroundColor === bg) continue;
        warnOut.push(`p${n}: ページ下部に結論の帯らしき要素「${(el.textContent || "").trim().slice(0, 24)}」（§4.8: 結論はタイトルへ。帯の形を変えただけの言い換えも同じ）`);
        break;
      }
    }
    // 8. 文字どうしの重なり：文字を持つ葉要素の矩形が、別の葉要素と2割以上重なる
    if (!std) {
      // 文字の行ごとの矩形で比べる（子要素と文字が混ざった要素の文字も拾う）
      const leaves = [];
      for (const el of els) {
        if (el.closest("svg")) continue;
        for (const r of ownTextRects(el)) leaves.push({ el, r });
      }
      let hit = 0;
      for (let a = 0; a < leaves.length && hit < 3; a++) for (let b = a + 1; b < leaves.length && hit < 3; b++) {
        const A = leaves[a], B = leaves[b];
        if (A.el === B.el) continue;
        const ix = Math.min(A.r.right, B.r.right) - Math.max(A.r.left, B.r.left);
        const iy = Math.min(A.r.bottom, B.r.bottom) - Math.max(A.r.top, B.r.top);
        if (ix <= 0 || iy <= 0) continue;
        const small = Math.min(A.r.width * A.r.height, B.r.width * B.r.height);
        if (ix * iy > small * 0.2) {
          hit++;
          warnOut.push(`p${n}: 文字が重なっている「${(A.el.textContent || "").trim().slice(0, 14)}」と「${(B.el.textContent || "").trim().slice(0, 14)}」（重ならない位置に動かす。意図した重ね（図の上の注記など）でも、文字が読めることを画像で確かめて qa.md に書く）`);
        }
      }
    }
    // 9. 罫線の太さを役割（要素名＋クラス＋辺）ごとに集める（背景と同じ色の線は区切りの余白なので数えない）
    // 線の下にある背景の色: 自分か祖先のうち最初に塗りのある要素の色（スライドも透明なら紙の白）。
    // 白い線を一律に外すと、濃色の背景（章扉・主張パネル）の白い区切り線の不揃いを見逃すので、背景と同じ色の線だけを外す
    const bgBehind = (el) => {
      for (let e = el; e; e = e.parentElement) {
        const bg = getComputedStyle(e).backgroundColor;
        if (bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg)) return bg;
      }
      return "rgb(255, 255, 255)";
    };
    for (const el of std ? [] : s.querySelectorAll("*")) {
      const st = getComputedStyle(el);
      for (const side of ["Top", "Bottom", "Left", "Right"]) {
        const w = parseFloat(st[`border${side}Width`]);
        if (!(w > 0) || st[`border${side}Style`] === "none") continue;
        const bc = st[`border${side}Color`];
        if (/rgba\([^)]*,\s*0\)$/.test(bc) || bc === bgBehind(el.parentElement || s)) continue;
        const scale = el.offsetWidth ? el.getBoundingClientRect().width / el.offsetWidth : 1;
        const key = `${el.tagName.toLowerCase()}${el.classList.length ? "." + [...el.classList].sort().join(".") : ""}:${side.toLowerCase()}`;
        (borders[key] ||= new Map()).set(Math.round(w * scale * 2) / 2, n);
      }
    }
    if (!std && !s.matches(".cover, .chap, .back")) {
      // 10. 同じ作り（要素名＋クラス）の兄弟を横に並べたときの幅・高さ・上端のずれ
      let alignHits = 0;
      for (const g of s.querySelectorAll("*")) {
        if (alignHits >= 2) break;
        const gs = getComputedStyle(g);
        const row = gs.display.includes("grid") || (gs.display.includes("flex") && !gs.flexDirection.startsWith("column"));
        if (!row || g.closest("table, svg, .foot, .footer, footer, .src, h1, .title, .ttl")) continue;
        const groups = {};
        for (const c of g.children) {
          const cs = getComputedStyle(c);
          if (cs.display === "none" || cs.position === "absolute" || !(c.textContent || "").trim()) continue;
          const r = c.getBoundingClientRect();
          if (r.width < 60 || r.height < 24) continue; // チップ・タグ・アイコンは対象外
          // 同じ作り＝要素名・クラス・中の子要素の並びが同じもの（左に表・右に箇条のような役割の違う列は比べない）
          const key = c.tagName + "." + [...c.classList].sort().join(".") + "|" + [...c.children].map((x) => x.tagName).join(",");
          (groups[key] ||= []).push(r);
        }
        for (const rs of Object.values(groups)) {
          if (rs.length < 2) continue;
          // 横に並んでいるもの（縦の範囲が半分以上重なる）だけを比べる
          const base = rs[0];
          const side = rs.filter((r) => Math.min(r.bottom, base.bottom) - Math.max(r.top, base.top) > Math.min(r.height, base.height) * 0.5);
          if (side.length < 2) continue;
          const spread = (f) => { const v = side.map(f); return [Math.min(...v), Math.max(...v)]; };
          const [w0, w1] = spread((r) => r.width), [h0, h1] = spread((r) => r.height), [t0, t1] = spread((r) => r.top);
          const what = [];
          // 大きな段差（階段状の配置など）は意図とみなし、作りの揃った要素の小さなずれだけを拾う
          if (t1 - t0 > 30) continue;
          // 幅は対比の2列だけを比べる（3つ以上の列は中身に合わせた幅の配分がありうる）
          // 2倍を超える差は見出しの細い列＋本文のような意図した配分とみなす
          if (side.length === 2 && w1 - w0 > 12 && w1 / w0 > 1.1 && w1 / w0 <= 2) what.push(`幅 ${Math.round(w0)}〜${Math.round(w1)}px`);
          if (t1 - t0 <= 3 && h1 - h0 > 6 && h1 / h0 > 1.06) what.push(`高さ ${Math.round(h0)}〜${Math.round(h1)}px`);
          if (t1 - t0 > 3) what.push(`上端のずれ ${Math.round(t1 - t0)}px`);
          if (what.length) {
            alignHits++;
            warnOut.push(`p${n}: 並べた要素（${side.length}個）の${what.join("・")}が揃っていない（§4.51: 対比の列・同格の箱は 1fr で同じ幅・高さに組む。中身の量の違いは揃えない理由にならない。残すのは役割の違う列（見出しの細い列＋本文など）のときだけで、その理由を qa.md に書く）`);
            break;
          }
        }
      }
      // 15. 左右2列の最初の横罫の高さ（片側は軸タイトル付きの図、片側は見出しのない表、のような組み合わせで下罫の高さがずれる）
      const firstRule = (c, cr) => {
        let y = Infinity;
        for (const el of [c, ...c.querySelectorAll("*")]) {
          if (el !== c && el.closest("svg")) continue;
          const st = getComputedStyle(el);
          if (st.display === "none" || st.visibility === "hidden") continue;
          const r = el.getBoundingClientRect();
          // 列の幅の半分以上にわたる線だけを見る（表のセルは表全体の線の一部として数える）
          const w = el.matches("th, td, tr") ? (el.closest("table")?.getBoundingClientRect().width ?? 0) : r.width;
          if (w < cr.width * 0.5 || r.height === 0) continue;
          if (parseFloat(st.borderTopWidth) >= 1 && st.borderTopStyle !== "none") y = Math.min(y, r.top);
          if (parseFloat(st.borderBottomWidth) >= 1 && st.borderBottomStyle !== "none") y = Math.min(y, r.bottom);
        }
        return y - cr.top;
      };
      for (const g of s.querySelectorAll("*")) {
        const gs = getComputedStyle(g);
        const row = gs.display.includes("grid") || (gs.display.includes("flex") && !gs.flexDirection.startsWith("column"));
        if (!row || g.closest("table, svg, .foot, .footer, footer, .src, h1, .title, .ttl")) continue;
        const cols = [...g.children].filter((c) => {
          const cs = getComputedStyle(c), r = c.getBoundingClientRect();
          return cs.display !== "none" && cs.position !== "absolute" && r.width >= 120 && r.height >= 80 && (c.textContent || "").trim();
        });
        if (cols.length !== 2) continue;
        const [ra, rb] = cols.map((c) => c.getBoundingClientRect());
        if (Math.abs(ra.top - rb.top) > 4 || ra.right > rb.left + 1) continue; // 上端の揃った左右の列だけ
        const ya = firstRule(cols[0], ra), yb = firstRule(cols[1], rb);
        // どちらも列の上のほう（見出しの位置）に横罫があるときだけ比べる
        if (!(ya <= 90 && yb <= 90)) continue;
        if (Math.abs(ya - yb) > 4) {
          warnOut.push(`p${n}: 左右の列の最初の横罫の高さが ${Math.round(Math.abs(ya - yb))}px ずれている（§4.21: 見出しの下罫・表の上罫の高さを揃える。見出しのない側にも同じ高さの見出し行を置く）`);
          break;
        }
      }
      // 16. 塗り・枠のある大きな箱の中の空き（版面の空き判定は箱を「埋まっている」と数えるので、中身の空きを別に測る）
      {
        const ttlB = (s.querySelector("h1, .title, .ttl") || s).getBoundingClientRect().bottom;
        const area = (fr ? fr.top : sr.bottom) - ttlB;
        for (const b of s.querySelectorAll("div, aside, li")) {
          if (b === s || b.closest("table, svg, .foot, .footer, footer, .src, .bar, .legend")) continue;
          const st = getComputedStyle(b);
          // 縦の線で区切った列（ロードマップの段など）: 左右どちらかの線だけを持ち、同じ種類の列が2本以上並ぶもの
          const sideOnly = (x) => { const t = getComputedStyle(x); const lr = ["Left", "Right"].some((k) => parseFloat(t[`border${k}Width`]) >= 1 && t[`border${k}Style`] !== "none"); const tb2 = ["Top", "Bottom"].some((k) => parseFloat(t[`border${k}Width`]) >= 1 && t[`border${k}Style`] !== "none"); return lr && !tb2 && !isFilled(t); };
          const sideRuled = !isBoxed(st) && sideOnly(b) && [...(b.parentElement?.children || [])].filter((x) => x.className === b.className).length >= 2;
          if (!isBoxed(st) && !sideRuled) continue;
          const br = b.getBoundingClientRect();
          if (br.height < area * 0.3 || br.width < sr.width * (isBoxed(st) ? 0.15 : 0.1)) continue;
          const padT = parseFloat(st.paddingTop) || 0, padB = parseFloat(st.paddingBottom) || 0;
          let top = Infinity, bot = -Infinity;
          const spans = [];
          for (const el of [b, ...b.querySelectorAll("*")]) {
            const rs = /^(svg|img|canvas|video)$/i.test(el.tagName) ? [el.getBoundingClientRect()]
              : el !== b && isBoxed(getComputedStyle(el)) ? [el.getBoundingClientRect()] : ownTextRects(el);
            for (const r of rs) { if (r.height > 0) { top = Math.min(top, r.top); bot = Math.max(bot, r.bottom); spans.push([r.top, r.bottom]); } }
          }
          const inner = br.height - padT - padB;
          if (!(bot > top) || inner <= 0) continue;
          // 箱の中の真ん中の空き（上と下に中身を離して置き、間が空いている）
          spans.sort((x, y) => x[0] - y[0]);
          let reach = -Infinity, midGap = 0;
          for (const [t2, b2] of spans) { if (reach > -Infinity) midGap = Math.max(midGap, t2 - reach); reach = Math.max(reach, b2); }
          if (midGap / inner > 0.3) {
            (midGap / inner > 0.45 ? out : warnOut).push(`p${n}: 箱・列の中の真ん中が ${Math.round(midGap / inner * 100)}% 空いている「${(b.textContent || "").trim().slice(0, 16)}」（§4.12・§4.54: 中身を上と下に離して置かない。箱を中身の高さにして詰める。margin-top:auto・height:100%・space-between で離さない）`);
            break;
          }
          const emptyIn = 1 - (bot - top) / inner;
          // 高さを揃えた並列の箱（§4.51）は、短い側が空くのが当然。並びの中でいちばん中身の多い箱も空いているときだけ拾う
          const sibs = [...(b.parentElement?.children || [])].filter((x) => x !== b && x.tagName === b.tagName && x.className === b.className);
          const fullest = sibs.reduce((m, x) => {
            const xr = x.getBoundingClientRect();
            let t2 = Infinity, b2 = -Infinity;
            for (const el of [x, ...x.querySelectorAll("*")]) for (const r of ownTextRects(el)) { t2 = Math.min(t2, r.top); b2 = Math.max(b2, r.bottom); }
            return b2 > t2 ? Math.min(m, 1 - (b2 - t2) / Math.max(1, xr.height)) : m;
          }, emptyIn);
          if (emptyIn > 0.5 && fullest > 0.5) {
            warnOut.push(isBoxed(st)
              ? `p${n}: 箱の中が ${Math.round(emptyIn * 100)}% 空いている「${(b.textContent || "").trim().slice(0, 16)}」（§4.54: 箱で囲っても空きは空き。箱を中身の高さにする・中身を足す・文字を一段大きくする）`
              : `p${n}: 縦の線で区切った列が伸び、中が ${Math.round(emptyIn * 100)}% 空いている「${(b.textContent || "").trim().slice(0, 16)}」（§4.12: 列は中身の高さにする。height:100%・stretch で伸ばさない）`);
            break;
          }
        }
      }
      // 18. 本文の文字の大きさの種類と、文中の太字の数
      {
        const sz = new Map();
        let bold = 0;
        for (const el of s.querySelectorAll("p, li, td, span, b, strong")) {
          if (el.closest("h1, h2, h3, h4, .title, .ttl, th, .foot, .footer, footer, .src, .bar, .kicker, .legend, svg")) continue;
          const own = ownTextRects(el);
          if (!own.length) continue;
          const txt = [...el.childNodes].filter((x) => x.nodeType === 3).map((x) => x.textContent).join("").trim();
          const st = getComputedStyle(el);
          const pst0 = el.parentElement ? getComputedStyle(el.parentElement) : null;
          // 前後どちらにも文がある太字だけを数える（行頭のラベル・行末のページ参照は数えない）
          const textAt = (nd) => nd && nd.nodeType === 3 && nd.textContent.trim();
          const mid = textAt(el.previousSibling) && textAt(el.nextSibling);
          if (parseInt(st.fontWeight) >= 600 && pst0 && parseInt(pst0.fontWeight) < 600 && /^(B|STRONG|SPAN)$/.test(el.tagName) && mid) bold++;
          if (txt.length < 6) continue;
          // 同じ作り（要素名＋クラス＋親のクラス）ごとに、実際の大きさを集める
          const role = el.tagName + "." + [...el.classList].sort().join(".") + "<" + (el.parentElement ? [...el.parentElement.classList].sort().join(".") : "");
          const k = Math.round(effSize(el) * 2) / 2;
          if (!sz.has(role)) sz.set(role, new Set());
          sz.get(role).add(k);
        }
        const mixed = [...sz.entries()].filter(([, v]) => v.size > 1);
        if (mixed.length) {
          const [role, v] = mixed[0];
          warnOut.push(`p${n}: 同じ作りの本文の文字が違う大きさで描かれている（${role.split("<")[0].toLowerCase()}：${[...v].sort((a, b) => a - b).join("・")}px）（§4.19: 同じ役割の文字は同じ大きさに）`);
        }
        if (bold >= 3) warnOut.push(`p${n}: 文の途中の太字が ${bold} か所（§5.5: 強調は目を向けたい1か所だけ。意味のない太字を外す）`);
      }
      // 19. 棒グラフ（塗りの箱が3本以上、下端を揃えて並ぶもの）の軸の線と項目名、色
      {
        const cand = [];
        for (const el of s.querySelectorAll("div, span, i")) {
          if (el.closest("table, .foot, .footer, footer, .legend")) continue;
          if ((el.textContent || "").trim()) continue;
          const st = getComputedStyle(el);
          if (!isFilled(st)) continue;
          const r = el.getBoundingClientRect();
          if (r.width < 8 || r.width > sr.width * 0.25 || r.height < 4) continue;
          cand.push({ el, r, bg: st.backgroundColor });
        }
        // 同じ親の下に並ぶ箱を1つの棒の並びとみなす。親で棒の並びにならなかった箱だけを祖父でまとめる
        // （棒を1本ずつ列で包む作り。下端がずれていても拾う）。2カラムに並んだ別々の棒グラフを1つに合流させず、それぞれ検査する
        const used = new Set();
        const barGroups = [];
        for (const up of [(e) => e.parentElement, (e) => e.parentElement?.parentElement]) {
          const groups = new Map();
          for (const c of cand) {
            if (used.has(c)) continue;
            const k = up(c.el);
            if (!k) continue;
            if (!groups.has(k)) groups.set(k, []);
            groups.get(k).push(c);
          }
          for (const g of groups.values()) {
            if (g.length < 3) continue;
            const ws = g.map((c) => c.r.width);
            if (Math.max(...ws) / Math.min(...ws) > 1.3) continue;
            const hs = new Set(g.map((c) => Math.round(c.r.height)));
            if (hs.size < 2) continue; // 高さが全部同じなら棒グラフではない（チップ・目盛りの並び）
            // 横に並んでいるもの（縦の範囲が重なる）だけ
            if (Math.max(...g.map((c) => c.r.top)) > Math.min(...g.map((c) => c.r.bottom))) continue;
            for (const c of g) used.add(c);
            barGroups.push(g);
          }
        }
        for (const g of barGroups) {
          const L = Math.min(...g.map((c) => c.r.left)), R = Math.max(...g.map((c) => c.r.right));
          const bottom = Math.max(...g.map((c) => c.r.bottom)), low = Math.min(...g.map((c) => c.r.bottom));
          if (bottom - low > 3) warnOut.push(`p${n}: 棒の下端が ${Math.round(bottom - low)}px ずれている（項目名の行数で棒が押し上げられている。棒は同じ軸の線に乗せる — §5.26）`);
          // 棒の下端より下にある、棒の並びの幅いっぱいの横線（軸の線）。軸とみなすのは、棒を包む器の下罫か、
          // 文字の無い細い線の要素だけ（棒の下に置いた下罫つきのカードやラッパーを軸と取り違えない）
          let axisY = null;
          for (const el of s.querySelectorAll("*")) {
            const st = getComputedStyle(el), r = el.getBoundingClientRect();
            if (r.left > L + 2 || r.right < R - 2) continue;
            const wrapsBars = g.every((c) => el.contains(c.el));
            const thinLine = r.height <= 6 && !(el.textContent || "").trim();
            if (!wrapsBars && !thinLine) continue;
            if (parseFloat(st.borderBottomWidth) >= 1 && st.borderBottomStyle !== "none" && r.bottom >= bottom - 2 && r.bottom <= bottom + 80) axisY = axisY === null ? r.bottom : Math.min(axisY, r.bottom);
          }
          if (axisY !== null && axisY - bottom > 4) {
            const between = els.some((el) => ownTextRects(el).some((t) => t.left >= L - 4 && t.right <= R + 4 && t.top >= bottom - 2 && t.bottom <= axisY + 2));
            if (between) warnOut.push(`p${n}: 棒グラフの項目名が軸の線より上にある（棒が線から浮いている。棒を軸の線に乗せ、項目名は線の下に出す — §5.26）`);
          }
          // 目を向けたい1本だけ色を変えるのは §5.26/§5.5 の推奨どおりなので、3色以上か、主色と違う棒が2本以上のときだけ
          const colors = new Set(g.map((c) => c.bg));
          const tally = new Map();
          for (const c of g) tally.set(c.bg, (tally.get(c.bg) || 0) + 1);
          const offMain = g.length - Math.max(...tally.values());
          const legend = s.querySelector('[class*="legend"]') || /凡例/.test(s.textContent || "");
          if ((colors.size >= 3 || offMain >= 2) && !legend) warnOut.push(`p${n}: 棒の色が ${colors.size} 色に分かれているのに凡例が無い（色を変えるのは目を向けたい1本だけにし、凡例か注記で理由を書く — §5.5）`);
        }
      }
      // 20. 表の行の間延び（13 の引き伸ばしとは別に、セルの上下の余白と行間が大きすぎる行を拾う）
      for (const t of s.querySelectorAll("table")) {
        const ratios = [];
        for (const tr of t.rows) {
          if ([...tr.cells].every((c) => c.tagName === "TH")) continue;
          let top = Infinity, bot = -Infinity, fs = 0;
          for (const c of tr.cells) for (const el of [c, ...c.querySelectorAll("*")]) for (const x of ownTextRects(el)) { top = Math.min(top, x.top); bot = Math.max(bot, x.bottom); fs = Math.max(fs, parseFloat(getComputedStyle(el).fontSize)); }
          if (bot > top && fs) ratios.push((tr.getBoundingClientRect().height - (bot - top)) / fs);
        }
        if (ratios.length >= 2) {
          const med = ratios.sort((a, b) => a - b)[Math.floor(ratios.length / 2)];
          if (med > 2.2) { warnOut.push(`p${n}: 表の行の上下が間延びしている（行の余白が文字の ${med.toFixed(1)} 倍。セルの上下の余白と行間を詰める — §4.12）`); break; }
        }
      }
      // 21. 見出しが、その下の本文より小さい（列の見出し・軸の見出し・表の見出し行）
      {
        const heads = [...s.querySelectorAll("th, .colh, .axh, .section-label, h2, h3, h4")].filter((h) => !h.closest("tbody tr:not(:first-child)") && (h.textContent || "").trim().length <= 40);
        for (const h of heads) {
          const hs = effSize(h);
          if (!hs) continue;
          let below = [];
          if (h.tagName === "TH") {
            const t = h.closest("table");
            below = [...t.querySelectorAll("td")];
          } else {
            let nx = h.nextElementSibling;
            while (nx && !(nx.textContent || "").trim()) nx = nx.nextElementSibling;
            if (nx) below = [nx, ...nx.querySelectorAll("*")];
          }
          // 大きく見せる数字（「72%」「約1,500人月」など）は見出しと比べない
          const isNum = (el) => /^[\s\d.,%％+\-−〜~約万億千円人件倍月年社pt]+$/.test([...el.childNodes].filter((x) => x.nodeType === 3).map((x) => x.textContent).join("").trim());
          const sizes = below.filter((el) => ownTextRects(el).length && !isNum(el) && !el.closest(".src, .source, .legend, .stack-legend") && el.tagName !== "TH").map(effSize).filter((v) => v > 0);
          if (!sizes.length) continue;
          const big = Math.max(...sizes);
          if (hs < big * 0.97) {
            warnOut.push(`p${n}: 見出し「${(h.textContent || "").trim().slice(0, 16)}」が、その下の文字より小さい（${Math.round(hs)}px < ${Math.round(big)}px。見出しは本文・行見出しより大きくする — §6・§4.21）`);
            break;
          }
        }
      }
      // 22. 文字と横罫の重なり（文字の行の矩形を、ほかの要素の上罫・下罫が横切る）
      {
        const rules = [];
        for (const el of s.querySelectorAll("*")) {
          if (el.closest(".foot, .footer, footer")) continue;
          const st = getComputedStyle(el), r = el.getBoundingClientRect();
          if (r.width < 40) continue;
          if (parseFloat(st.borderTopWidth) >= 1 && st.borderTopStyle !== "none") rules.push({ el, y: r.top, l: r.left, r: r.right });
          if (parseFloat(st.borderBottomWidth) >= 1 && st.borderBottomStyle !== "none") rules.push({ el, y: r.bottom, l: r.left, r: r.right });
        }
        let hit = 0;
        for (const el of els) {
          if (hit || el.closest(".foot, .footer, footer, svg")) continue;
          // 2行以上にまたがるセルの文字は、同じ表の行の区切り罫が横切って見えるのが正しい形なので比べない
          const span = el.closest("td, th");
          const spanTable = span && span.rowSpan > 1 ? span.closest("table") : null;
          for (const t of ownTextRects(el)) {
            const ln = rules.find((q) => !q.el.contains(el) && !el.contains(q.el) && !(spanTable && q.el.closest("table") === spanTable) && q.y > t.top + 3 && q.y < t.bottom - 3 && Math.min(q.r, t.right) - Math.max(q.l, t.left) > 4);
            if (ln) {
              hit = 1;
              warnOut.push(`p${n}: 文字「${(el.textContent || "").trim().slice(0, 14)}」が罫線に重なっている（数字・ラベルを線から離す。棒グラフなら最も高い棒の上に数字の場所を取る）`);
              break;
            }
          }
        }
      }
      // 23. 同じ作りの箱の左端のずれ（揃うはずの位置から 3〜60px ずれている）
      {
        const groups = {};
        for (const el of s.querySelectorAll("div, li, span")) {
          if (el.closest("table, svg, .foot, .footer, footer, .src, .bar, .hdr, h1, .title")) continue;
          const st = getComputedStyle(el);
          if (!isBoxed(st) || !(el.textContent || "").trim()) continue;
          const r = el.getBoundingClientRect();
          if (r.width < 40 || r.height < 14) continue;
          const key = el.tagName + "." + [...el.classList].sort().join(".");
          (groups[key] ||= []).push(r.left);
        }
        for (const [key, ls] of Object.entries(groups)) {
          if (ls.length < 3) continue;
          const v = [...ls].sort((a, b) => a - b);
          // 互いに60px以内に集まる左端の塊ごとに、ずれ幅を測る
          let i = 0, found = 0;
          while (i < v.length) {
            let j = i;
            while (j + 1 < v.length && v[j + 1] - v[i] <= 60) j++;
            if (j - i >= 2 && v[j] - v[i] > 3) { found = Math.round(v[j] - v[i]); break; }
            i = j + 1;
          }
          if (found) {
            warnOut.push(`p${n}: 同じ作りの箱（${key.split(".").slice(1).join(".") || key}）の左端が ${found}px ずれている（段・列の始まる位置を揃える。箱の幅を中身で変えない — §4.51）`);
            break;
          }
        }
      }
      // 24. 行のリスト（罫線で区切った行の並び）の間延びと、左右2列の行の位置のずれ
      {
        const lists = [];
        for (const g of s.querySelectorAll("div, ul")) {
          if (g.closest("table, svg, .foot, .footer, footer")) continue;
          const kids = [...g.children].filter((c) => (c.textContent || "").trim());
          if (kids.length < 3) continue;
          const ruled = kids.filter((c) => { const st = getComputedStyle(c); return (parseFloat(st.borderTopWidth) >= 1 && st.borderTopStyle !== "none") || (parseFloat(st.borderBottomWidth) >= 1 && st.borderBottomStyle !== "none"); });
          if (ruled.length < kids.length - 1) continue;
          const rs = kids.map((c) => c.getBoundingClientRect());
          if (rs.some((r, k) => k && r.top < rs[k - 1].bottom - 2)) continue; // 縦に並んだ行だけ
          lists.push({ g, kids, rs });
        }
        let slackHit = 0;
        for (const { kids, rs } of lists) {
          const ratios = kids.map((c, k) => {
            let top = Infinity, bot = -Infinity, fs = 0;
            for (const el of [c, ...c.querySelectorAll("*")]) for (const x of ownTextRects(el)) { top = Math.min(top, x.top); bot = Math.max(bot, x.bottom); fs = Math.max(fs, parseFloat(getComputedStyle(el).fontSize)); }
            return bot > top && fs ? (rs[k].height - (bot - top)) / fs : 0;
          }).filter((x) => x > 0).sort((a, b) => a - b);
          const med = ratios[Math.floor(ratios.length / 2)];
          if (!slackHit && med > 2.2) { slackHit = 1; warnOut.push(`p${n}: 行のリストの上下が間延びしている（行の余白が文字の ${med.toFixed(1)} 倍。行を引き伸ばさず、余白と行間を詰める — §4.12）`); }
        }
        for (let a = 0; a < lists.length; a++) for (let b = a + 1; b < lists.length; b++) {
          const A = lists[a], B = lists[b];
          if (A.kids.length !== B.kids.length || A.g.contains(B.g) || B.g.contains(A.g)) continue;
          const side = A.rs[0].right <= B.rs[0].left + 1 || B.rs[0].right <= A.rs[0].left + 1;
          if (!side || Math.abs(A.rs[0].top - B.rs[0].top) > 40) continue;
          const d = Math.max(...A.rs.map((r, k) => Math.abs(r.top - B.rs[k].top)));
          if (d > 4) { warnOut.push(`p${n}: 左右の列の行の位置が ${Math.round(d)}px ずれている（対応する行は同じ高さに揃える。行見出しが折れて高さが変わっていないか確かめる — §4.51）`); a = lists.length; break; }
        }
      }
      // 25. 並べた見出し・大きな数字の折れの不揃い（同じ作りが横に並ぶ見出し、または同じ列の大きな数字）
      {
        const lineCount = (el) => {
          const tops = new Set();
          for (const r of ownTextRects(el)) tops.add(Math.round(r.top / 4));
          return tops.size;
        };
        const groups = new Map();
        for (const el of s.querySelectorAll("h2, h3, h4, div, p, td, span")) {
          if (el.closest(".foot, .footer, footer, .src, .bar, .hdr, h1, .title, svg")) continue;
          if (el.querySelector("br")) continue; // 意味の切れ目で改行したものは対象外
          const own = ownTextRects(el);
          if (!own.length) continue;
          const st = getComputedStyle(el);
          const fs = parseFloat(st.fontSize);
          const isCell = el.tagName === "TD" || el.tagName === "TH";
          if (isCell && fs < 20) continue; // 表は大きな数字の列だけ
          if (!isCell && !(parseInt(st.fontWeight) >= 600 && fs >= 15)) continue; // 見出し（太字）だけ
          const txt = [...el.childNodes].filter((x) => x.nodeType === 3).map((x) => x.textContent).join("").trim();
          if (txt.length > 40) continue;
          const key = el.tagName + "." + [...el.classList].sort().join(".") + "|" + Math.round(fs);
          const anc = isCell ? el.closest("table") : el.parentElement?.parentElement;
          if (!anc) continue;
          if (!groups.has(anc)) groups.set(anc, {});
          (groups.get(anc)[key] ||= []).push({ el, n: lineCount(el), txt });
        }
        let hit = 0;
        for (const g of groups.values()) {
          if (hit) break;
          for (const items of Object.values(g)) {
            if (items.length < 3) continue;
            const one = items.filter((x) => x.n === 1), multi = items.filter((x) => x.n >= 2);
            if (one.length && multi.length) {
              hit = 1;
              warnOut.push(`p${n}: 並べた見出し・数字のうち「${multi[0].txt.slice(0, 14)}」だけが ${multi[0].n} 行に折れている（ほかは1行。見出しを短くする・列を広げる・文字を一段小さくして全部を1行に揃える — §4.51）`);
              break;
            }
          }
        }
      }
      // 26. 列の区切り線・行の軸の縦線が見出しの行まで伸びている（左端の列の右の線も含む）
      for (const t of s.querySelectorAll("table")) {
        const head = t.rows[0];
        if (!head || ![...head.cells].every((c) => c.tagName === "TH")) continue;
        const ruled = [...head.cells].some((c) => { const st = getComputedStyle(c); return parseFloat(st.borderBottomWidth) >= 1 && st.borderBottomStyle !== "none"; });
        if (!ruled) continue;
        const cells = [...head.cells];
        const bad = cells.find((c, k) => {
          const st = getComputedStyle(c);
          const left = k >= 2 && parseFloat(st.borderLeftWidth) >= 1 && st.borderLeftStyle !== "none";
          const right = k < cells.length - 1 && parseFloat(st.borderRightWidth) >= 1 && st.borderRightStyle !== "none";
          return left || right;
        });
        if (bad) { warnOut.push(`p${n}: 表の縦の線が見出しの行まで伸び、見出しの下罫より上に出ている「${(bad.textContent || "").trim().slice(0, 12)}」（行の軸の線・区切り線は本文の行にだけ引く — §6）`); break; }
      }
      // 27. 並べた項目の間を空けて版面を埋める間延び（箇条書き・縦に並べた同じ種類の項目。§4.12）
      {
        // 項目の中身の上下: 文字の行ボックスに加えて、中の塗り・枠のある要素（文字の無いバー、padding 付きのカード）と
        // 画像・図の外接矩形も中身に数える（それらの高さを「余分な空き」に入れない）。項目自身の枠は数えない＝引き伸ばしは引き続き測れる
        const textBox = (el) => {
          let t = Infinity, b = -Infinity;
          const take = (r) => { if (r.width > 0 && r.height > 0) { t = Math.min(t, r.top); b = Math.max(b, r.bottom); } };
          for (const x of [el, ...el.querySelectorAll("*")]) for (const r of ownTextRects(x)) take(r);
          for (const x of el.querySelectorAll("*")) {
            if (x.closest("svg") && x.tagName.toLowerCase() !== "svg") continue;
            if (/^(svg|img|canvas)$/i.test(x.tagName) || isBoxed(getComputedStyle(x))) take(x.getBoundingClientRect());
          }
          return b > t ? { t, b } : null;
        };
        let worst = null;
        for (const box of s.querySelectorAll("ul, ol, div")) {
          if (box.closest("table, svg, .foot, .footer, footer, .src, .bar, .legend, h1, .title, .ttl")) continue;
          if (/tree/.test(box.className) || box.closest("[class*='tree']")) continue; // ツリーは枝の間が子の数に合わせて開くのが自然
          const shown = [...box.children].filter((k) => { const st = getComputedStyle(k); return st.display !== "none" && st.visibility !== "hidden" && st.position !== "absolute"; });
          // 文字の無い子（ラベルの下の塗りのバー等）が挟まる並びは項目の間に中身があるので、項目の並びとして測らない
          if (shown.some((k) => !(k.textContent || "").trim() && k.getBoundingClientRect().height > 1)) continue;
          const kids = shown.filter((k) => (k.textContent || "").trim());
          if (kids.length < 2 || kids.some((k) => k.tagName !== kids[0].tagName || k.className !== kids[0].className)) continue;
          const tb = kids.map(textBox);
          if (tb.some((x) => !x)) continue;
          // 項目の上下の余白・罫線・margin と、並びの gap で決めた間隔を差し引いた「余分な空き」を測る
          const px = (st, k) => parseFloat(st[k]) || 0;
          const rowGap = px(getComputedStyle(box), "rowGap");
          const gaps = [];
          let stacked = true;
          for (let k = 0; k + 1 < tb.length; k++) {
            if (tb[k + 1].t < tb[k].b - 2) { stacked = false; break; }
            const a = getComputedStyle(kids[k]), c = getComputedStyle(kids[k + 1]);
            const fixed = px(a, "paddingBottom") + px(a, "borderBottomWidth") + px(a, "marginBottom")
              + px(c, "marginTop") + px(c, "borderTopWidth") + px(c, "paddingTop") + rowGap;
            gaps.push(tb[k + 1].t - tb[k].b - fixed);
          }
          if (!stacked) continue;
          gaps.sort((a, b) => a - b);
          const med = gaps[Math.floor(gaps.length / 2)];
          const fs = effSize(kids[0]) || 12;
          const ratio = med / fs;
          if (ratio > 1.5 && (!worst || ratio > worst.ratio)) worst = { ratio, el: kids[0] };
        }
        if (worst) {
          const msg = `p${n}: 並べた項目の間が、余白の決まりより文字の約${Math.round(worst.ratio)}倍ぶん余分に空いている「${(worst.el.textContent || "").trim().slice(0, 14)}」（§4.12: 項目の間を広げて版面を埋めない＝間延び。項目は詰めて並べ、空くなら文字を一段大きくする・形を変える・前後のページとまとめる。部品の CSS に height:100%・flex:1・space-around などを足して伸ばさない）`;
          (worst.ratio > 3 ? out : warnOut).push(msg);
        }
      }
      // 11. 片側だけの空き：タイトルの横幅を基準に、本文の文字・図形が占める横の範囲の外側を測る
      const ttl2 = s.querySelector("h1, .title, .ttl");
      if (ttl2) {
        const tr = ttl2.getBoundingClientRect();
        let L = Infinity, R = -Infinity;
        for (const el of s.querySelectorAll("*")) {
          if (el.closest("h1, .title, .ttl, .foot, .footer, footer, .src, .bar, .kicker, .hdr, .rule")) continue;
          const st = getComputedStyle(el);
          if (st.display === "none" || st.visibility === "hidden") continue;
          let r = null;
          if (/^(svg|img|canvas)$/i.test(el.tagName)) r = el.getBoundingClientRect();
          else if ([...el.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim())) r = el.getBoundingClientRect();
          else {
            const bg = st.backgroundColor;
            const filled = bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg);
            const ruled = ["Top", "Right", "Bottom", "Left"].some((k) => parseFloat(st[`border${k}Width`]) > 0 && st[`border${k}Style`] !== "none");
            if (filled || ruled) r = el.getBoundingClientRect();
          }
          if (!r || r.width === 0 || r.height === 0 || el.closest("svg") && el.tagName.toLowerCase() !== "svg") continue;
          L = Math.min(L, r.left); R = Math.max(R, r.right);
        }
        if (R > L && tr.width > 200) {
          const right = (tr.right - R) / tr.width, left = (L - tr.left) / tr.width;
          if (right > 0.25) warnOut.push(`p${n}: 版面の右側 ${Math.round(right * 100)}% が空いている（§4.54: 列の幅を中身に合わせて配り直すか、内容を足す）`);
          else if (left > 0.25) warnOut.push(`p${n}: 版面の左側 ${Math.round(left * 100)}% が空いている（§4.54）`);
        }
      }
      // 12. 塗りのハイライト：表で塗った行（tr・td の塗り）と、文中の mark を数える（セル内の棒・チップの塗りは数えない）
      {
        const painted = (el) => { const bg = getComputedStyle(el).backgroundColor; return bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg); };
        let spots = 0;
        for (const t of s.querySelectorAll("table")) {
          const tbg = getComputedStyle(t).backgroundColor;
          // 1列を通して塗った列のハイライトは1か所と数える（塗った行の数と列の数の少ない方）
          // 3行以上を塗った表は縞・地色とみなして数えない（縞は §6 で別に禁止）
          const rows = new Set(), cols = new Set();
          const trs = [...t.querySelectorAll("tr")].filter((tr) => !(tr.querySelector("th") && !tr.querySelector("td")));
          const paintedTr = trs.filter((tr) => painted(tr) && getComputedStyle(tr).backgroundColor !== tbg);
          if (paintedTr.length <= 2) spots += paintedTr.length;
          trs.forEach((tr, ri) => {
            if (paintedTr.includes(tr)) return;
            for (const td of tr.querySelectorAll("td"))
              if (painted(td) && getComputedStyle(td).backgroundColor !== tbg) { rows.add(ri); cols.add(td.cellIndex); }
          });
          spots += Math.min(rows.size, cols.size);
        }
        for (const el of s.querySelectorAll("mark")) if ((el.textContent || "").trim() && painted(el)) spots++;
        if (spots >= 2) warnOut.push(`p${n}: 塗りで立てた箇所が ${spots} か所ある（§4.57: 1ページ1か所まで。塗りが値を表すヒートマップなら無視してよい）`);
      }
    }
    // 6. タイトルと本文の実際の大きさ（表紙・章扉・裏表紙は対象外）
    if (!std && !s.matches(".cover, .chap, .back")) {
      const ttl = s.querySelector("h1, .title, .ttl");
      sizes.push({ n, title: ttl ? effSize(ttl) : 0, sw: sr.width, body: bodySize(s) });
    }
    // 17. 文字が、それを囲む箱（塗り・四辺の枠・表のセル）の外にはみ出している
    if (!std) {
      let over = 0;
      for (const el of els) {
        if (over >= 3 || el.closest("svg")) continue;
        const rs = ownTextRects(el);
        if (!rs.length) continue;
        let box = el;
        while (box && box !== s && !(box.matches("td, th") || isBoxed(getComputedStyle(box)))) box = box.parentElement;
        if (!box || box === s) continue;
        const bx = box.getBoundingClientRect();
        const outBy = Math.max(...rs.map((r) => Math.max(bx.left - r.left, r.right - bx.right, bx.top - r.top, r.bottom - bx.bottom)));
        if (outBy > 2) {
          over++;
          out.push(`p${n}: 文字が箱の外に ${Math.round(outBy)}px はみ出している「${(el.textContent || "").trim().slice(0, 20)}」（箱を広げる・文字を短くする・改行位置を変える）`);
        }
      }
    }
    for (const el of els) {
      const r = el.getBoundingClientRect();
      if (r.height === 0 || r.width === 0) continue;
      // 葉要素だけ見る（コンテナの巨大rectでの誤検出を避ける）
      if (el.children.length > 0 && el.tagName !== "IMG") continue;
      if (fr && r.bottom > fr.top + 1 && r.top < fr.bottom - 1) { // フッターの上端をまたぐものに加え、フッターの中に入り込んだもの（押し出された出典行など）も
        out.push(`p${n}: フッターと本文が重なる: <${el.tagName.toLowerCase()}> 「${(el.textContent || "").trim().slice(0, 30)}」`);
      }
      if (r.right > sr.right + 1) {
        out.push(`p${n}: 右端はみ出し ${Math.round(r.right - sr.right)}px: <${el.tagName.toLowerCase()}> 「${(el.textContent || "").trim().slice(0, 30)}」`);
      }
      if (r.bottom > sr.bottom + 1) {
        out.push(`p${n}: 下端はみ出し ${Math.round(r.bottom - sr.bottom)}px: <${el.tagName.toLowerCase()}> 「${(el.textContent || "").trim().slice(0, 30)}」`);
      }
    }
  });
  // 6. ページ間の大きさの揃い。多数派（中央値）から外れたページを挙げる
  const median = (a) => { const v = a.filter((x) => x > 0).sort((p, q) => p - q); return v.length ? v[Math.floor(v.length / 2)] : 0; };
  const mt = median(sizes.map((x) => x.title)), mb = median(sizes.map((x) => x.body));
  for (const x of sizes) {
    if (mt && x.title && Math.abs(x.title / mt - 1) > 0.04)
      out.push(`p${x.n}: タイトルの実際の大きさが他のページの ${Math.round((x.title / mt) * 100)}%（パーツ集の混在で縮小がかかっていない可能性。§4・追加パーツ集は .slide の zoom ごと持ち込む）`);
    // §2.1: タイトルは 22pt（版面の幅 338.67mm に対して 7.76mm）。空きを埋めるために大きくしない・1行に収めるために小さくしない
    const tr = x.title && x.sw ? x.title / x.sw / (22 * 25.4 / 72 / 338.67) : 0;
    if (tr && Math.abs(tr - 1) > 0.1)
      out.push(`p${x.n}: タイトルの大きさが既定の22ptの ${Math.round(tr * 100)}%（§2.1: タイトルは22pt。空きを埋めるために大きくしない・1行に収めるために小さくしない。長ければ2行にする）`);
    if (mb && x.body && Math.abs(x.body / mb - 1) > 0.15)
      warnOut.push(`p${x.n}: 本文の実際の大きさが他のページの ${Math.round((x.body / mb) * 100)}%（揃える。強調なら、強調する理由を qa.md に書く）`);
  }
  // 9. 同じ役割の罫線が、ページによって違う太さで描かれている
  for (const [key, m] of Object.entries(borders)) {
    if (m.size > 1) warnOut.push(`同じ役割の罫線の太さが揃っていない：${key} が ${[...m.keys()].sort((a, b) => a - b).join("px・")}px（§5.4: 同じ役割の線は同じ太さにする）`);
  }
  return { issues: [...new Set(out)], warns: [...new Set(warnOut)] };
});

// 28. PDF にしたときのページ数がスライドの枚数と合うか（1枚が用紙より高いと、PDF で2ページに割れる）
try {
  const nSlides = await page.evaluate(() => document.querySelectorAll("section.s, section.slide, .slide").length);
  const pdf = await page.pdf({ preferCSSPageSize: true, printBackground: true });
  const nPages = (pdf.toString("latin1").match(/\/Type\s*\/Page(?!s)/g) || []).length;
  if (nSlides && nPages && nPages !== nSlides)
    issues.unshift(`PDF が ${nPages} ページになる（スライドは ${nSlides} 枚）。用紙より高いスライドがあり、PDF で途中から次のページに割れている（はみ出した要素を版面に収める）`);
} catch (e) { console.error("PDF ページ数の照合を飛ばした: " + e.message); }
await browser.close();
// 既定では各20件まで表示する。--all（check_all.py が付ける）なら全件を出す
const cap = process.argv.includes("--all") ? Infinity : 20;
for (const m of warns.slice(0, cap)) console.log("WARN  " + m);
if (warns.length > cap) console.log(`（WARN はほか ${warns.length - cap} 件。全件は --all）`);
if (issues.length) {
  for (const m of issues.slice(0, cap)) console.log("FAIL  " + m);
  if (issues.length > cap) console.log(`（FAIL はほか ${issues.length - cap} 件。全件は --all）`);
  console.log(`\n${issues.length} layout FAIL`);
  process.exit(1);
}
console.log("layout OK（フッター重なり・はみ出し・下半分の空きなし）");
