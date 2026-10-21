// Chrome headless を DevTools Protocol で直接操作する最小ヘルパー（追加依存なし・Node 22+ の標準 WebSocket を使う）。
// measure_deck.mjs / html_dump.mjs から使う。
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, existsSync, readdirSync, statSync, accessSync, constants } from "node:fs";
import { tmpdir, homedir } from "node:os";
import { join, resolve, delimiter } from "node:path";
import { pathToFileURL } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

// ブラウザの探し方は scripts/find_browser.py と同じ: CHROME_PATH → Playwright の headless shell → Chrome 本体・Chromium
export function findBrowser() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, join(homedir(), "Library", "Caches", "ms-playwright"),
    join(homedir(), ".cache", "ms-playwright"), process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, "ms-playwright")].filter((x) => x && x !== "0");
  const shells = [];
  for (const r of roots) {
    let dirs = [];
    try { dirs = readdirSync(r).filter((d) => d.startsWith("chromium_headless_shell-")); } catch { continue; }
    for (const d of dirs) {
      let subs = [];
      try { subs = readdirSync(join(r, d)); } catch { continue; }
      for (const sub of subs) for (const exe of ["chrome-headless-shell", "chrome-headless-shell.exe", "headless_shell"]) {
        const p = join(r, d, sub, exe);
        if (existsSync(p)) shells.push({ p, v: Number(d.split("-")[1]) || 0 });
      }
    }
  }
  if (shells.length) return shells.sort((a, b) => b.v - a.v)[0].p;
  // find_browser.py の CHROME_CANDIDATES と同じ順。絶対パスはそのまま、名前だけのものは PATH から探す（shutil.which 相当）
  for (const c of ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "C:/Program Files/Google/Chrome/Application/chrome.exe", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    if (existsSync(c)) return c;
    const w = which(c);
    if (w) return w;
  }
  return undefined;
}

function which(name) {
  if (name.includes("/") || name.includes("\\")) return null;
  const exts = process.platform === "win32" ? (process.env.PATHEXT || ".EXE").split(";") : [""];
  for (const dir of (process.env.PATH || "").split(delimiter)) {
    if (!dir) continue;
    for (const ext of exts) {
      const p = join(dir, name + ext);
      try { if (statSync(p).isFile()) { accessSync(p, constants.X_OK); return p; } } catch {}
    }
  }
  return null;
}

export async function openPage(file, { width = 1400, height = 900, scale = 1, media = "print" } = {}) {
  const CHROME = findBrowser();
  if (!CHROME) throw new Error("ブラウザが見つからない（`npm run setup` で headless shell を入れるか、CHROME_PATH で指定する）");

  const userDataDir = mkdtempSync(join(tmpdir(), "chr-deck-"));
  const port = 9222 + Math.floor(Math.random() * 1000);
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    `--remote-debugging-port=${port}`, `--user-data-dir=${userDataDir}`, "about:blank",
  ], { stdio: ["ignore", "ignore", "ignore"] });

  const close = async () => {
    try { ws?.close(); } catch {}
    chrome.kill();
    await delay(300);
    try { rmSync(userDataDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch {}
  };

  let endpoint, ws;
  for (let i = 0; i < 80 && !endpoint; i++) {
    await delay(100);
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (r.ok) endpoint = (await r.json()).webSocketDebuggerUrl;
    } catch {}
  }
  if (!endpoint) { await close(); throw new Error("Chrome devtools endpoint not ready"); }

  ws = new WebSocket(endpoint);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0, sessionId;
  const inflight = new Map(), events = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && inflight.has(msg.id)) {
      const { resolve, reject } = inflight.get(msg.id);
      inflight.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    } else if (msg.method) events.push(msg);
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const _id = ++id;
    inflight.set(_id, { resolve, reject });
    ws.send(JSON.stringify({ id: _id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });

  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  ({ sessionId } = await send("Target.attachToTarget", { targetId, flatten: true }));
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile: false });
  // 印刷レイアウトで扱う（画面用のビューポート追従スケーラーの影響を受けない）
  await send("Emulation.setEmulatedMedia", { media });
  await send("Page.navigate", { url: pathToFileURL(resolve(file)).href });
  for (let i = 0; i < 100 && !events.some((e) => e.method === "Page.loadEventFired"); i++) await delay(100);
  await delay(1200); // フォント・画像

  const evaluate = async (fnOrExpr, arg) => {
    const expression = typeof fnOrExpr === "function"
      ? `(${fnOrExpr.toString()})(${JSON.stringify(arg ?? null)})` : fnOrExpr;
    const { result, exceptionDetails } = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (exceptionDetails) throw new Error(JSON.stringify(exceptionDetails).slice(0, 500));
    return result.value;
  };
  return { send, evaluate, close };
}
