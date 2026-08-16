"""Compact public Kaggriculture replays into day-level strategy evidence.

The raw replay payloads are roughly 30 MB each.  This script keeps only
observable daily state, action counts, and transparent engine labels so the
evidence can be reviewed and versioned without retaining the raw files.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")
MIDGAME_DAYS = set(range(12, 24))


def phase_for(day: int) -> str:
    """Use narrow decision windows instead of one broad early/mid/late label."""
    if day <= 2:
        return "bootstrap"
    if day <= 7:
        return "opener-build"
    if day <= 11:
        return "first-conversion"
    if day <= 15:
        return "engine-commit"
    if day <= 19:
        return "throughput-balance"
    if day <= 23:
        return "engine-convert"
    if day <= 27:
        return "terminal-optimize"
    return "liquidate"


def tile_counts(farm: dict) -> tuple[dict, dict, int]:
    crops = Counter()
    animals = Counter()
    weeds = 0
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            crop = tile.get("crop")
            animal = tile.get("animal")
            if crop:
                crops[crop] += 1
            if animal:
                animals[animal] += 1
            if tile.get("kind") == "WEED":
                weeds += 1
    return dict(crops), dict(animals), weeds


def action_counts(day_steps: list[dict]) -> dict:
    counts = Counter()
    for state in day_steps:
        action = state.get("action") or {}
        orders = [action.get("farmer") or []] + list(action.get("hands") or []) + list(action.get("market") or [])
        for order in orders:
            if order and order[0] != "PASS":
                counts[str(order[0])] += 1
                if order[0] in {"BUY_SEED", "BUY_ANIMAL", "SELL", "BUY_PRODUCT"} and len(order) > 1:
                    counts[f"{order[0]}:{order[1]}"] += int(order[2]) if len(order) > 2 else 1
                elif order[0] == "PLANT" and len(order) > 1:
                    counts[f"PLANT:{order[1]}"] += 1
    return dict(sorted(counts.items()))


def classify_engine(crops: dict, animals: dict, actions: dict, day: int) -> dict:
    """Return an interpretable engine posterior from visible commitments."""
    scores = {
        "staple-volume": 0.45 * crops.get("WHEAT", 0),
        "cash-crop": 1.4 * crops.get("MELON", 0) + 0.65 * crops.get("CARROT", 0),
        "recurring-crop": 1.25 * crops.get("TOMATO", 0) + 1.55 * crops.get("STRAWBERRY", 0),
        "livestock": animals.get("GOOSE", 0) + 1.4 * animals.get("COW", 0) + 1.5 * animals.get("SHEEP", 0),
    }
    scores["cash-crop"] += 0.35 * actions.get("BUY_SEED:MELON", 0)
    scores["recurring-crop"] += 0.25 * (
        actions.get("BUY_SEED:TOMATO", 0) + actions.get("BUY_SEED:STRAWBERRY", 0)
    )
    scores["livestock"] += 0.4 * sum(actions.get(f"BUY_ANIMAL:{animal}", 0) for animal in ANIMALS)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    leader, leader_score = ranked[0]
    runner, runner_score = ranked[1]
    if leader_score <= 0:
        label = "undeclared"
    elif runner_score >= leader_score * 0.72 and runner_score >= 2:
        label = f"hybrid:{leader}+{runner}"
    else:
        label = leader
    if day >= 28:
        label = f"liquidation:{label}"
    total = sum(max(0, value) for value in scores.values()) or 1
    return {
        "label": label,
        "confidence": round(leader_score / total, 3),
        "scores": {key: round(value, 2) for key, value in scores.items()},
    }


def compact_farm(farm: dict) -> dict:
    crops, animals, weeds = tile_counts(farm)
    return {
        "bank": round(float(farm.get("money", 0)), 2),
        "hands": len(farm.get("hands", [])),
        "quadrants": len(farm.get("unlocked_quadrants", [])),
        "crops": {crop: crops.get(crop, 0) for crop in CROPS if crops.get(crop, 0)},
        "animals": {animal: animals.get(animal, 0) for animal in ANIMALS if animals.get(animal, 0)},
        "weeds": weeds,
    }


def extract_replay(path: Path, team: str, rank: int) -> dict:
    replay = json.loads(path.read_text(encoding="utf-8"))
    teams = replay.get("info", {}).get("TeamNames", [])
    if team not in teams:
        raise ValueError(f"{team!r} is not in {path.name}: {teams}")
    seat = teams.index(team)
    opponent_seat = 1 - seat
    by_day: dict[int, list[dict]] = {}
    boundary: dict[int, dict] = {}
    for step in replay.get("steps", []):
        state = step[seat]
        obs = state.get("observation") or {}
        day = int(obs.get("day", -1))
        if day < 0:
            continue
        by_day.setdefault(day, []).append(state)
        if int(obs.get("hour", -1)) == 0:
            boundary[day] = obs

    daily = []
    prior_label = None
    for day in sorted(boundary):
        obs = boundary[day]
        farms = obs.get("farms") or []
        if len(farms) < 2:
            continue
        ours = compact_farm(farms[seat])
        theirs = compact_farm(farms[opponent_seat])
        actions = action_counts(by_day.get(day, []))
        engine = classify_engine(ours["crops"], ours["animals"], actions, day)
        transition = prior_label is not None and engine["label"] != prior_label
        prior_label = engine["label"]
        daily.append({
            "day": day,
            "phase": phase_for(day),
            "engine": engine,
            "engine_transition": transition,
            "farm": ours,
            "opponent": theirs,
            "bank_margin": round(ours["bank"] - theirs["bank"], 2),
            "actions": actions,
            "shed": {key: int(value) for key, value in ((obs.get("private") or {}).get("shed") or {}).items() if value},
            "prices": {key: int(value) for key, value in ((obs.get("market") or {}).get("prices") or {}).items()},
            "shops": list((obs.get("town") or {}).get("unlocked_shops", [])),
        })

    rewards = [float(value) for value in replay.get("rewards", [])]
    margin = rewards[seat] - rewards[opponent_seat]
    return {
        "episode_id": int(replay.get("info", {}).get("EpisodeId", replay.get("id", 0))),
        "seed": replay.get("info", {}).get("seed"),
        "rank_at_capture": rank,
        "team": team,
        "opponent": teams[opponent_seat],
        "seat": seat,
        "result": "win" if margin > 0 else ("loss" if margin < 0 else "tie"),
        "reward": round(rewards[seat], 2),
        "opponent_reward": round(rewards[opponent_seat], 2),
        "margin": round(margin, 2),
        "daily": daily,
    }


def summarize(episodes: list[dict]) -> dict:
    mid_labels = Counter()
    mid_actions = Counter()
    team_labels: dict[str, Counter] = {}
    for episode in episodes:
        team_counter = team_labels.setdefault(episode["team"], Counter())
        for day in episode["daily"]:
            if day["day"] not in MIDGAME_DAYS:
                continue
            label = day["engine"]["label"]
            mid_labels[label] += 1
            team_counter[label] += 1
            for action, count in day["actions"].items():
                mid_actions[action] += count
    return {
        "episodes": len(episodes),
        "teams": len({item["team"] for item in episodes}),
        "wins": sum(item["result"] == "win" for item in episodes),
        "losses": sum(item["result"] == "loss" for item in episodes),
        "ties": sum(item["result"] == "tie" for item in episodes),
        "midgame_engine_days": dict(mid_labels.most_common()),
        "midgame_action_counts": dict(mid_actions.most_common()),
        "team_midgame_modes": {
            team: counts.most_common(3) for team, counts in sorted(team_labels.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("replays", nargs="*", type=Path)
    parser.add_argument("--team", required=True)
    parser.add_argument("--rank", required=True, type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    episodes = []
    if args.append and args.output.exists():
        episodes = json.loads(args.output.read_text(encoding="utf-8")).get("episodes", [])
    # The same public episode can appear in both sampled teams' recent lists;
    # keep each team's perspective because private inventory and intent differ.
    known = {(item["episode_id"], item["team"]) for item in episodes}
    for path in args.replays:
        episode = extract_replay(path.resolve(), args.team, args.rank)
        key = (episode["episode_id"], episode["team"])
        if key not in known:
            episodes.append(episode)
            known.add(key)
    episodes.sort(key=lambda item: (item["rank_at_capture"], -item["episode_id"]))
    payload = {
        "schema": "kaggriculture-public-ladder-strategy-v1",
        "capture_date": "2026-08-16",
        "sample_design": "Every tenth public rank from 100 through 200; two most recent visible matches per team.",
        "classifier": {
            "type": "transparent weighted commitment classifier",
            "labels": ["staple-volume", "cash-crop", "recurring-crop", "livestock", "hybrid", "undeclared"],
            "caveat": "Labels describe visible commitments, not private intent or source code.",
        },
        "summary": summarize(episodes),
        "episodes": episodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
