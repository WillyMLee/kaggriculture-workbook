"""Compare a new agent module with the frozen first-submission artifact."""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
import tempfile
import time
import hashlib
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


def daily_trace(steps, seat):
    """Compact day-boundary evidence for locating the first strategic divergence."""
    trace = []
    for step in steps:
        state = step[seat]
        obs = state.get("observation") or {}
        if int(obs.get("hour", -1)) != 0:
            continue
        farms = obs.get("farms") or []
        if len(farms) < 2:
            continue
        ours = farms[seat]
        theirs = farms[1 - seat]

        def crop_counts(farm):
            counts = {}
            for row in farm.get("tiles", []):
                for tile in row:
                    if isinstance(tile, dict) and tile.get("crop"):
                        crop = tile["crop"]
                        counts[crop] = counts.get(crop, 0) + 1
            return counts

        def animal_counts(farm):
            counts = {}
            for row in farm.get("tiles", []):
                for tile in row:
                    if isinstance(tile, dict) and tile.get("animal"):
                        animal = tile["animal"]
                        counts[animal] = counts.get(animal, 0) + 1
            return counts

        trace.append({
            "day": int(obs.get("day", 0)),
            "bank": float(ours.get("money", 0)),
            "opponent_bank": float(theirs.get("money", 0)),
            "crops": crop_counts(ours),
            "opponent_crops": crop_counts(theirs),
            "animals": animal_counts(ours),
            "opponent_animals": animal_counts(theirs),
            "shed": (obs.get("private") or {}).get("shed", {}),
            "prices": (obs.get("market") or {}).get("prices", {}),
            "shops": (obs.get("town") or {}).get("unlocked_shops", []),
        })
    return trace


def summarize_games(games):
    if not games:
        return {
            "episodes": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "average_margin": 0,
            "minimum_margin": 0,
            "runtime_failures": 0,
            "suspicious_fallback_turns": 0,
            "maximum_action_ms": 0,
        }
    margins = [game["margin"] for game in games]
    return {
        "episodes": len(games),
        "wins": sum(game["result"] == "win" for game in games),
        "losses": sum(game["result"] == "loss" for game in games),
        "ties": sum(game["result"] == "tie" for game in games),
        "average_margin": round(statistics.mean(margins), 2),
        "minimum_margin": round(min(margins), 2),
        "runtime_failures": sum(any(status != "DONE" for status in game["statuses"]) for game in games),
        "suspicious_fallback_turns": sum(game["suspicious_fallback_turns"] for game in games),
        "maximum_action_ms": max(game["max_action_ms"] for game in games),
    }


def write_result(path, args, games, challenger_load_ms, complete):
    artifact = args.challenger_artifact.resolve() if args.challenger_artifact else None
    payload = {
        "complete": complete,
        "expected_episodes": args.seeds * 2,
        "baseline": args.baseline.name,
        "challenger": args.challenger_artifact.name if args.challenger_artifact else args.challenger,
        "configuration": {"seed_start": args.seed_start, "seeds": args.seeds, "seat_orders": 2},
        "artifact": {
            "bytes": artifact.stat().st_size,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "load_ms": challenger_load_ms,
        } if artifact else None,
        "summary": summarize_games(games),
        "games": games,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("challenger", nargs="?", default="agents.balanced_tempo:agent", help="Python reference such as agents.experimental:agent")
    parser.add_argument("--challenger-artifact", type=Path, help="Exact tar.gz challenger artifact; overrides the Python reference")
    parser.add_argument("--baseline", type=Path, default=PROJECT_ROOT / "artifacts" / "kaggriculture-v0.2.1.tar.gz")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--daily-trace", action="store_true")
    args = parser.parse_args()

    kaggle, _ = load_environment()
    games = []
    with tempfile.TemporaryDirectory(prefix="kaggriculture-baseline-") as temp_dir:
        temp_root = Path(temp_dir)
        baseline = load_artifact_agent(args.baseline.resolve(), temp_root / "baseline")
        load_started = time.perf_counter()
        challenger = (
            load_artifact_agent(args.challenger_artifact.resolve(), temp_root / "challenger")
            if args.challenger_artifact
            else load_callable(args.challenger)
        )
        challenger_load_ms = round((time.perf_counter() - load_started) * 1000, 3)
        for seed in range(args.seed_start, args.seed_start + args.seeds):
            for seat in (0, 1):
                action_times_ms = []

                def timed_challenger(obs):
                    started = time.perf_counter()
                    action = challenger(obs)
                    action_times_ms.append((time.perf_counter() - started) * 1000)
                    return action

                agents = [baseline, baseline]
                agents[seat] = timed_challenger
                env = kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
                env.run(agents)
                final = env.steps[-1]
                banks = [float(state["reward"]) for state in final]
                margin = banks[seat] - banks[1 - seat]
                game = {
                    "seed": seed,
                    "seat": seat,
                    "result": "win" if margin > 0 else ("loss" if margin < 0 else "tie"),
                    "challenger_bank": banks[seat],
                    "baseline_bank": banks[1 - seat],
                    "margin": margin,
                    "statuses": [state["status"] for state in final],
                    "suspicious_fallback_turns": suspicious_fallback_turns(env.steps, seat),
                    "max_action_ms": round(max(action_times_ms, default=0), 3),
                    "average_action_ms": round(statistics.mean(action_times_ms), 3) if action_times_ms else 0,
                }
                if args.daily_trace:
                    game["daily_trace"] = daily_trace(env.steps, seat)
                games.append(game)
                if args.output:
                    write_result(args.output, args, games, challenger_load_ms, complete=False)

    summary = summarize_games(games)
    if args.output:
        write_result(args.output, args, games, challenger_load_ms, complete=True)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
