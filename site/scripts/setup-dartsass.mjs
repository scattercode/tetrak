/**
 * setup-dartsass.mjs
 *
 * Postinstall script that replaces node_modules/.bin/sass with a symlink to
 * the platform-specific native Dart Sass binary installed by sass-embedded.
 *
 * Hugo's dartsass transpiler calls `sass --embedded` and communicates via the
 * Embedded Sass Protocol over stdin/stdout. The JS wrapper that sass-embedded
 * puts in node_modules/.bin/sass does not support this protocol. The native
 * binary in the platform-specific optional dependency (e.g.
 * sass-embedded-darwin-arm64) does.
 *
 * On Apple Silicon Macs running Node.js under Rosetta 2, os.arch() reports
 * 'x64' even though the arm64 package is installed. This script tries the
 * OS-reported key first, then falls back to all candidates for the current
 * platform so it handles Rosetta transparently.
 *
 * Prerequisites: sass-embedded must be installed (npm install).
 * Run: node scripts/setup-dartsass.mjs  (or automatically via postinstall)
 */

import { existsSync, lstatSync, unlinkSync, symlinkSync } from "fs";
import { resolve } from "path";
import { fileURLToPath } from "url";
import { platform, arch } from "os";

const ROOT = resolve(fileURLToPath(import.meta.url), "..", "..");

const PLATFORM_PACKAGES = {
  "darwin-arm64": "sass-embedded-darwin-arm64",
  "darwin-x64": "sass-embedded-darwin-x64",
  "linux-x64": "sass-embedded-linux-x64",
  "linux-arm64": "sass-embedded-linux-arm64",
  "linux-arm": "sass-embedded-linux-arm",
  "win32-x64": "sass-embedded-win32-x64",
  "win32-arm64": "sass-embedded-win32-arm64"
};

const os = platform();
const reportedKey = `${os}-${arch()}`;

// Build a list of candidates: reported arch first, then all others for this OS.
// This handles Rosetta 2 (os.arch() = 'x64' but arm64 package is installed).
const candidates = [
  reportedKey,
  ...Object.keys(PLATFORM_PACKAGES).filter(k => k.startsWith(`${os}-`) && k !== reportedKey)
];

let nativeSass = null;

for (const key of candidates) {
  const candidate = PLATFORM_PACKAGES[key];
  if (!candidate) continue;
  const bin = resolve(ROOT, "node_modules", candidate, "dart-sass", "sass");
  if (existsSync(bin)) {
    nativeSass = bin;
    if (key !== reportedKey) {
      console.log(`setup-dartsass: ${reportedKey} binary not found; using ${key} (Rosetta or cross-install)`);
    }
    break;
  }
}

if (!nativeSass) {
  console.error(`setup-dartsass: no native Dart Sass binary found for platform '${os}' in node_modules`);
  process.exit(1);
}

const binSass = resolve(ROOT, "node_modules", ".bin", "sass");

// lstatSync, not existsSync: existsSync follows the link, so a *dangling*
// symlink reports false, the unlink below is skipped, and symlinkSync then
// fails with EEXIST. That is exactly what a renamed or moved checkout leaves
// behind, because the link this script writes is absolute -- so the one
// situation where re-running it is the documented fix was the one it could
// not repair. lstatSync stats the link itself.
if (lstatSync(binSass, { throwIfNoEntry: false })) {
  unlinkSync(binSass);
}

symlinkSync(nativeSass, binSass);
console.log(`setup-dartsass: linked node_modules/.bin/sass → ${nativeSass}`);
