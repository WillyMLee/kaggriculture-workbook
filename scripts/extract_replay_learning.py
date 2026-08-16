"""Convert Kaggle replay JSON into compact, versionable learning evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def tile_counts(farm):
    crops = {}
    animals = {}
    weeds = 0
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("crop"):
                crops[tile["crop"]] = crops.get(tile["crop"], 0) + 1
            if tile.get("animal"):
                animals[tile["animal"]] = animals.get(tile["animal"], 0) + 1
            if tile.get("kind") == "WEED":
                weeds += 1
    return {"crops": crops, "animals": animals, "weeds": weeds}


def summarize_farm(farm):
    return {
        "bank": float(farm.get("money", 0)),
        "hands": len(farm.get("hands", [])),
        "quadrants": list(farm.get("unlocked_quadrants", [])),
        **tile_counts(farm),
    }


def extract(path, team, checkpoint_days):
    replay = json.loads(path.read_text(encoding="utf-8"))
    teams = replay.get("info", {}).get("TeamNames", [])
    if team not in teams:
        raise ValueError(f"{team!r} is not in {path.name}: {teams}")
    seat = teams.index(team)
    opponent_seat = 1 - seat
    daily = []
    checkpoints = []
    for step in replay.get("steps", []):
        state = step[seat]
        obs = state.get("observation") or {}
        if int(obs.get("hour", -1)) != 0:
            continue
        day = int(obs.get("day", 0))
        farms = obs.get("farms", [])
        if len(farms) < 2:
            continue
        record = {
            "day": day,
            "ours": summarize_farm(farms[seat]),
            "opponent": summarize_farm(farms[opponent_seat]),
            "bank_margin": float(farms[seat].get("money", 0)) - float(farms[opponent_seat].get("money", 0)),
            "shed": (obs.get("private") or {}).get("shed", {}),
            "prices": (obs.get("market") or {}).get("prices", {}),
            "shops": (obs.get("town") or {}).get("unlocked_shops", []),
        }
        daily.append(record)
        if day in checkpoint_days:
            checkpoints.append({"day": day, "observation": obs, "action": state.get("action")})

    rewards = [float(value) for value in replay.get("rewards", [])]
    our_reward = rewards[seat]
    opponent_reward = rewards[opponent_seat]
    return {
        "source_file": path.name,
        "episode_id": replay.get("info", {}).get("EpisodeId", replay.get("id")),
        "seed": replay.get("info", {}).get("seed"),
        "team": team,
        "opponent": teams[opponent_seat],
        "seat": seat,
        "result": "win" if our_reward > opponent_reward else ("loss" if our_reward < opponent_reward else "tie"),
        "rewards": {"ours": our_reward, "opponent": opponent_reward, "margin": our_reward - opponent_reward},
        "daily": daily,
        "checkpoints": checkpoints,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--team", default="William Lee")
    parser.add_argument("--checkpoint-days", nargs="*", type=int, default=[0, 9, 12, 15, 21, 27])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    episodes = [extract(path.resolve(), args.team, set(args.checkpoint_days)) for path in args.replays]
    payload = {
        "schema": "kaggriculture-replay-learning-v1",
        "episodes": episodes,
        "summary": {
            "games": len(episodes),
            "wins": sum(item["result"] == "win" for item in episodes),
            "losses": sum(item["result"] == "loss" for item in episodes),
            "ties": sum(item["result"] == "tie" for item in episodes),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}))


if __name__ == "__main__":
    main()
