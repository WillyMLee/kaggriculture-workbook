"""Extract and self-play the exact tar.gz that will be uploaded to Kaggle."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402


def load_artifact_agent(artifact: Path, destination: Path):
    with tarfile.open(artifact, "r:gz") as bundle:
        names = bundle.getnames()
        if "main.py" not in names:
            raise RuntimeError("artifact does not contain main.py at its root")
        root = destination.resolve()
        for member in bundle.getmembers():
            target = (root / member.name).resolve()
            if root not in target.parents or not member.isfile():
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                raise RuntimeError(f"unsafe artifact member: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise RuntimeError(f"could not read artifact member: {member.name}")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)

    sys.path.insert(0, str(destination))
    for module_name in ("agents.balanced_tempo", "agents"):
        sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location("frozen_submission_main", destination / "main.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load artifact entry point")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args()

    kaggle, _ = load_environment()
    with tempfile.TemporaryDirectory(prefix="kaggriculture-artifact-") as temp_dir:
        agent = load_artifact_agent(args.artifact.resolve(), Path(temp_dir))
        for seed in range(args.seeds):
            env = kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
            env.run([agent, agent])
            statuses = [state["status"] for state in env.steps[-1]]
            if statuses != ["DONE", "DONE"]:
                raise RuntimeError(f"seed {seed} failed: {statuses}")
            print(f"seed={seed} statuses={statuses}")

    print(f"artifact validation passed for {args.seeds} self-play seeds")


if __name__ == "__main__":
    main()
