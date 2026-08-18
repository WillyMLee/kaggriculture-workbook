# v2.0 phase strategy inventory

Date: 2026-08-18  
Status: Fieldbook inventory + hosted strategy dojo implemented

## Operating rule

- **Keep** a mechanism in the production core only when direct, regression, or holdout evidence supports it.
- **Refine** a bounded hypothesis when the mechanism has a credible causal path but incomplete lower-tail evidence.
- **Cull** a failed mechanism from production. It may remain as an arena persona so the core learns to withstand it.

## Inventory

| Phase | Mechanism | Decision | Evidence read |
|---|---|---|---|
| Early | Lean reversible opener + six-hand service floor | Keep | Lower capital lock-in; five-hand ablation lost both seats. |
| Early | Aggressive land rush | Refine | Useful capacity threat, but requires funded deployment and route capacity. |
| Early | Forced crop-first land | Cull from production | 0–2 versus v0.9.2; day-6 handoff and forced third plot worsened the loss. |
| Middle | Recurring crop + livestock core | Keep | Strongest repeated source of serviceable compounding across promoted agents. |
| Middle | Staged land compound | Keep with gates | Expansion earns a branch only when utilization, service, bundle funding, and payback agree. |
| Middle | Mixed conversion | Refine | High upside but the weakest measured lower-tail/persona coverage. |
| Middle | Heavy opponent reaction | Cull to residual | Opponent attention must not replace absolute farm-value optimization. |
| Late | Reachability-gated finish | Keep | Prevents late purchases and work that cannot reach bank before the terminal turn. |
| Late | Staggered D18–21 replacement cohorts | Refine | Next bounded test for late productivity without a single service spike. |
| Late | Forced day-22 wheat wave | Cull | Added density while reducing terminal value (mean −193.5; worst −1,770 in the recorded ablation). |
| Close | Reachable liquidation + overflow safety | Keep | Unsold inventory has zero official terminal value. |
| Close | One-day demand timing | Refine | Hold only when tomorrow's price gain and the route to sale are both reachable. |

## Hosted Strategy Dojo boundary

The online game is `v2.0-dojo-1`, a deterministic 30-day strategy proxy. It models liquidity, crops, livestock, plot capacity, work hands, service coverage, weeds, inventory, market demand, and terminal conversion. It is designed to collect human macro choices and rationales, not to reproduce the exact 720-turn Kaggle environment.

The exact Python Human Arena remains available locally for movement, unit actions, town orders, and direct Alpha5 play. Hosted dojo decisions are stored anonymously in D1 with a per-session secret; no account or email is collected.

## Next culling cycle

1. Collect at least five complete seasons across lean, dense, land, mixed, and adaptive benchmarks.
2. Tag the earliest material value divergence, not only the final result.
3. Promote a dojo lesson into the exact simulator as one bounded mechanism.
4. Run known regression seeds, then a fresh holdout.
5. Update this inventory: keep, refine, or cull.

