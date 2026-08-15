"""Build a compact, browser-friendly daily replay for the best Balanced Tempo run."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.balanced_tempo import balanced_tempo_agent  # noqa: E402
from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402


def tile_code(tile):
    if tile is None:
        return "empty"
    if tile == "LOCKED":
        return "locked"
    if not isinstance(tile, dict):
        return "empty"
    if "animal" in tile:
        return tile["animal"].lower()
    if tile.get("kind") == "PLANT":
        return tile.get("crop", "plant").lower()
    return tile.get("kind", "empty").lower()


def count_assets(farm):
    counts = Counter()
    for row in farm["tiles"]:
        for tile in row:
            code = tile_code(tile)
            if code != "empty" and code != "locked":
                counts[code] += 1
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
                market_units[order[0]] += int(order[2])
    return {
        "unit_ops": dict(unit_ops.most_common()),
        "market_ops": dict(market_ops.most_common()),
        "market_units": dict(market_units.most_common()),
    }


def phase_for(day):
    if day <= 10:
        return "Cash foundation"
    if day <= 12:
        return "Transition"
    if day <= 26:
        return "Compound"
    return "Exit gap"


def reasoning_for(day, actions, changes):
    unit = actions["unit_ops"]
    market = actions["market_ops"]
    if day == 0:
        return {
            "title": "Fund the first harvest",
            "text": "The opening rule buys melon and wheat seeds, hires six hands, then plants and waters before the first day closes.",
        }
    if day <= 10:
        return {
            "title": "Protect melon yield",
            "text": f"Watering stays ahead of expansion ({unit.get('WATER', 0)} water actions today) so the first payout survives.",
        }
    if market.get("BUY_ANIMAL") or unit.get("BUILD_PASTURE"):
        return {
            "title": "Convert cash into recurring output",
            "text": "The transition rule builds pasture capacity, buys cattle, and begins the daily feed-and-care loop.",
        }
    if market.get("BUY_LAND"):
        return {
            "title": "Buy productive room",
            "text": "The land gate fired only after the opening payout left enough cash to preserve an operating buffer.",
        }
    if day <= 26:
        return {
            "title": "Run both production clocks",
            "text": f"The scheduler balances recurring strawberries and cattle: {unit.get('HARVEST', 0)} harvest, {unit.get('FEED', 0)} feed, and {unit.get('CARE', 0)} care actions.",
        }
    return {
        "title": "No hard liquidation gate",
        "text": "v0 keeps hiring and replenishing seeds while selling continuously. It has an exit intention, but no rule that stops reinvestment—our clearest next fix.",
    }


def describe_changes(previous, current, actions):
    if previous is None:
        return "Opened the farm and established the first crop grid."
    notes = []
    previous_assets = previous["assets"]
    current_assets = current["assets"]
    for key, label in (("melon", "melons"), ("strawberry", "strawberries"), ("cow", "cows"), ("pasture", "pastures")):
        delta = current_assets.get(key, 0) - previous_assets.get(key, 0)
        if delta:
            notes.append(f"{delta:+d} {label}")
    land_delta = current["quadrants"] - previous["quadrants"]
    if land_delta:
        notes.append(f"{land_delta:+d} quadrant")
    sold = actions["market_units"].get("SELL", 0)
    if sold:
        notes.append(f"sold {sold} units")
    return ", ".join(notes) if notes else "Maintained the active production loop."


def build_replay(env, seed, seat):
    days = []
    previous = None
    for day in range(30):
        visual_index = min(day * 24 + 23, len(env.steps) - 1)
        end_index = min((day + 1) * 24, len(env.steps) - 1)
        visual_obs = env.steps[visual_index][seat]["observation"]
        end_obs = env.steps[end_index][seat]["observation"]
        farm = end_obs["farms"][seat]
        visual_farm = visual_obs["farms"][seat]
        private = end_obs.get("private", {}) or {}
        opponent = end_obs["farms"][1 - seat]
        actions = action_summary(env.steps, seat, day * 24 + 1, min((day + 1) * 24 + 1, len(env.steps)))
        snapshot = {
            "day": day,
            "phase": phase_for(day),
            "bank": round(float(farm["money"])),
            "opponent_bank": round(float(opponent["money"])),
            "margin": round(float(farm["money"] - opponent["money"])),
            "quadrants": len(farm.get("unlocked_quadrants", [])),
            "shed_units": int(sum(private.get("shed", {}).values())),
            "assets": count_assets(farm),
            "cells": [tile_code(tile) for row in visual_farm["tiles"] for tile in row],
            "workers": [
                {"x": int(position[0]), "y": int(position[1]), "kind": "farmer" if index == 0 else "hand"}
                for index, position in enumerate([visual_farm["farmer"], *visual_farm.get("hands", [])])
            ],
            "actions": actions,
        }
        snapshot["change"] = describe_changes(previous, snapshot, actions)
        snapshot["reasoning"] = reasoning_for(day, actions, snapshot["change"])
        snapshot["bank_delta"] = snapshot["bank"] - (previous["bank"] if previous else 3000)
        days.append(snapshot)
        previous = snapshot
    return {
        "agent": "Balanced Tempo v0",
        "opponent": "Official starter",
        "seed": seed,
        "seat": seat,
        "final_bank": days[-1]["bank"],
        "days": days,
    }


def main():
    results_path = PROJECT_ROOT / "results" / "balanced_tempo_v0.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    best = max(results["games"], key=lambda game: game["balanced_bank"])
    seed, seat = int(best["seed"]), int(best["seat"])

    kaggle, module = load_environment()
    env = kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
    agents = [module.starter_agent, module.starter_agent]
    agents[seat] = balanced_tempo_agent
    env.run(agents)
    replay = build_replay(env, seed, seat)

    json_path = PROJECT_ROOT / "results" / "balanced_tempo_best_run.json"
    js_path = PROJECT_ROOT / "results" / "balanced_tempo_best_run.js"
    json_path.write_text(json.dumps(replay, indent=2), encoding="utf-8")
    js_path.write_text("window.BALANCED_BEST_RUN = " + json.dumps(replay, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"best seed={seed} seat={seat} bank={replay['final_bank']}")
    print(f"saved {json_path}")
    print(f"saved {js_path}")


if __name__ == "__main__":
    main()

