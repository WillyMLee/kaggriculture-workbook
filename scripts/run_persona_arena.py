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


def summary(games):
    margins = [game["margin"] for game in games]
    return {
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


def write_result(path, artifact, games, expected, complete):
    by_persona = {
        name: summary([game for game in games if game["persona"] == name])
        for name in PERSONAS
    }
    payload = {
        "complete": complete,
        "expected_episodes": expected,
        "candidate_artifact": artifact.name,
        "candidate_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "personas_are_inferred": True,
        "persona_caveat": "Public commitment emulations, not reconstructions of private code.",
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
    parser.add_argument("--max-wall-seconds", type=float, default=600.0)
    parser.add_argument("--action-failure-ms", type=float, default=700.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    artifact = args.candidate_artifact.resolve()
    expected = len(PERSONAS) * args.seeds_per_persona * 2
    started = time.perf_counter()
    games = []
    kaggle, _ = load_environment()
    with tempfile.TemporaryDirectory(prefix="kaggriculture-persona-arena-") as temp_dir:
        candidate = load_artifact_agent(artifact, Path(temp_dir) / "candidate")
        for persona_index, (persona_name, persona) in enumerate(PERSONAS.items()):
            for seed_offset in range(args.seeds_per_persona):
                seed = args.seed_start + persona_index * 100 + seed_offset
                for seat in (0, 1):
                    elapsed = time.perf_counter() - started
                    if elapsed >= args.max_wall_seconds:
                        write_result(args.output, artifact, games, expected, complete=False)
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
                    }
                    if game["max_action_ms"] > args.action_failure_ms:
                        game["latency_gate"] = "fail"
                    games.append(game)
                    write_result(args.output, artifact, games, expected, complete=False)
                    print(json.dumps({
                        "checkpoint": f"{len(games)}/{expected}",
                        "persona": persona_name,
                        "seed": seed,
                        "seat": seat,
                        "result": game["result"],
                        "margin": margin,
                        "max_action_ms": game["max_action_ms"],
                    }), flush=True)

    write_result(args.output, artifact, games, expected, complete=True)
    print(json.dumps(summary(games), indent=2))


if __name__ == "__main__":
    main()
