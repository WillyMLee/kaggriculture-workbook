# v2.0 online arena + strategy inventory working set

Date: 2026-08-18

## Objective

1. Make the Fieldbook Human Arena playable from the hosted site and provide a useful feedback submission path.
2. Consolidate candidate strategies into an early / middle / late inventory with explicit keep, refine, and cull decisions.

## Boundaries

- Preserve the exact local Python/Kaggle arena as the research-grade simulator unless a faithful browser runtime can be proved.
- Label any online simplification clearly; do not imply that a proxy is the exact Kaggle engine.
- Do not submit a Kaggle agent.
- GitHub push and Cloudflare deployment are authorized by the user.
- Avoid committing unrelated user work; inspect the existing dirty tree and remote state before staging.
- Do not expose credentials or private replay state.

## Required evidence

- Current UI/API dependency map for `human-arena.js` and `scripts/human_arena_server.py`.
- A phase-aware strategy inventory with evidence and cull rationale.
- Desktop and mobile play-through checks, including starting a game, making a move, advancing state, and saving feedback.
- Successful Git push and a live Cloudflare URL verified after deployment.

## Active unknowns

- Whether the current hosted Pages project supports Functions or a separate Worker is required.
- Whether a faithful browser-side environment implementation already exists in the repository.
- Whether Cloudflare credentials and the Git remote are currently available.

## Resolution

- Cloudflare Pages Functions compile successfully for the existing Pages project.
- The hosted game is a separate day-level strategy proxy (`v2.0-dojo-1`); the exact Python arena remains unchanged below it.
- D1 stores anonymous sessions, per-day decisions, rationales, confidence, turning-point flags, and free-form feedback.
- Local QA completed API health, create, step, resume, feedback, five 30-day benchmark seasons, browser interaction, and strategy-inventory rendering.
- A saturated-plot coach recommendation found during QA was fixed by making crop/livestock utility infeasible when fewer than two capacity slots remain.
