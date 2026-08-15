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
- A cited market-tensions page connecting shared prices to competitive convergence
- Opponent-model, strategy-library, lookahead-simulator, and attention-controller workspaces
- A persistent baseline-readiness checklist
- An experiment log with a clearly labeled head-to-head outcome chart and JSON export
- A persistent Kaggle submission, rating, rank, and episode tracker
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

## Phase Tempo candidate

`main.py` is the safe Kaggle entry point for Phase Tempo v0.3. The policy separates early, middle, late optimization, and final execution; keeps survival labor active through the close; reserves feed before selling wheat; and collects livestock fertilizer. Unexpected states still fall back to a valid `PASS` action.

Validate the exact entry point through self-play and benchmark it against the starter:

```powershell
.\.venv\Scripts\python.exe scripts\validate_submission.py --seeds 3
.\.venv\Scripts\python.exe scripts\run_balanced_experiment.py --seeds 10 --output results\balanced_tempo_v0_2.json
```

Build and validate the exact multi-file upload:

```powershell
npm run submission:build
npm run submission:validate
```

The generated `artifacts/kaggriculture-v0.3.0.tar.gz` contains one self-contained `main.py`. The accepted `artifacts/kaggriculture-v0.2.1.tar.gz` remains the frozen first-opponent artifact.

Kaggle accepted v0.2.1 after v0.2.0 exposed a runtime package-name collision with the generic module name `agents`. Four reviewed matches produced a 1–3 record and exposed fixed labor, market-crowding, and terminal liquidation failures. The compact archive is `results/kaggle_v0_2_1_match_history.json`.

Compare a future architecture with that artifact in both seats:

```powershell
.\.venv\Scripts\python.exe scripts\run_challenger.py agents.balanced_tempo:agent --seeds 10 --output results\phase_tempo_v0_3_vs_v0_2_1.json
```

The v0.3 candidate won 19 of 20 local games against the exact v0.2.1 artifact, averaged a +5,024.25 bank margin, and recorded zero runtime failures.

## Sources

Competition facts were checked against the live Kaggle pages on August 14, 2026:

- <https://www.kaggle.com/competitions/kaggriculture/overview>
- <https://www.kaggle.com/competitions/kaggriculture/rules>

The official competition page and environment always take precedence if the rules or mechanics change.
