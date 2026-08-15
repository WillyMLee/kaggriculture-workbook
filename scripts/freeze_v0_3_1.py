"""Reproduce the v0.3.1 closeout-fix checkpoint from the committed v0.3.0 source."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "3a67f39"
SOURCE_PATH = "agents/balanced_tempo.py"
OLD = '''    farms = obs.get("farms", [])
    player = int(obs.get("player", 0))
    private = obs.get("private", {}) or {}
'''
NEW = '''    farms = obs.get("farms", [])
    player = int(obs.get("player", 0))
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    private = obs.get("private", {}) or {}
'''


def main():
    source = subprocess.check_output(
        ["git", "show", f"{BASE_COMMIT}:{SOURCE_PATH}"],
        cwd=PROJECT_ROOT,
        text=True,
    )
    if source.count(OLD) != 1:
        raise RuntimeError("The frozen source no longer matches the expected v0.3.0 checkpoint")
    fixed = source.replace(OLD, NEW).encode("utf-8")

    artifact = PROJECT_ROOT / "artifacts" / "kaggriculture-v0.3.1.tar.gz"
    artifact.parent.mkdir(exist_ok=True)
    with tarfile.open(artifact, "w:gz") as bundle:
        info = tarfile.TarInfo("main.py")
        info.size = len(fixed)
        bundle.addfile(info, io.BytesIO(fixed))

    manifest = {
        "version": "v0.3.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "source": f"{BASE_COMMIT}:{SOURCE_PATH}",
        "change": "Define day and hour inside _policy so late execution cannot silently fall back.",
        "entry_point": "main.py:agent",
    }
    manifest_path = PROJECT_ROOT / "results" / "submission_v0_3_1_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
