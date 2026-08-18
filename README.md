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

The hosted Strategy Dojo uses a Pages Function plus the `kaggriculture-fieldbook` D1 binding. Apply migrations before the first deployment:

```powershell
npx wrangler d1 migrations apply kaggriculture-fieldbook --remote
```

The online dojo is a transparent day-level strategy proxy for gathering early/middle/late decisions and feedback. The Python Human Arena remains the exact Kaggle-environment mode and runs locally.

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

Lean Horizon v0.8.4 asks whether an adaptive policy can outperform a fixed engine once that engine is recognized from public play. Counterfactual branches show that dramatic sheep and goose pivots lose 0–4 each against exact v0.8.0, while preserving the lean engine and adding a fifth cow wins 4–0 at +2,502.5 average and +652 worst margin. The implemented recognizer uses the visible one-quadrant melon/wheat opener during days 10–12 and later crop/livestock commitments; it never uses opponent identity and rejects a two-quadrant frontier fingerprint. Initial six-game screens finish 6–0 against v0.7.0, v0.7.1-i5, and v0.7.2, while the fresh 20-game v0.7.1-i5 gate finishes 13–3–4 at +1,170.6 average, −2,253 worst, zero failures, zero fallbacks, and 111.336 ms maximum action time. Kaggle's live evaluation now shows 590.5 at rank 3,095 with a visible recent record of 3–2. A 43,351–77,597 loss to an immediate livestock engine confirms that day-10 recognition is too late against opener compounding. Treat v0.8.4 as a live hold, not a promoted baseline.

Compound Horizon v0.8.5 moves the response into the opener. It buys four cows with compact wheat/melon support, then unlocks the second plot only after three animals are placed, seven wheat cells are serviced, and conversion cash is available. Dynamic livestock scoring begins after the opener with switch hysteresis. The final failure-persona gate is 2–0 against the Sarthak proxy at +9,107 average and 0–2 against the Vignesh proxy at −8,941—an improvement of 3,053 over frozen v0.8.4 on that case. Exact paired seeds 1800–1802 finish 2–4 against v0.8.4 at −3,146 average and −14,660 worst, with zero failures/fallbacks and 39.882 ms maximum action time. The shop-driven recurring branch was rejected because it stranded deployment work. v0.8.5 is held and must not be submitted.

Core Horizon v0.9.0 rebuilds core play from ten current top-ladder perspectives rather than adding another opponent-response patch. The common spine is a 7-wheat / 12-melon / 2-cow / 2-sheep opener, staged land, strawberry conversion, 14-animal middle game, and terminal liquidation; town and product economics may tilt cows versus sheep without letting opponent attention replace the engine. QA exposed and fixed two basic execution bugs: a cached land order could repeat or be dropped behind the ten-order market cap, and closing new-animal investment also stopped feed purchases for existing livestock after day 20. The exact packaged `main.py` clears both frozen controls 20–0 across seeds 1900–1909 and both seats: +9,588.5 average / +235 worst against v0.7.1-i5 and +9,119.35 average / +335 worst against v0.8.4, with zero runtime failures or fallbacks and 107.505 ms maximum action time. The 26,265-byte artifact SHA-256 is `5834f0db3d9555e590d1c0e03d7f4a8f62573ab72f8e449f139aaeb3a82025db`. It is locally promoted but was not submitted or deployed in this pass.

Core Horizon v0.9.1-i4 corrects two core-economy failures found on fresh variable seeds. Livestock targets now preserve deployed and held animals when environmental signals change the preferred species, buying only the remaining phase slots; the service queue protects feed and care before routine crop watering. The exact 26,537-byte artifact finishes 10–0 against v0.9.0 on the five-seed development panel (+12,969.8 average, +9,038 minimum) and 6–0 on a frozen three-seed random holdout (+10,792 average, +5,732 minimum), with zero failures or suspicious fallbacks. Holdout terminal bank averages 67,404 versus 56,612 for v0.9.0. Five-hand labor and fixed 42-plot density ablations were both rejected. The artifact SHA-256 is `1cf72ea930347dc83d3593415453dd6bb9724cc0f2a41fe5c49355ec0a955f41`; it was submitted to Kaggle on August 17 and was pending at browser verification.

