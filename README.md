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

## Reverse Horizon candidate

`main.py` is the local entry point for Reverse Horizon v0.6. It extends Dense Predictor v0.5.1 with a backward terminal-state model: payoff reachability, last productive feed/care/water obligations, travel slack, shed capacity, and demand-timed liquidation. Unexpected states still fall back to a valid `PASS` action, while the evaluator separately flags suspicious fallbacks.

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

The generated `artifacts/kaggriculture-v0.6.1.tar.gz` contains one self-contained `main.py`. It is a promoted local-only candidate. The accepted v0.2.1 and frozen v0.4.0/v0.5.0/v0.5.1/v0.6.0 artifacts remain exact controls.

Kaggle accepted v0.2.1 after v0.2.0 exposed a runtime package-name collision with the generic module name `agents`. Four reviewed matches produced a 1–3 record and exposed fixed labor, market-crowding, and terminal liquidation failures. The compact archive is `results/kaggle_v0_2_1_match_history.json`.

Compare a future architecture with that artifact in both seats:

```powershell
.\.venv\Scripts\python.exe scripts\run_challenger.py agents.balanced_tempo:agent --seeds 10 --output results\phase_tempo_v0_3_vs_v0_2_1.json
```

The corrected phase candidate and weighted-strategy v0.4 candidate each won 20 of 20 local games against the exact v0.2.1 artifact, averaging a +13,439.25 bank margin. This is only the fixed-opponent gate; broader strategy-family evaluation remains required before another Kaggle submission.

Run exact-artifact packaging and held-out matchup QA with:

```powershell
.\.venv\Scripts\python.exe scripts\qa_submission_artifact.py artifacts\kaggriculture-v0.4.0.tar.gz --output results\qa_v0_4_packaging.json
.\.venv\Scripts\python.exe scripts\run_challenger.py --challenger-artifact artifacts\kaggriculture-v0.4.0.tar.gz --seed-start 10 --seeds 50 --output results\qa_v0_4_vs_submitted_v0_2_1_heldout.json
```

That held-out suite produced 100 wins in 100 games, a +11,853.13 average margin, a +1,380 minimum margin, zero runtime failures, zero suspicious fallbacks, and a 49.889 ms maximum local action time. The 4,854-byte archive is far below the competition's 100 MiB limit and contains only root-level `main.py`.

Dense Predictor v0.5.1 is intentionally not promoted yet. Its exact 6,557-byte artifact won 20 of 20 held-out games against submitted v0.2.1 (+10,619 average, +6,012 minimum), then won 19 of 20 against frozen v0.4 (+4,300 average) with one repeatable seed 5, seat 0 loss of 2,719. It recorded zero runtime failures, zero suspicious fallbacks, and a 64.183 ms maximum local action time. The failed case remains the next optimization target.

Reverse Horizon v0.6 is also a held candidate. Its first checkpoint lost 8-12 to v0.5.1. A seed-6 self-control trace showed that earlier operational completion sold milk before town demand lifted its price; adding capacity-safe, demand-timed liquidation flipped that regression from 0-2 to 2-0. The final exact 7,595-byte artifact won 12 of 20 games against v0.5.1 across seeds 0-9 and both seats, averaging +323.7 with a -2,999 minimum margin, zero runtime failures, zero suspicious fallbacks, and a 30.339 ms maximum local action time. This is an aggregate improvement, not sufficient reliability for promotion or submission.

Reverse Horizon v0.6.1 adds marginal crop/livestock economics, probability-weighted strategy-group utility, profitable fertilizer allocation, and deadline-aware global worker assignment. Its first unbounded router timed out on held-out seed 10; bounding the candidate set to three task alternatives per worker fixed that case at 75.64 ms and was added as a stress regression. The final exact 10,039-byte artifact went 60-0 against the v0.5 class: 20-0 against v0.5.0 (+14,911.6 average), 20-0 against v0.5.1 (+14,072.05), and 20-0 on held-out seeds 10-19 against v0.5.1 (+13,222.8). The combined worst margin was +8,748, with zero runtime failures, zero suspicious fallbacks, and a 319.111 ms maximum local action time. It is promoted locally; unfamiliar Kaggle ladder architectures remain the next test.

v0.6.1 was submitted to Kaggle on August 15 ET / August 16 UTC. The exact frozen artifact was accepted with an initial score of 600.0 and rank #2,891. The only available episode at the first checkpoint was validation self-play, so competitive conclusions are deferred until external matches arrive.

## Sources

Competition facts were checked against the live Kaggle pages on August 14, 2026:

- <https://www.kaggle.com/competitions/kaggriculture/overview>
- <https://www.kaggle.com/competitions/kaggriculture/rules>

The official competition page and environment always take precedence if the rules or mechanics change.
