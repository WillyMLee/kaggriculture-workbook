"""Validate the root Kaggle submission entry point through self-play."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from main import agent as submission_agent  # noqa: E402
from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args()

    kaggle, _ = load_environment()
    for seed in range(args.seeds):
        env = kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
        env.run([submission_agent, submission_agent])
        final = env.steps[-1]
        statuses = [state["status"] for state in final]
        rewards = [float(state["reward"]) for state in final]
        if statuses != ["DONE", "DONE"]:
            raise RuntimeError(f"seed {seed} failed: {statuses}")
        print(f"seed={seed} statuses={statuses} banks={rewards}")

    print(f"submission validation passed for {args.seeds} self-play seeds")


if __name__ == "__main__":
    main()
