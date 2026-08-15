"""Compare a new agent module with the frozen first-submission artifact."""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402
from scripts.validate_artifact import load_artifact_agent  # noqa: E402


def load_callable(reference: str):
    module_name, attribute = reference.split(":", 1)
    return getattr(importlib.import_module(module_name), attribute)


def suspicious_fallback_turns(steps, seat):
    """Flag safe no-op fallbacks that Kaggle still reports as a completed game."""
    count = 0
    for step in steps[1:]:
        state = step[seat]
        obs = state.get("observation") or {}
        farms = obs.get("farms") or []
        if seat >= len(farms):
            continue
        expected_hands = len(farms[seat].get("hands", []))
        action = state.get("action") or {}
        private = obs.get("private") or {}
        shed_has_value = any(int(value) > 0 for value in (private.get("shed") or {}).values())
        empty_action = (
            action.get("farmer") == ["PASS"]
            and action.get("hands") == []
            and action.get("market") == []
        )
        if empty_action and (expected_hands > 0 or (int(obs.get("day", 0)) >= 28 and shed_has_value)):
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("challenger", help="Python reference such as agents.experimental:agent")
    parser.add_argument("--baseline", type=Path, default=PROJECT_ROOT / "artifacts" / "kaggriculture-v0.2.1.tar.gz")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    challenger = load_callable(args.challenger)
    kaggle, _ = load_environment()
    games = []
    with tempfile.TemporaryDirectory(prefix="kaggriculture-baseline-") as temp_dir:
        baseline = load_artifact_agent(args.baseline.resolve(), Path(temp_dir))
        for seed in range(args.seeds):
            for seat in (0, 1):
                agents = [baseline, baseline]
                agents[seat] = challenger
                env = kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
                env.run(agents)
                final = env.steps[-1]
                banks = [float(state["reward"]) for state in final]
                margin = banks[seat] - banks[1 - seat]
                games.append({
                    "seed": seed,
                    "seat": seat,
                    "result": "win" if margin > 0 else ("loss" if margin < 0 else "tie"),
                    "challenger_bank": banks[seat],
                    "baseline_bank": banks[1 - seat],
                    "margin": margin,
                    "statuses": [state["status"] for state in final],
                    "suspicious_fallback_turns": suspicious_fallback_turns(env.steps, seat),
                })

    summary = {
        "episodes": len(games),
        "wins": sum(game["result"] == "win" for game in games),
        "losses": sum(game["result"] == "loss" for game in games),
        "ties": sum(game["result"] == "tie" for game in games),
        "average_margin": round(statistics.mean(game["margin"] for game in games), 2),
        "runtime_failures": sum(any(status != "DONE" for status in game["statuses"]) for game in games),
        "suspicious_fallback_turns": sum(game["suspicious_fallback_turns"] for game in games),
    }
    payload = {"baseline": args.baseline.name, "challenger": args.challenger, "summary": summary, "games": games}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
