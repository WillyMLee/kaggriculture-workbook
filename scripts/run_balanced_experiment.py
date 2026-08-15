"""Run Balanced Tempo v0 against the official starter in both seat orders."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.balanced_tempo import balanced_tempo_agent  # noqa: E402
from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402


def final_snapshot(env, seat):
    state = env.steps[-1][seat]
    obs = state["observation"]
    farm = obs["farms"][seat]
    private = obs.get("private", {}) or {}
    tiles = [tile for row in farm["tiles"] for tile in row]
    return {
        "bank": float(farm["money"]),
        "shed_units": int(sum(private.get("shed", {}).values())),
        "cows": sum(1 for tile in tiles if isinstance(tile, dict) and tile.get("animal") == "COW"),
        "strawberries": sum(1 for tile in tiles if isinstance(tile, dict) and tile.get("crop") == "STRAWBERRY"),
        "quadrants": len(farm.get("unlocked_quadrants", [])),
    }


def run_game(kaggle, module, seed, seat):
    env = kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
    agents = [module.starter_agent, module.starter_agent]
    agents[seat] = balanced_tempo_agent
    env.run(agents)
    rewards = [float(item["reward"]) for item in env.steps[-1]]
    result = "tie" if rewards[0] == rewards[1] else ("win" if rewards[seat] > rewards[1 - seat] else "loss")
    return {
        "seed": seed,
        "seat": seat,
        "result": result,
        "balanced_bank": rewards[seat],
        "starter_bank": rewards[1 - seat],
        "margin": rewards[seat] - rewards[1 - seat],
        "balanced": final_snapshot(env, seat),
        "starter": final_snapshot(env, 1 - seat),
        "statuses": [item["status"] for item in env.steps[-1]],
    }


def summarize(games):
    wins = sum(game["result"] == "win" for game in games)
    losses = sum(game["result"] == "loss" for game in games)
    ties = sum(game["result"] == "tie" for game in games)
    banks = [game["balanced_bank"] for game in games]
    margins = [game["margin"] for game in games]
    ranks = [1 if game["result"] == "win" else (1.5 if game["result"] == "tie" else 2) for game in games]
    return {
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_rate": round((wins + ties * 0.5) / len(games), 4),
        "average_rank": round(statistics.mean(ranks), 2),
        "average_bank": round(statistics.mean(banks), 2),
        "bank_range": [round(min(banks), 2), round(max(banks), 2)],
        "average_margin": round(statistics.mean(margins), 2),
        "crashes": sum(any(status == "ERROR" for status in game["statuses"]) for game in games),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=10, help="number of seeds; each is tested in both seats")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results" / "balanced_tempo_v0.json")
    args = parser.parse_args()

    kaggle, module = load_environment()
    games = [run_game(kaggle, module, seed, seat) for seed in range(args.seeds) for seat in (0, 1)]
    payload = {
        "experiment": "balanced-tempo-v0-vs-starter",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment_source": "Kaggle/kaggle-environments master, kaggriculture plugin",
        "configuration": {"seeds": args.seeds, "seat_orders": 2, "episode_steps": 720},
        "summary": summarize(games),
        "games": games,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
