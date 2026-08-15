"""Audit a Kaggriculture tar.gz against the competition packaging contract."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tarfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--size-limit-mib", type=float, default=100.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    artifact = args.artifact.resolve()
    compressed_bytes = artifact.stat().st_size
    limit_bytes = int(args.size_limit_mib * 1024 * 1024)
    with tarfile.open(artifact, "r:gz") as bundle:
        members = bundle.getmembers()
        names = [member.name for member in members]
        unsafe = [
            member.name
            for member in members
            if not member.isfile()
            or Path(member.name).is_absolute()
            or ".." in Path(member.name).parts
        ]
        if "main.py" not in names:
            raise RuntimeError("main.py is not at the archive root")
        source_file = bundle.extractfile("main.py")
        if source_file is None:
            raise RuntimeError("main.py could not be read")
        source = source_file.read()

    tree = ast.parse(source, filename="main.py")
    imports = sorted({
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    })
    compile(source, "main.py", "exec")

    checks = {
        "under_size_limit": compressed_bytes <= limit_bytes,
        "main_at_root": "main.py" in names,
        "safe_members": not unsafe,
        "python_compiles": True,
        "single_file": names == ["main.py"],
    }
    payload = {
        "artifact": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "compressed_bytes": compressed_bytes,
        "uncompressed_main_bytes": len(source),
        "size_limit_bytes": limit_bytes,
        "size_limit_mib": args.size_limit_mib,
        "limit_used_percent": round(compressed_bytes / limit_bytes * 100, 6),
        "members": names,
        "imports": imports,
        "checks": checks,
        "ready": all(checks.values()),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
