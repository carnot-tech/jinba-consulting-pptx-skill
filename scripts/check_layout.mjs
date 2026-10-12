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
// 正本から差し込んだ定型ページ（section に .std。§4.99）は、はみ出し以外の検査を飛ばす
// 使い方: node scripts/check_layout.mjs deck.html   （playwright 必須: リポ直下で `npm run setup`。PLAYWRIGHT_MODULE_DIR でも解決可）
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

const file = process.argv[2];
if (!file) { console.error("usage: node check_layout.mjs deck.html"); process.exit(2); }

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
  const slides = [...document.querySelectorAll("section.s, section.slide, .slide")];
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
      let contentBottom = -Infinity, contentTop = Infinity;
      for (const el of els) {
        if (el === ttl || (ttl && ttl.contains(el))) continue;
        if (el.closest(".src, .bar")) continue; // 出典行・上部バーは本文に数えない
        if (el.children.length > 0 && el.tagName !== "IMG" && el.tagName !== "svg") continue;
        const r = el.getBoundingClientRect();
        if (r.height === 0 || r.width === 0) continue;
        contentBottom = Math.max(contentBottom, r.bottom);
        contentTop = Math.min(contentTop, r.top);
      }
      // 図形（svg・画像・塗りや罫線のある箱）も本文に数える
      const isShape = (el) => {
        if (/^(svg|img|canvas)$/i.test(el.tagName)) return true;
        const st = getComputedStyle(el);
        const bg = st.backgroundColor;
        const filled = bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg);
        const bordered = ["Top", "Right", "Bottom", "Left"].some((k) => parseFloat(st[`border${k}Width`]) > 0 && st[`border${k}Style`] !== "none");
        return filled || bordered || st.clipPath !== "none";
      };
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
      const area = bottom - top;
      const span = contentBottom > contentTop ? contentBottom - contentTop : 0;
      const empty = area > 0 ? 1 - span / area : 0;
      if (empty > 0.4) {
        out.push(`p${n}: 版面の ${Math.round(empty * 100)}% が空いている（40%超。表を割る・図を足す・2枚を1枚に統合する）`);
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
      const leaves = els.filter((el) => el.children.length === 0 && (el.textContent || "").trim().length > 0 && !el.closest("svg"))
        .map((el) => ({ el, r: el.getBoundingClientRect() })).filter((x) => x.r.width > 2 && x.r.height > 2);
      let hit = 0;
      for (let a = 0; a < leaves.length && hit < 3; a++) for (let b = a + 1; b < leaves.length && hit < 3; b++) {
        const A = leaves[a], B = leaves[b];
        if (A.el.contains(B.el) || B.el.contains(A.el)) continue;
        const ix = Math.min(A.r.right, B.r.right) - Math.max(A.r.left, B.r.left);
        const iy = Math.min(A.r.bottom, B.r.bottom) - Math.max(A.r.top, B.r.top);
        if (ix <= 0 || iy <= 0) continue;
        const small = Math.min(A.r.width * A.r.height, B.r.width * B.r.height);
        if (ix * iy > small * 0.2) {
          hit++;
          warnOut.push(`p${n}: 文字が重なっている「${(A.el.textContent || "").trim().slice(0, 14)}」と「${(B.el.textContent || "").trim().slice(0, 14)}」（意図した重なりでも読めるかを確かめる）`);
        }
      }
    }
    // 9. 罫線の太さを役割（要素名＋クラス＋辺）ごとに集める
    for (const el of std ? [] : s.querySelectorAll("*")) {
      const st = getComputedStyle(el);
      for (const side of ["Top", "Bottom", "Left", "Right"]) {
        const w = parseFloat(st[`border${side}Width`]);
        if (!(w > 0) || st[`border${side}Style`] === "none") continue;
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
            warnOut.push(`p${n}: 並べた要素（${side.length}個）の${what.join("・")}が揃っていない（§4.51: 対比の列・同格の箱は 1fr で同じ幅・高さに組む。意図した差なら無視してよい）`);
            break;
          }
        }
      }
      // 11. 片側だけの空き：タイトルの横幅を基準に、本文の文字・図形が占める横の範囲の外側を測る
      const ttl2 = s.querySelector("h1, .title, .ttl");
      if (ttl2) {
        const tr = ttl2.getBoundingClientRect();
        let L = Infinity, R = -Infinity;
        for (const el of s.querySelectorAll("*")) {
          if (el.closest("h1, .title, .ttl, .foot, .footer, footer, .src, .bar, .kicker")) continue;
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
      const body = [...s.querySelectorAll("li, td, p")].filter((el) => (el.textContent || "").trim().length > 8 && !el.closest(".src, .foot, .footer"));
      const bs = body.map(effSize).filter((v) => v > 0).sort((a, b) => a - b);
      sizes.push({ n, title: ttl ? effSize(ttl) : 0, body: bs.length ? bs[Math.floor(bs.length / 2)] : 0 });
    }
    for (const el of els) {
      const r = el.getBoundingClientRect();
      if (r.height === 0 || r.width === 0) continue;
      // 葉要素だけ見る（コンテナの巨大rectでの誤検出を避ける）
      if (el.children.length > 0 && el.tagName !== "IMG") continue;
      if (fr && r.bottom > fr.top + 1 && r.top < fr.top) {
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
    if (mb && x.body && Math.abs(x.body / mb - 1) > 0.15)
      warnOut.push(`p${x.n}: 本文の実際の大きさが他のページの ${Math.round((x.body / mb) * 100)}%（意図した強調でなければ揃える）`);
  }
  // 9. 同じ役割の罫線が、ページによって違う太さで描かれている
  for (const [key, m] of Object.entries(borders)) {
    if (m.size > 1) warnOut.push(`同じ役割の罫線の太さが揃っていない：${key} が ${[...m.keys()].sort((a, b) => a - b).join("px・")}px（§5.4: 同じ役割の線は同じ太さにする）`);
  }
  return { issues: [...new Set(out)], warns: [...new Set(warnOut)] };
});

await browser.close();
for (const m of warns.slice(0, 20)) console.log("WARN  " + m);
if (issues.length) {
  for (const m of issues.slice(0, 20)) console.log("FAIL  " + m);
  console.log(`\n${issues.length} layout FAIL`);
  process.exit(1);
}
console.log("layout OK（フッター重なり・はみ出し・下半分の空きなし）");
