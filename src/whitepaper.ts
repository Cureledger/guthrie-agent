import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

let cachedText: string | null = null;

/**
 * Resolve path to bundled whitepaper markdown (works in dev from src/ and prod from dist/).
 */
function resolveWhitepaperPath(): string {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);

  const candidates = [
    join(__dirname, "data", "cureledger-whitepaper.md"),
    join(__dirname, "..", "data", "cureledger-whitepaper.md"),
    join(process.cwd(), "src", "data", "cureledger-whitepaper.md"),
    join(process.cwd(), "dist", "data", "cureledger-whitepaper.md"),
    join(process.cwd(), "guthrie", "src", "data", "cureledger-whitepaper.md"),
    join(process.cwd(), "guthrie", "dist", "data", "cureledger-whitepaper.md"),
  ];

  for (const p of candidates) {
    if (existsSync(p)) return p;
  }

  throw new Error(
    "cureledger-whitepaper.md not found. Run build so dist/data/ is populated, or keep src/data/ in dev.",
  );
}

/** Full whitepaper markdown (April 2026). Loaded once per process. */
export function getWhitepaperFullText(): string {
  if (cachedText) return cachedText;
  cachedText = readFileSync(resolveWhitepaperPath(), "utf-8");
  return cachedText;
}