The final frozen release gate completes 20–0 versus exact v0.9.0 at +12,692.4 average and +5,732 worst. Fresh seeds 2200–2209 finish 19–1 versus both v0.7.1-i5 (+12,963.45 average) and v0.8.4 (+12,509.75 average), with the same −9,780 seed-2200 seat-0 loss and zero runtime failures or fallbacks. The trace shows a town-schema failure: milk falls from 193 to 34 while two yarn stores unlock, but the committed engine remains 10 cows / 4 sheep; after the recurring crop disappears, an instantaneous tile-count gate also prevents third land despite more than 10k cash. v0.9.1-i4 remains a strong exploratory candidate but is held under the literal 20–0 cross-family release rule. The prioritized follow-up is recorded in `results/v0_9_2_backlog.md`.

v0.9.2-i1 begins the v1.0 program with remembered recurring-density milestones and one bounded additive restructure when the middle-game town schema sharply favors wool. On the exact seed-2200 regression it now beats v0.8.4 in both seats by +3,854 and +64. A new weighted random-seed arena samples documented core styles, pairs both seats, checkpoints after every episode, and emits daily state/action/terminal-return JSONL for later decision-tree or offline-RL fitting. Its four-episode harness smoke finished 4–0 at +30,219 average with 120 training rows, zero failures, and zero fallbacks. This is implementation evidence, not a promotion gate; see `results/v1_0_training_arena_checkpoint.md`.

The first preregistered v1.0 arena loop kept the exact v0.9.2-i1 artifact frozen and finished 12–0 at +24,466.17 average, +7,401 minimum, zero failures, and 46.288 ms maximum action time. With no policy failure to justify another heuristic, the loop repaired the learning-data contract instead: daily rows now contain an explicit branch/action summary, planned hires, next state, terminal marker, and diagnostic bank delta. The scheduler also guarantees one shuffled pass over every selected style before weighted repeats whenever the budget permits. The transition smoke produced 60 valid rows and finished 2–0. Details and the next decision are in `results/v1_0_arena_loop1_checkpoint.md`.

The aggressive-route lab adds a selectable crop-first day-0 land policy without changing the default agent. It reproduces the intended two-plot timing but finishes 0–2 against frozen v0.9.2-i1 at −12,196.5 average on replay seed 164828330. A day-6 handoff (−19,840) and a forced third plot (−23,540) were rejected: both prove that land without engine continuity or deployable capacity is negative value. The shared router now blocks feed and fertilizer assignments to unequipped workers, and all 38 focused regressions pass. The retained route, replay families, and next promotion gates are documented in `results/aggressive_route_playbook.md`; nothing from this lab was submitted.

The current default was frozen honestly as v1.0.0-alpha1 for an exact comparison with submitted v0.9.1-i4. It is not a trained v1.0 model yet: the transition dataset exists, but no learned branch scorer has been fitted. Across known seed 2200 and fresh seeds 2600–2604 in both seats, alpha1 finishes 6–6 at −4,219.42 average, −30,308 worst, 57,098 average terminal bank, zero failures/fallbacks, and 63.39 ms maximum action time. It wins both seats on supportive seeds 2602 and 2604, but loses both on seeds 2601 and 2603. The earliest failure is unconditional capital intensity: it reaches three plots and 14 animals even when the town path rewards the submitted agent's compact one-plot engine. Alpha1 is held; see `results/v1_0_0_alpha1_vs_submitted_checkpoint.md`.

At the earlier four-game checkpoint, v0.9.1-i4 was 3–1 at 622.7. Wins over Kaito Ichikawa, Micah Fernando, and taaaaanq ranged from +3,816 to +35,186 and demonstrated both compact recurring and expanded livestock paths. The −22,692 Manuel Pérez loss identified the core junction: land was purchased on day 7 with 1,728 cash, the bank fell to 47, and the engine remained cow-heavy as three Yarn Stores appeared; by day 14 it had 18 weeds, no crops, and 22% productive land utilization. An active full-bundle cash guard improved over alpha1 on a bounded internal panel but lost all eight completed games against the submitted control (−7,974.75 average), so v1.0.0-alpha2 was rejected and the working default restored. This historical checkpoint led to the scored compact-versus-expand controller; replays, junction weights, capital metrics, and hardening/break rules are in `results/kaggle_v0_9_1_latest_matches.json` and `results/v1_0_core_junction_analysis.md`.

