"""Build the exact multi-file Kaggle upload and record its checksum."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_FILES = (
    Path("main.py"),
    Path("agents/__init__.py"),
    Path("agents/balanced_tempo.py"),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0.2.0")
    args = parser.parse_args()

    artifact_dir = PROJECT_ROOT / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    artifact = artifact_dir / f"kaggriculture-{args.version}.tar.gz"

    with tarfile.open(artifact, "w:gz") as bundle:
        for relative in SUBMISSION_FILES:
            bundle.add(PROJECT_ROOT / relative, arcname=relative.as_posix())

    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "version": args.version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": artifact.name,
        "sha256": checksum,
        "files": [path.as_posix() for path in SUBMISSION_FILES],
        "entry_point": "main.py:agent",
    }
    manifest_path = PROJECT_ROOT / "results" / "submission_v0_2_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
