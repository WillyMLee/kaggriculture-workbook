import { copyFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const outputRoot = join(projectRoot, "dist");
const assets = [
  "index.html",
  "styles.css",
  "app.js",
  "strategy-lab.js",
  "human-arena.js",
  "results/balanced_tempo_best_run.js",
];

await mkdir(outputRoot, { recursive: true });

for (const asset of assets) {
  const destination = join(outputRoot, asset);
  await mkdir(dirname(destination), { recursive: true });
  await copyFile(join(projectRoot, asset), destination);
}

console.log(`Built ${assets.length} static assets in ${outputRoot}`);