v1.0.0-alpha3 implements that scored junction. The exact single-file artifact preserves the mixed opener, then chooses among compact, expand, repair, and liquidate using full-bundle funding, productive utilization, service slack, weeds, town support, opponent land, and horizon evidence. Its exact 20-game v0.9-series panel finishes 14–6 at +13,771.95 average, −8,666 worst, zero failures/fallbacks, and 45.347 ms maximum action time: 8–0 versus v0.9.0, 4–4 versus submitted v0.9.1-i4, and 2–2 versus v0.9.2-i1. All losses cluster on environment seeds 2700 and 2703 in both seats. The 30,028-byte artifact SHA-256 is `0c60ef7b1d5e6151659cba8449233e1df75d736e9f43503bd0eb8318fe1b8046`; it is held locally because it did not clear the 20–0 promotion gate. See `results/v1_0_0_alpha3_vs_v0_9_series_checkpoint.md`.

v1.0.0-alpha4 adds one bounded terminal-junction lever after the −20,738 BeyondAnalytics replay exposed stranded seed capital and late wheat order churn. Reachability now blocks seed purchases and planting whose first useful yield cannot arrive by day 28, while liquidation releases unnecessary holds. The replay also shows that Beyond led by 14,332 on day 22 with a much larger strawberry/sheep engine, so terminal cleanup is explicitly secondary to the midgame engine deficit. The exact 30,920-byte artifact finishes 6–4 against v0.9.2-i1 across seeds 2700–2703 and the Beyond seed in both seats at +7,394.5 average and −8,981 worst, with zero failures/fallbacks. It improves the Beyond-seed margin by 137 but slightly trails alpha3 on their shared 2700–2701 panel. A capped four-style mini arena finishes 8–0 at +31,668.5 average and emits 240 daily transitions; these are persona proxies, not private top agents or in-match learning. Alpha4 is held. See `results/v1_0_0_alpha4_checkpoint.md`.

v1.0.0-alpha5 traces alpha4's remaining failures to a day-13 capital cliff: seeds 2700 and 2703 broke a compact commitment at only 48% two-quadrant utilization, bought eight animals and a third plot, and lost to v0.9.2's compact strawberry engine in both seats. The new scored junction requires either 64% productive utilization or repeated town demand before expansion wins. The repeated-demand exception preserves the two-Smoothie Beyond path. The exact 31,403-byte artifact finishes 10–0 against v0.9.2-i1 across the frozen four-seed panel and Beyond seed in both seats at +7,829.6 average and +2,075 worst, with zero failures/fallbacks. It ties alpha4 in 12 direct games because their coupled trajectories remove the lean-opponent prediction break. On the same capped arena seed and personas, alpha5 finishes 8–0 at +33,962.62 average, +2,294.12 above alpha4. Alpha5 is the local front runner but remains held for a fresh 20-game release gate. See `results/v1_0_0_alpha5_checkpoint.md`.

v1.0.0-alpha6 adds a constant-time favorable/base/adverse value head at the daily compact/expand/repair/liquidate junction, borrowing bounded option search—not an LLM or open-ended MCTS—from competitive Pokémon agents. It preserves alpha5's exact 10–0 frozen v0.9.2/Beyond panel at +7,829.6 average and +2,075 worst, but is neutral in four direct alpha5 games. A capped six-style arena completed 12–0 at +28,270.42 average with zero failures/fallbacks and emitted 360 daily transitions; a game-seed-safe split produces 240 training and 120 validation rows for a later offline option-value tree. Alpha6 is held as an architecture candidate. See `results/v1_0_0_alpha6_checkpoint.md` and `results/pokemon_bot_architecture_research.md`.

