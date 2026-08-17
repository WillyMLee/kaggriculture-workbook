"""Run a bounded random-seed arena against inferred public-ladder personas."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.inferred_personas import PERSONAS  # noqa: E402
from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402
from scripts.run_challenger import suspicious_fallback_turns  # noqa: E402
from scripts.validate_artifact import load_artifact_agent  # noqa: E402


CHECKPOINT_DAYS = (7, 12, 15, 24, 29)


def trajectory_checkpoints(steps, seat):
    """Return compact state milestones used as offline reinforcement signals."""
    checkpoints = {}
    for step in steps:
        state = step[seat]
        obs = state.get("observation") or {}
        day = int(obs.get("day", -1))
        if day not in CHECKPOINT_DAYS or int(obs.get("hour", -1)) != 0 or str(day) in checkpoints:
            continue
        farms = obs.get("farms") or []
        if seat >= len(farms):
            continue
        farm = farms[seat]
        crops = {}
        animals = {}
        for row in farm.get("tiles", []):
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if tile.get("crop"):
                    crops[tile["crop"]] = crops.get(tile["crop"], 0) + 1
                if tile.get("animal"):
                    animals[tile["animal"]] = animals.get(tile["animal"], 0) + 1
        checkpoints[str(day)] = {
            "bank": float(farm.get("money", 0)),
            "quadrants": len(farm.get("unlocked_quadrants", [])),
            "peak_hands": 0,
            "crops": crops,
            "animals": animals,
        }
    for step in steps:
        state = step[seat]
        obs = state.get("observation") or {}
        day = str(int(obs.get("day", -1)))
        farms = obs.get("farms") or []
        if day in checkpoints and seat < len(farms):
            checkpoints[day]["peak_hands"] = max(
                checkpoints[day]["peak_hands"], len(farms[seat].get("hands", []))
            )
    return checkpoints


def milestone_summary(games):
    if not games:
        return {}

    def rate(predicate):
        return round(sum(bool(predicate(game)) for game in games) / len(games), 3)

    return {
        "second_quadrant_by_day_7_rate": rate(
            lambda game: game.get("trajectory", {}).get("7", {}).get("quadrants", 0) >= 2
        ),
        "third_quadrant_by_day_12_rate": rate(
            lambda game: game.get("trajectory", {}).get("12", {}).get("quadrants", 0) >= 3
        ),
        "day_15_recurring_15_plus_rate": rate(
            lambda game: sum(
                game.get("trajectory", {}).get("15", {}).get("crops", {}).get(crop, 0)
                for crop in ("STRAWBERRY", "TOMATO")
            ) >= 15
        ),
        "day_15_livestock_8_plus_rate": rate(
            lambda game: sum(game.get("trajectory", {}).get("15", {}).get("animals", {}).values()) >= 8
        ),
        "day_24_bank_60000_plus_rate": rate(
            lambda game: game.get("trajectory", {}).get("24", {}).get("bank", 0) >= 60000
        ),
    }


def summary(games):
    margins = [game["margin"] for game in games]
    result = {
        "episodes": len(games),
        "wins": sum(game["result"] == "win" for game in games),
        "losses": sum(game["result"] == "loss" for game in games),
        "ties": sum(game["result"] == "tie" for game in games),
        "average_margin": round(statistics.mean(margins), 2) if margins else 0,
        "minimum_margin": round(min(margins), 2) if margins else 0,
        "runtime_failures": sum(any(status != "DONE" for status in game["statuses"]) for game in games),
        "suspicious_fallback_turns": sum(game["suspicious_fallback_turns"] for game in games),
        "maximum_action_ms": max((game["max_action_ms"] for game in games), default=0),
    }
    result["training_milestones"] = milestone_summary(games)
    return result


def write_result(path, artifact, games, expected, complete, persona_names):
    by_persona = {
        name: summary([game for game in games if game["persona"] == name])
        for name in persona_names
    }
    payload = {
        "complete": complete,
        "expected_episodes": expected,
        "candidate_artifact": artifact.name,
        "candidate_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "personas_are_inferred": True,
        "persona_caveat": "Public commitment emulations, not reconstructions of private code.",
        "training_method": "Bounded offline policy improvement: seeded games produce win/loss and trajectory milestone signals; code changes occur only between arena runs.",
        "summary": summary(games),
        "by_persona": by_persona,
        "games": games,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-artifact", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, default=100)
    parser.add_argument("--seeds-per-persona", type=int, default=1)
    parser.add_argument("--persona", action="append", choices=sorted(PERSONAS))
    parser.add_argument("--episode-limit", type=int, help="Run a stratified prefix of the arena schedule.")
    parser.add_argument("--max-wall-seconds", type=float, default=600.0)
    parser.add_argument("--action-failure-ms", type=float, default=700.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    artifact = args.candidate_artifact.resolve()
    persona_names = args.persona or list(PERSONAS)
    selected_personas = [(name, PERSONAS[name]) for name in persona_names]
    schedule = []
    # One seat from every persona is observed before the second-seat pass. This
    # makes small training budgets representative instead of spending the first
    # episodes on one opponent family.
    for seed_offset in range(args.seeds_per_persona):
        for seat in (0, 1):
            for persona_index, (persona_name, persona) in enumerate(selected_personas):
                seed = args.seed_start + persona_index * 100 + seed_offset
                schedule.append((persona_name, persona, seed, seat))
    if args.episode_limit is not None:
        schedule = schedule[: max(0, args.episode_limit)]
    expected = len(schedule)
    started = time.perf_counter()
    games = []
    kaggle, _ = load_environment()
    with tempfile.TemporaryDirectory(prefix="kaggriculture-persona-arena-") as temp_dir:
        candidate = load_artifact_agent(artifact, Path(temp_dir) / "candidate")
        for persona_name, persona, seed, seat in schedule:
            elapsed = time.perf_counter() - started
            if elapsed >= args.max_wall_seconds:
                write_result(args.output, artifact, games, expected, complete=False, persona_names=persona_names)
                print(json.dumps({"stopped": "wall_clock_cap", "checkpoint": f"{len(games)}/{expected}"}), flush=True)
                return
            action_times = []

            def timed_candidate(obs):
                action_started = time.perf_counter()
                action = candidate(obs)
                action_times.append((time.perf_counter() - action_started) * 1000)
                return action

            agents = [persona, persona]
            agents[seat] = timed_candidate
            env = kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
            env.run(agents)
            final = env.steps[-1]
            rewards = [float(state["reward"]) for state in final]
            margin = rewards[seat] - rewards[1 - seat]
            game = {
                "persona": persona_name,
                "seed": seed,
                "seat": seat,
                "result": "win" if margin > 0 else ("loss" if margin < 0 else "tie"),
                "candidate_reward": rewards[seat],
                "persona_reward": rewards[1 - seat],
                "margin": margin,
                "statuses": [state["status"] for state in final],
                "suspicious_fallback_turns": suspicious_fallback_turns(env.steps, seat),
                "max_action_ms": round(max(action_times, default=0), 3),
                "average_action_ms": round(statistics.mean(action_times), 3) if action_times else 0,
                "trajectory": trajectory_checkpoints(env.steps, seat),
            }
            if game["max_action_ms"] > args.action_failure_ms:
                game["latency_gate"] = "fail"
            games.append(game)
            write_result(args.output, artifact, games, expected, complete=False, persona_names=persona_names)
            print(json.dumps({
                "checkpoint": f"{len(games)}/{expected}",
                "persona": persona_name,
                "seed": seed,
                "seat": seat,
                "result": game["result"],
                "margin": margin,
                "max_action_ms": game["max_action_ms"],
            }), flush=True)

    write_result(args.output, artifact, games, expected, complete=True, persona_names=persona_names)
    print(json.dumps(summary(games), indent=2))


if __name__ == "__main__":
    main()
