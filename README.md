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

## Adaptive Horizon candidate

`main.py` is the local entry point for Adaptive Horizon v0.7.0. It keeps the v0.6.1 terminal planner and adds within-match opponent memory, temporal strategy beliefs, productive-asset threat, asset-aware valuation, and one compact diagnostic trace per game day. Unexpected states still fall back to a valid `PASS` action and now emit an explicit error record.

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

The generated `artifacts/kaggriculture-v0.7.0.tar.gz` contains one self-contained `main.py`. It remains local until its benchmark and packaging gates pass. The submitted v0.2.1/v0.6.1 and frozen v0.4.0/v0.5.0/v0.5.1/v0.6.0 artifacts remain exact controls.

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

v0.6.1 was submitted to Kaggle on August 15 ET / August 16 UTC. After 18 visible external matches it was 9–9 with a 562.2 score. Episode 93564365 against PQ_Marz exposed a specific blind spot: our cash led through the middle game while the opponent accumulated far more land, crops, and animals, then won 60,301 to 57,559.

Adaptive Horizon v0.7.0 turns that replay into `results/kaggle_v0_6_1_pq_marz_regression.json`. The temporal regression detects livestock compounding by day 9, a 35-tile scale gap and fifth-animal response by day 12, and a 24-animal gap by day 21. A naive second-quadrant branch was tested and rejected after going 0–4 against v0.6.1 with a −10,982 average margin; extra plots increased chore and travel load faster than realized output. Use `scripts/extract_replay_learning.py` to convert future Kaggle replays into the same compact evidence format.

The final exact both-seat suite against frozen v0.6.1 finished 7–7–6 across 20 games, with a +103.8 average margin, −4,621 minimum margin, zero runtime failures, zero suspicious fallbacks, and 123.095 ms maximum action time. This is a non-regression result with one improved asymmetric seed, not evidence of superiority. The local 12,785-byte artifact passed the single-file packaging contract with SHA-256 `0c1c5cbbd21f7f094173a2b8dd2cc1f51f853df6c64d8bef52b7a43590588ab7`; it should remain on hold until broader opponent-family tests justify a ladder submission.

Adaptive Horizon v0.7.1-i5 fixes the seed-503 terminal regression by making wheat pickup honor the reverse planner's remaining feed obligations. The known failure flipped from −6 to +380, and the bounded exact suite finished 20–0 against frozen v0.7.0 across seeds 500–509 and both seats, with a +5,685.2 average margin, +380 minimum margin, zero failures or suspicious fallbacks, and a 334.716 ms maximum local action time. The 15,356-byte artifact is locally promoted over v0.7.0. A six-game persona sanity check finished 4–2; both −13,434 losses came from the mixed-conversion persona, so this is not yet a Kaggle submission recommendation.

Frontier Horizon v0.7.2 is a held experimental branch built from two current-leader public replays. Their first 144 actions were identical, supporting a deterministic 12-melon / 7-wheat / 2-cow / 2-sheep opener followed by signal-driven adaptation. The candidate couples land purchases to utilization, payback, deployed livestock, recurring density, and held inventory; it also reserves a small expansion crew and scales to twelve daily hands. A bounded eight-game offline training arena records win/loss plus trajectory milestones rather than claiming access to private opponent code. The final checkpoint finished 1–7 (−12,301.88 average), including a +86 win and −2,605 loss against the frontier proxy, with zero failures, zero suspicious fallbacks, and 289.004 ms maximum action time. Against frozen v0.7.1-i5 on the fixed expansion seed it lost both seats by 1,862 and 1,648—a large improvement over the earlier roughly 13k deficit, but still a failed promotion gate. The exact 18,349-byte artifact is packaged locally and was not submitted.

The v0.8 roadmap keeps v0.7.1 as the always-on lean core and treats v0.7.2's frontier machinery as a conditional branch. A daily selector will compare lean, selective-expansion, and frontier terminal value after land, labor, travel, feed, switching, and stranded-inventory costs. More expensive opponent prediction and town simulation activate only near material decisions, with hysteresis and bailout thresholds. Counterfactual arenas will run identical seeds through each branch and compile the best outcome splits into a shallow tree. Deeper v0.9 density—compact forest votes, portfolio specialists, and short stochastic rollouts—remains gated until v0.8 preserves the predecessor suite, avoids a losing persona family, and proves a real 60k+ path.