v1.0.0-alpha7 lets material counterfactual regret release a stale expansion commitment before its capital/service damage becomes visible. A broader first draft was rejected after compact/expand thrashing flipped the Beyond control from +8,324 to −2,406; the final asymmetric veto restores Beyond and adds both failure modes as regressions. The exact 32,682-byte artifact passes 41 policy tests, preserves the frozen 10–0 v0.9.2/Beyond panel at +7,829.6 average and +2,075 worst, and repeats the six-style arena at 12–0. Fresh direct evidence remains neutral versus Alpha6 (1–1–6) and Alpha5 (1–1–2), so Alpha7 is held. The Alpha8 backlog ranks entropy-triggered search, economic quiescence, a terminal tablebase, incremental evaluation, transposition caching, and belief-particle opponent search. See `results/v1_0_0_alpha7_checkpoint.md` and `results/alpha8_optimizer_research_backlog.md`.

v1.0.0-alpha9 adds a bounded four-day scenario model-predictive controller at the daily capital junction. It compares compact, expand, repair, and liquidate packages; rejects plans that fail cash, productive-density, service-capacity, or remaining-payback constraints; executes one daily decision; and replans from the next observation. The final 36,364-byte artifact with SHA-256 `a660250d84b138713c9838572c100734c73e3fa799aa2fbaeb079676f2932459` passes the exact last-submission gate 20–0 at +3,945.6 average and +2,032 worst, preserves the frozen v0.9.2/Beyond panel 10–0, and completes a capped persona arena 12–0 with zero failures. This meets the local submission criterion but is not evidence of leaderboard superiority; v1.1 research targets interruptible engine options, decomposed farm-value heads, selective package search, expert-iteration distillation, and a diverse adversarial arena. See `results/v1_0_0_alpha9_checkpoint.md`, `results/alpha10_research_directions.md`, and `results/v1_1_go_architecture_research.md`.

The exact Alpha9 artifact was submitted as the first v1.0 ladder entry and produced an initial public score of 606.8. That early checkpoint was 1.6 above v0.9.1-i4's 605.2 and 2.9 below v0.8.4's 609.7; later Alpha9 snapshots and replay reviews supersede it as current evidence.

v1.1.0-alpha1 adds interruptible launch, densify, expand, repair, and close options and repairs the planner/executor land gap. A broad “MPC feasible” authorization was rejected after it regressed both frozen controls; the retained land gate also requires a visible opponent plot lead and blocks another purchase during stabilization. The exact 37,706-byte artifact passes 49 policy tests, preserves the v0.9.2/Beyond panel 10–0 at +7,538 average, and finishes a six-style arena 12–0 at +29,109 average. It ties Alpha9 0–0–8 directly, so it remains held. The next ordered lever is a KataGo-inspired decomposed farm value with explicit density, service, capital-efficiency, terminal-conversion, and bank-trajectory heads. See `results/v1_1_0_alpha1_checkpoint.md` and `results/v1_1_go_architecture_research.md`.

v1.1.0-alpha2 implements that decomposed farm-value lever in constant time. Capacity, service, capital, runway, and trajectory now reweight the four daily capital branches, while a bundle-level land guard cancels dependent purchases whenever expansion is not authorized. The exact 39,100-byte artifact passes 53 policy tests, beats submitted Alpha9 8–0 at +6,830 average, beats v0.9.2 8–0 at +10,931.88 average, and wins both seats on each of the two reviewed ladder-loss seeds against the aggressive-land proxy. A fresh 20-episode Alpha9 panel stopped at its cap after 17 episodes with 11 wins, 6 ties, and 0 losses; the ties already fail the strict 20–0 promotion rule. Alpha2 remains local; see `results/v1_1_0_alpha2_checkpoint.md` and `results/v1_0_alpha9_latest_match_review.md`.

v1.1.0-alpha3-i2 adds a strict proactive saturation permit: a one-plot farm may break a stale compact commitment only when density, full-bundle funding, service slack, runway, the decomposed value head, scenario MPC, and bank parity all agree. It converts seed 3300 from two ties to two +88 wins and preserves the v0.9.2 frozen panel 8–0. However, the exact twenty-episode Alpha9 gate finishes 16–4 at +5,634.85 average and −10,689 worst, so the candidate is held. A five-style mini arena finishes 10–0 at +24,536.3 average, revealing that the current persona gym does not represent Alpha9's mirror/variance failure. The next architecture is a one-day stage/reserve option plus distributional lower-tail value; see `results/v1_1_0_alpha3_i2_checkpoint.md`.

