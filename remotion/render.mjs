// Render a Hype Studio video plan with Remotion: node render.mjs plan.json out.mp4
// Prints "progress=<0..1>" lines for the Python job and exits non-zero on failure.
import { bundle } from "@remotion/bundler";
import { ensureBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const [planPath, output] = process.argv.slice(2);
if (!planPath || !output) {
  console.error("Usage: node render.mjs plan.json out.mp4");
  process.exit(2);
}

// Reuse the webpack bundle while the composition sources are unchanged.
const sources = readdirSync(path.join(here, "src")).sort()
  .map((name) => readFileSync(path.join(here, "src", name)));
const digest = createHash("sha256").update(Buffer.concat(sources)).digest("hex").slice(0, 16);
const cacheDir = path.join(here, ".bundle");
const marker = path.join(cacheDir, ".digest");
let serveUrl = cacheDir;
if (!existsSync(marker) || readFileSync(marker, "utf8") !== digest) {
  rmSync(cacheDir, { recursive: true, force: true });
  serveUrl = await bundle({ entryPoint: path.join(here, "src", "index.jsx"), outDir: cacheDir });
  writeFileSync(marker, digest);
}

// Prefer an explicit or preinstalled headless shell; otherwise Remotion fetches its own once.
function findBrowser() {
  if (process.env.REMOTION_BROWSER) return process.env.REMOTION_BROWSER;
  const root = "/opt/pw-browsers";
  if (existsSync(root)) {
    for (const name of readdirSync(root).filter((entry) => entry.startsWith("chromium_headless_shell"))) {
      const candidate = path.join(root, name, "chrome-linux", "headless_shell");
      if (existsSync(candidate)) return candidate;
    }
  }
  return null;
}
const browserExecutable = findBrowser();
if (!browserExecutable) await ensureBrowser();

const plan = JSON.parse(readFileSync(planPath, "utf8"));
const inputProps = { plan };
const composition = await selectComposition({ serveUrl, id: "AopiaVideo", inputProps, browserExecutable, logLevel: "error" });
let last = -1;
await renderMedia({
  composition, serveUrl, codec: "h264", outputLocation: output, inputProps, browserExecutable,
  muted: true, crf: 20, pixelFormat: "yuv420p", logLevel: "error",
  concurrency: Math.max(1, Math.min(4, os.cpus().length - 1)),
  onProgress: ({ progress }) => {
    const step = Math.floor(progress * 50);
    if (step !== last) {
      last = step;
      process.stdout.write(`progress=${progress.toFixed(3)}\n`);
    }
  },
});
process.stdout.write("progress=1\n");
