#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


PACKAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9+_.-]{0,127}$")
URL_RE = re.compile(r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+\.git$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
RELATIVE_PATH_RE = re.compile(r"^[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*$")


def valid_relative_path(value: str) -> bool:
    return bool(
        RELATIVE_PATH_RE.fullmatch(value)
        and all(part not in {".", ".."} for part in value.split("/"))
    )


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    packages = data.get("packages") if isinstance(data, dict) else None
    if not isinstance(packages, list):
        raise ValueError("external package manifest must contain a packages list")

    result: list[dict[str, Any]] = []
    names: set[str] = set()
    for item in packages:
        if not isinstance(item, dict):
            raise ValueError("external package entries must be objects")
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        revision = str(item.get("revision", "")).strip().lower()
        executables = item.get("executables", [])
        if not PACKAGE_RE.fullmatch(name) or name in names:
            raise ValueError(f"invalid or duplicate external package name: {name}")
        if not URL_RE.fullmatch(url):
            raise ValueError(f"invalid external package URL: {url}")
        if not REVISION_RE.fullmatch(revision):
            raise ValueError(f"external package {name} requires a full commit revision")
        if not isinstance(executables, list) or any(
            not isinstance(value, str) or not valid_relative_path(value)
            for value in executables
        ):
            raise ValueError(f"invalid executable path for external package: {name}")
        names.add(name)
        result.append(
            {
                "name": name,
                "url": url,
                "revision": revision,
                "executables": executables,
            }
        )
    return result


def run_git(arguments: list[str], cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    process = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if process.returncode != 0:
        detail = process.stderr.strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "git command failed")
    return process.stdout.strip()


def install_packages(manifest: Path, source_dir: Path) -> list[str]:
    packages = load_manifest(manifest)
    package_root = source_dir.resolve() / "package" / "openwrt-local"
    package_root.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []

    for package in packages:
        destination = package_root / package["name"]
        if destination.exists():
            shutil.rmtree(destination)
        try:
            run_git(["clone", "--filter=blob:none", "--no-checkout", package["url"], str(destination)])
            run_git(["checkout", "--detach", package["revision"]], cwd=destination)
            actual_revision = run_git(["rev-parse", "HEAD"], cwd=destination).lower()
            if actual_revision != package["revision"]:
                raise RuntimeError(f"revision mismatch for {package['name']}")
            if not (destination / "Makefile").is_file():
                raise RuntimeError(f"external package has no Makefile: {package['name']}")
            for relative_path in package["executables"]:
                executable = destination / relative_path
                if not executable.is_file():
                    raise RuntimeError(
                        f"external package executable is missing: {package['name']}/{relative_path}"
                    )
                executable.chmod(0o755)
            shutil.rmtree(destination / ".git")
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
        installed.append(package["name"])
    return installed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()

    installed = install_packages(args.manifest.resolve(), args.source.resolve())
    if installed:
        print(f"Installed external packages: {', '.join(installed)}")


if __name__ == "__main__":
    main()
