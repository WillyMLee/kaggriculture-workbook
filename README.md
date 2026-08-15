# Kaggriculture Fieldbook

A local, dependency-free website for understanding the Kaggriculture simulation competition and tracking agent experiments.

**Live site:** <https://kaggriculture-workbook.pages.dev/>

**Source:** <https://github.com/WillyMLee/kaggriculture-workbook>

## Build and deploy

Create the static Cloudflare Pages bundle:

```powershell
npm install
npm run build
```

Deploy it to the configured Cloudflare Pages project:

```powershell
npm run deploy
```

## Open it

Double-click `index.html`, or run a local server from this folder:

```powershell
python -m http.server 4173
```

Then open <http://localhost:4173>.

## What is included

- A verified competition brief and deadline summary
- A visual game-mechanics reference
- A persistent baseline-readiness checklist
- An experiment log with a clearly labeled head-to-head outcome chart and JSON export
- A scored improvement roadmap

Checklist, experiment, and roadmap data are stored in the browser's local storage. The experiment export creates a portable JSON backup.

## Balanced Tempo benchmark

The first executable agent lives in `agents/balanced_tempo.py`. Its paired local benchmark is saved to `results/balanced_tempo_v0.json` and summarized in the Balanced Tempo notebook tabs.

The best match is condensed into a 30-day replay in `results/balanced_tempo_best_run.json`; the browser-ready copy is generated alongside it.

Run it with:

```powershell
.\.venv\Scripts\python.exe scripts\run_balanced_experiment.py --seeds 10
.\.venv\Scripts\python.exe scripts\build_best_run_replay.py
```

The project-local runtime loads the official Kaggriculture environment plugin from `.vendor/kaggle-environments` while remaining compatible with Python 3.9.

## Sources

Competition facts were checked against the live Kaggle pages on August 14, 2026:

- <https://www.kaggle.com/competitions/kaggriculture/overview>
- <https://www.kaggle.com/competitions/kaggriculture/rules>

The official competition page and environment always take precedence if the rules or mechanics change.
