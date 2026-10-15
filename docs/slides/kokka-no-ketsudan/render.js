#!/usr/bin/env node
// Render static cards (PNG) and the animation (MP4) from index.html.
//   node render.js cards [--fmt story]
//   node render.js video [--fmt story] [--fps 30] [--from 0 --to 10]
// Requires: playwright (Chromium) + ffmpeg on PATH.
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
let playwright;
try { playwright = require("playwright"); } catch { playwright = require(path.join(path.dirname(process.execPath), "../lib/node_modules/playwright")); }

const args = process.argv.slice(2);
const mode = args[0] || "cards";
const opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; };
const fmt = opt("fmt", "feed");
const fps = parseInt(opt("fps", "30"), 10);
const W = 1080, H = fmt === "story" ? 1920 : 1350;
const out = path.join(__dirname, "renders");
fs.mkdirSync(out, { recursive: true });
const url = q => "file://" + path.join(__dirname, "index.html") + "?" + q + (fmt === "story" ? "&fmt=story" : "");

(async () => {
  const browser = await playwright.chromium.launch({ executablePath: fs.existsSync("/opt/pw-browsers/chromium") ? undefined : undefined });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on("pageerror", e => console.error("pageerror:", e.message));
  const ready = () => page.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
  const frame = await (async () => null)();

  if (mode === "cards") {
    const only = opt("only", null);
    for (let i = 1; i <= 10; i++) {
      if (only && parseInt(only, 10) !== i) continue;
      await page.goto(url("static=" + i)); await ready();
      const f = path.join(out, `${fmt === "story" ? "story" : "card"}-${String(i).padStart(2, "0")}.png`);
      await page.locator("#frame").screenshot({ path: f });
      console.log("wrote", f);
    }
  } else {
    await page.goto(url("render=1")); await ready();
    const total = await page.evaluate(() => window.__total);
    const from = parseFloat(opt("from", "0")), to = Math.min(parseFloat(opt("to", String(total))), total);
    const n = Math.round((to - from) * fps);
    const f = path.join(out, opt("out", fmt === "story" ? "kokka-no-ketsudan-01-story.mp4" : "kokka-no-ketsudan-01-feed.mp4"));
    const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-i", "-",
      "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
      "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
      "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", f], { stdio: ["pipe", "inherit", "inherit"] });
    const el = page.locator("#frame");
    const t0 = Date.now();
    for (let k = 0; k < n; k++) {
      await page.evaluate(t => window.__seek(t), from + k / fps);
      const buf = await page.screenshot({ type: "jpeg", quality: 93, clip: { x: 0, y: 0, width: W, height: H } });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
      if (k % 150 === 0) console.log(`frame ${k}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on("close", r));
    console.log("wrote", f);
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