Lean Horizon v0.8.0 implements the first roadmap layer: v0.7.1-compatible operations remain the default, while a cached daily selector scores lean, selective, and frontier branches from visible land commitments, service slack, payback, market opportunity, and hysteresis. A fixed both-seat seed comparison against the exact v0.7.1-i5 artifact finished 1–1 at exactly zero average margin. On six identical persona games, both versions finished 1–5, but v0.8 improved average margin from −4,936 to −4,187 and reduced the worst measured action from 3,599.713 ms to 767.159 ms; its cow/fertilizer deficit improved by 2,247 on average. A relaxed frontier-readiness experiment was rejected after worsening the two-seat frontier average from −4,364.5 to −6,569. The exact 19,962-byte artifact passes 21 deterministic regressions and one self-play packaging validation, but remains held because it does not clear persona, 60k-cap, or 700 ms gates.

Lean Horizon v0.8.1 adds back reasoning density at the day-12 engine commitment instead of making the whole agent heavier. Six crop×livestock paths vote from crop and animal return, town synergy, feed, labor, fertilizer, incumbent value, and opponent supply; a three-day history, vote edge, and locked commitment prevent hourly strategy thrashing. A matched eight-game arena against four inferred personas improved average margin from −6,315.13 for exact v0.8.0 to −5,833.38: three games improved, five were unchanged, and none regressed. The cow/fertilizer deficit improved by 1,187 on average. The exact 21,594-byte single-file artifact passes 21 policy regressions and two self-play seeds, but remains held at 1–7 with no day-24 60k milestone. One combined arena run hit the environment deadline after seven games; the isolated missing matchup completed normally, so runtime stress remains an open gate rather than a silent pass.

Lean Horizon v0.8.2 makes the operations, opponent, and horizon attention modules operative through one cached daily softmax over cash, recurring, livestock, and liquidity strategies. Its five-case training loop caught a pre-hire service-pressure bug and rejected both universal and frontier-specific four-cow caps; the retained tree lets softmax select an engine family while preserving v0.8.0's proven asset count. The final matched training average was effectively neutral (−20 coins per game). On the untouched 20-game promotion gate against exact v0.8.0, v0.8.2 finished 4–10–6 with a +440 average margin, −1,265 worst loss, zero failures, zero fallbacks, and 120.845 ms maximum action time. A single +4,650 two-seat seed drives the positive average. The exact 22,778-byte artifact passes packaging and two self-play seeds but fails the required 20–0 reliability gate and must not be submitted.

Lean Horizon v0.8.3 restores the useful temporal commitment density from v0.7 without reopening v0.7.2's failed frontier bulk. A trace showed that v0.8.2 replaced its day-12 committed crop with each new daily vote after livestock deployed; a temporary tomato vote bought seeds that the next strawberry vote stranded. v0.8.3 preserves the committed crop and day while attention and softmax continue updating diagnostically. On the eight diagnostic games it improves from v0.8.2's 3–3–2 (+1,137.5 average, −1,265 worst) to 3–1–4 (+1,237.5 average, −1,215 worst). The twelve-game holdout finishes 1–1–10 at zero average margin with no failures. Across the comparable 20 games, the record improves from 4–10–6 to 4–2–14 and average margin from +440 to +495, but fourteen ties still fail the required 20–0 promotion rule. The exact 22,937-byte artifact passes 22 regressions and two self-play seeds and remains a held local candidate.

Lean Horizon v0.8.4 asks whether an adaptive policy can outperform a fixed engine once that engine is recognized from public play. Counterfactual branches show that dramatic sheep and goose pivots lose 0–4 each against exact v0.8.0, while preserving the lean engine and adding a fifth cow wins 4–0 at +2,502.5 average and +652 worst margin. The implemented recognizer uses the visible one-quadrant melon/wheat opener during days 10–12 and later crop/livestock commitments; it never uses opponent identity and rejects a two-quadrant frontier fingerprint. Initial six-game screens finish 6–0 against v0.7.0, v0.7.1-i5, and v0.7.2, while the fresh 20-game v0.7.1-i5 gate finishes 13–3–4 at +1,170.6 average, −2,253 worst, zero failures, zero fallbacks, and 111.336 ms maximum action time. The exact 24,192-byte artifact passes 23 regressions and three self-play seeds. Kaggle accepted it as an exploratory submission on August 16 and currently shows it as pending, but it has not met the internal 20–0 promotion rule.

## Sources

Competition facts were checked against the live Kaggle pages on August 14, 2026:

- <https://www.kaggle.com/competitions/kaggriculture/overview>
- <https://www.kaggle.com/competitions/kaggriculture/rules>

The official competition page and environment always take precedence if the rules or mechanics change.
