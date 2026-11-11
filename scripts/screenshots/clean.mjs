// npm run shots:clean [-- --dry-run]
// Removes screenshots/tmp and screenshots/raw (never final/). Lists what it will delete first.
import { RAW, TMP, dryRunThenDelete, listOwned, log, rel } from "./lib.mjs";

const dryRunOnly = process.argv.includes("--dry-run");
for (const dir of [TMP, RAW]) {
  const { owned, foreign } = listOwned(dir);
  dryRunThenDelete(owned, { label: rel(dir), dryRunOnly, removeEmptyDirs: dir === TMP ? [TMP] : [] });
  if (foreign.length) log(`  left alone (not created by this workflow): ${foreign.map((f) => rel(f.path)).join(", ")}`);
}
