"""Export a compact daily trace for one challenger-versus-baseline episode."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.balanced_tempo import _opponent_attention  # noqa: E402
from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402
from scripts.validate_artifact import load_artifact_agent  # noqa: E402


def load_callable(reference):
    module_name, attribute = reference.split(":", 1)
    return getattr(importlib.import_module(module_name), attribute)


def count_assets(farm):
    counts = Counter()
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if "animal" in tile:
                counts[tile["animal"].lower()] += 1
            elif tile.get("kind") == "PLANT":
                counts[tile.get("crop", "plant").lower()] += 1
            elif tile.get("kind"):
                counts[tile["kind"].lower()] += 1
    return dict(sorted(counts.items()))


def action_summary(steps, seat, start, end):
    unit_ops = Counter()
    market_ops = Counter()
    market_units = Counter()
    for index in range(start, min(end, len(steps))):
        action = steps[index][seat].get("action") or {}
        for unit_action in [action.get("farmer", ["PASS"]), *(action.get("hands", []) or [])]:
            if isinstance(unit_action, list) and unit_action:
                unit_ops[unit_action[0]] += 1
        for order in action.get("market", []) or []:
            if not isinstance(order, list) or not order:
                continue
            market_ops[order[0]] += 1
            if len(order) >= 3 and isinstance(order[2], (int, float)):
                market_units[f"{order[0]}:{order[1]}"] += int(order[2])
    return {
        "unit_ops": dict(unit_ops.most_common()),
        "market_ops": dict(market_ops.most_common()),
        "market_units": dict(market_units.most_common()),
    }


def player_snapshot(steps, seat, day):
    index = min((day + 1) * 24, len(steps) - 1)
    obs = steps[index][seat]["observation"]
    farm = obs["farms"][seat]
    private = obs.get("private", {}) or {}
    return {
        "bank": round(float(farm["money"])),
        "hands": len(farm.get("hands", [])),
        "quadrants": len(farm.get("unlocked_quadrants", [])),
        "assets": count_assets(farm),
        "shed": {key: int(value) for key, value in private.get("shed", {}).items() if value},
        "seeds": {key: int(value) for key, value in private.get("seeds", {}).items() if value},
        "actions": action_summary(steps, seat, day * 24 + 1, min((day + 1) * 24 + 1, len(steps))),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seat", type=int, choices=(0, 1), required=True)
    parser.add_argument("--challenger", default="agents.balanced_tempo:agent")
    parser.add_argument("--baseline", type=Path, default=PROJECT_ROOT / "artifacts" / "kaggriculture-v0.2.1.tar.gz")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    challenger = load_callable(args.challenger)
    kaggle, _ = load_environment()
    with tempfile.TemporaryDirectory(prefix="kaggriculture-trace-") as temp_dir:
        baseline = load_artifact_agent(args.baseline.resolve(), Path(temp_dir))
        agents = [baseline, baseline]
        agents[args.seat] = challenger
        env = kaggle.make(ENV_NAME, configuration={"seed": args.seed}, debug=False)
        env.run(agents)

    days = []
    for day in range(30):
        index = min((day + 1) * 24, len(env.steps) - 1)
        obs = env.steps[index][args.seat]["observation"]
        ours = player_snapshot(env.steps, args.seat, day)
        opponent = player_snapshot(env.steps, 1 - args.seat, day)
        days.append({
            "day": day,
            "margin": ours["bank"] - opponent["bank"],
            "opponent_belief": _opponent_attention(obs, args.seat),
            "ours": ours,
            "opponent": opponent,
        })

    final = env.steps[-1]
    payload = {
        "seed": args.seed,
        "challenger_seat": args.seat,
        "challenger": args.challenger,
        "baseline": args.baseline.name,
        "final_rewards": [float(state["reward"]) for state in final],
        "statuses": [state["status"] for state in final],
        "days": days,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"final_rewards": payload["final_rewards"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