v1.1.0-alpha4 implements that staged option. An equal-land expansion reserves cash for one observation, then commits only when funding, service, feasibility, weeds, scenario selection, lower-tail value, and forecast spread remain safe; otherwise it releases to the frozen compact floor. The exact twenty-game Alpha9 panel finishes 12–0–8 at +3,482.35 average with zero failures/fallbacks and 62.51 ms maximum action time. The same artifact finishes an eight-style mini arena 8–0 at +27,015.12 average, but reaches neither early expansion nor a day-24 60k bank in any episode. Alpha4 is safer than Alpha3 but remains held because eight ties fail the strict 20–0 gate and the persona gym lacks the newly observed capacity paths. The newest four visible Alpha9 episodes finished 1–3: one loss came from a denser one-plot livestock engine, two from funded multi-plot compounding, and the win showed why unfunded expansion must still be rejected. See `results/v1_1_0_alpha4_checkpoint.md`, `results/kaggle_alpha9_recent_four_review.json`, and `results/mixed_model_cross_game_research.md`.

v1.1.0-alpha5 replaces the single capacity score with a risk-adjusted mixture of lean liquidity, dense one-plot livestock, and staged land compounding. Each path exposes expected, lower-tail, adverse, and spread values; a confidence shield retains the lean blueprint when the winner lacks separation or serviceability. The exact 43,223-byte artifact passes 62 policy tests and finishes the frozen Alpha9 panel 20–0 at +5,141.9 average, +85 minimum, with zero failures/fallbacks. Its eight-persona arena remains 8–0 at +34,084.62 average while the day-15 eight-livestock milestone rises from 12.5% to 62.5%. Alpha5 is not a universal local replacement: Alpha4 wins seed 3304 in both seats by 221, making their five-seed comparison 8–2. Four denser follow-ups were rejected after either known-seed losses, fresh losses to base Alpha5, or a worse seed-3304 regression. Recent-AI research therefore prioritizes offline search teachers, a distilled junction tree, and a small residual world model rather than a live LLM. See `results/v1_1_0_alpha5_checkpoint.md` and `results/alpha6_recent_ai_research.md`.

The v2.0 series is planned as a teacher-trained controller around Alpha5's deterministic floor. Alpha1 targets the seed-3304 purchase-to-deployment failure with a productive-slot scheduler; later increments add exact counterfactual labels, a distilled shallow junction ensemble, calibrated residual values, and an adversarial league. Promotion requires fresh 20–0 gates against Alpha5, Alpha4, and submitted Alpha9, plus bounded runtime and cell-level arena coverage. Runs are capped at two smoke games, four traced diagnostics, and twenty regression games per mechanism before the final holdout. See `results/v2_0_series_roadmap.md`.

The first v2 core-economy pass isolates absolute farm value from opponent adaptation. A transparent enumerator models crop clocks, livestock production, feed, land, daily workhands, town demand, nonlinear market crowding, and service capacity; its neutral robust hypothesis targets three plots and 56 serviceable productive cells rather than unconditional four-plot growth. Alpha5 already averages 92,934 bank against passive market load, while sampled elite public replays finish at 111K–146K through different openings but consistently preserve high crop/livestock density and near-zero midgame weeds. An initial opponent-blind ablation exposed overweighted land-rush reaction. The final v2d iteration authorizes land from our own economics, executes a selective rather than aggressive bundle, and replaces the one-time crop wave with a 26-tile recurring target. On one frozen passive seed it is essentially level with Alpha5 (82,199 vs 82,392 mean) with a better minimum; on two fresh paired pressure seeds it improves mean bank by 5,194 against the Sarthak proxy and 12,336 against lean liquidity, with zero failures, backlog, or unsold value. Those seeds are now consumed. `agents/core_economy_v2.py` remains unsubmitted pending a new holdout and does not change the Alpha5 entry point. See `results/v2_0_core_economy_checkpoint.md`.

## Sources

Competition facts were checked against the live Kaggle pages on August 14, 2026:

- <https://www.kaggle.com/competitions/kaggriculture/overview>
- <https://www.kaggle.com/competitions/kaggriculture/rules>

The official competition page and environment always take precedence if the rules or mechanics change.
