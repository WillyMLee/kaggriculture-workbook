# v2.0 human arena working set

Date: 2026-08-18

## Outcome

Build a Fieldbook page where the user can play a complete Kaggriculture episode against the frozen Alpha5 artifact, inspect enough state to make informed decisions, annotate junctions, and save the episode into a versioned reinforcement-learning dataset.

## In scope

- Local session server over the exact installed Kaggriculture environment.
- Human action authoring, validation, day/turn stepping, replay persistence, and feedback labels.
- Fieldbook farm/town/inventory/action UI with agent comparison and decision history.
- Dataset ingestion from historical arena JSONL plus new human episodes.
- A small offline reinforcement learner whose output is measured against the frozen Alpha5 floor.

## Boundaries

- No Kaggle submission or Cloudflare deployment in this task.
- No live LLM, cross-match writable state, or unbounded training.
- Alpha5 remains the frozen baseline; learned policies must pass deterministic schema and replay gates before they can affect an agent artifact.
- Every long run needs a wall-clock cap and partial checkpoint.

## Evidence required

- Engine/session API tests.
- One completed or smoke-tested human session with a saved replay.
- Fieldbook desktop and mobile visual QA with no console errors.
- Deterministic dataset/trainer test and baseline-versus-candidate metrics.
- A checkpoint naming what is ready, experimental, and next.

## Unknowns to resolve

- Exact manual-step API and observation/action schemas in the installed environment.
- Which historical replay files contain transition-complete junction rows.
- Whether a full episode can be played one turn at a time without reimplementing environment rules.

