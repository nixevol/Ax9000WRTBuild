from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

FEED_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$")
FEED_URL_RE = re.compile(
    r"^https://[a-zA-Z0-9.-]+(?::[0-9]{1,5})?/[a-zA-Z0-9._~%+/@:-]+$"
)
BRANCH_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$")
PACKAGE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9+_.-]{0,127}$")
SKIPPED_PACKAGE_DIRS = {
    "build",
    "cmake",
    "common",
    "docs",
    "examples",
    "files",
    "include",
    "patches",
    "scripts",
    "src",
    "test",
    "tests",
    "tools",
}
HIDDEN_PACKAGE_NAMES = {"uboot-envtools"}
PACKAGE_DIRECTORY_ALIASES = {
    "oaf": "kmod-oaf",
    "open-app-filter": "appfilter",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def normalize_feed(feed: dict[str, Any]) -> dict[str, Any]:
    name = str(feed.get("name", "")).strip()
    url = str(feed.get("url", "")).strip()
    branch = str(feed.get("branch", "")).strip() or "main"

    if not FEED_NAME_RE.fullmatch(name):
        raise ValueError(f"软件源名称无效: {name or '<empty>'}")
    if not FEED_URL_RE.fullmatch(url) or "/../" in url or url.endswith("/.."):
        raise ValueError(f"软件源 {name} 必须使用有效的 HTTPS Git 地址")
    if not BRANCH_RE.fullmatch(branch) or branch.startswith("-") or ".." in branch:
        raise ValueError(f"软件源 {name} 的分支名称无效")

    return {
        "name": name,
        "label": str(feed.get("label", name)).strip() or name,
        "url": url,
        "branch": branch,
        "kind": str(feed.get("kind", "custom")).strip() or "custom",
        "builtin": bool(feed.get("builtin", False)),
        "enabled": bool(feed.get("enabled", True)),
    }


def load_feed_sources(profile_dir: Path) -> list[dict[str, Any]]:
    data = read_json(profile_dir / "feeds.json")
    feeds = data.get("feeds", [])
    if not isinstance(feeds, list):
        return []

    result: list[dict[str, Any]] = []
    for feed in feeds:
        if isinstance(feed, dict):
            result.append(normalize_feed(feed))
    return result


def category_for(name: str) -> str:
    lowered = name.lower()
    if lowered.startswith("luci-theme-"):
        return "界面主题"
    if any(token in lowered for token in ("passwall", "openclash", "homeproxy", "ssr-plus", "nekobox", "v2ray", "xray", "nikki", "momo")):
        return "代理工具"
    if any(token in lowered for token in ("disk", "samba", "ksmbd", "nfs", "filebrowser", "webdav", "rclone", "minidlna", "transmission", "qbittorrent", "aria2")):
        return "存储与下载"
    if any(token in lowered for token in ("ddns", "dns", "adguard", "mosdns", "smartdns")):
        return "DNS 与域名"
    if any(token in lowered for token in ("vpn", "wireguard", "zerotier", "easytier", "frpc", "frps", "natmap", "tunnel", "socat")):
        return "远程与组网"
    if any(token in lowered for token in ("nlbwmon", "wrtbwmon", "netdata", "statistics", "monitor", "watchcat", "uptime", "htop")):
        return "监控与诊断"
    if any(token in lowered for token in ("docker", "dockerd", "container", "qemu", "lxc")):
        return "容器与虚拟化"
    if lowered.startswith("kmod-") or "firmware" in lowered:
        return "驱动与固件"
    if lowered.startswith("luci-app-"):
        return "LuCI 应用"
    if lowered.startswith("luci-proto-"):
        return "网络协议"
    if lowered.startswith("lib"):
        return "运行库"
    return "系统工具"


def infer_packages(paths: list[str], source: str) -> list[dict[str, str]]:
    packages: dict[str, dict[str, str]] = {}
    for raw_path in paths:
        path = PurePosixPath(raw_path.strip())
        if path.name != "Makefile" or len(path.parts) < 2:
            continue

        name = path.parent.name.strip()
        lowered = name.lower()
        if (
            lowered in SKIPPED_PACKAGE_DIRS
            or lowered in HIDDEN_PACKAGE_NAMES
            or lowered.startswith("luci-i18n-")
        ):
            continue
        name = PACKAGE_DIRECTORY_ALIASES.get(lowered, lowered)
        if not PACKAGE_NAME_RE.fullmatch(name):
            continue

        packages[name] = {
            "name": name,
            "title": "",
            "category": category_for(name),
            "source": source,
        }
    return list(packages.values())


def merge_packages(
    discovered: list[dict[str, Any]], curated: list[dict[str, Any]]
) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for item in discovered:
        name = str(item.get("name", "")).strip().lower()
        name = PACKAGE_DIRECTORY_ALIASES.get(name, name)
        if not name or name.lower() in HIDDEN_PACKAGE_NAMES:
            continue
        merged[name] = {
            "name": name,
            "title": str(item.get("title", "")).strip(),
            "category": str(item.get("category", "")).strip() or category_for(name),
            "source": str(item.get("source", "")).strip() or "profile",
        }

    for item in curated:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        current = merged.get(name, {})
        merged[name] = {
            "name": name,
            "title": str(item.get("title", "")).strip() or current.get("title", ""),
            "category": str(item.get("category", "")).strip()
            or current.get("category", category_for(name)),
            "source": current.get("source", str(item.get("source", "curated"))),
        }

    return sorted(merged.values(), key=lambda item: (item["category"], item["name"]))


def load_package_catalog(profile: str, profile_dir: Path, runtime_dir: Path) -> dict[str, Any]:
    curated_data = read_json(profile_dir / "package-catalog.json")
    curated = curated_data.get("packages", [])
    if not isinstance(curated, list):
        curated = []

    cache_path = runtime_dir / "package-catalog" / f"{profile}.json"
    cached_data = read_json(cache_path)
    discovered = cached_data.get("packages", [])
    if not isinstance(discovered, list):
        discovered = []

    packages = merge_packages(discovered, curated)
    return {
        "mode": "synced" if discovered else "curated",
        "generatedAt": cached_data.get("generatedAt"),
        "sources": cached_data.get("sources", []),
        "total": len(packages),
        "packages": packages,
    }


def run_git(arguments: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
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
        timeout=timeout,
        env=env,
    )
    if process.returncode != 0:
        detail = process.stderr.strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "Git 命令执行失败")
    return process.stdout


def sync_feed(feed: dict[str, Any], source_root: Path) -> tuple[str, list[dict[str, str]]]:
    fingerprint = hashlib.sha256(f"{feed['url']}\n{feed['branch']}".encode()).hexdigest()[:10]
    repository = source_root / f"{feed['name']}-{fingerprint}"

    if not (repository / ".git").exists():
        if repository.exists():
            shutil.rmtree(repository)
        run_git(
            [
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--no-checkout",
                "--single-branch",
                "--branch",
                feed["branch"],
                feed["url"],
                str(repository),
            ],
            timeout=180,
        )
        revision = run_git(["-C", str(repository), "rev-parse", "HEAD"]).strip()
    else:
        run_git(["-C", str(repository), "remote", "set-url", "origin", feed["url"]])
        run_git(
            ["-C", str(repository), "fetch", "--depth", "1", "origin", feed["branch"]],
            timeout=180,
        )
        revision = run_git(["-C", str(repository), "rev-parse", "FETCH_HEAD"]).strip()

    paths = run_git(
        ["-C", str(repository), "ls-tree", "-r", "--name-only", revision],
        timeout=60,
    ).splitlines()
    return revision, infer_packages(paths, feed["name"])


def refresh_package_catalog(
    profile: str,
    profile_dir: Path,
    runtime_dir: Path,
    requested_feeds: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(requested_feeds) > 12:
        raise ValueError("一次最多同步 12 个软件源")

    feeds = [normalize_feed(feed) for feed in requested_feeds]
    enabled_feeds = [feed for feed in feeds if feed["enabled"]]
    if not enabled_feeds:
        raise ValueError("至少需要启用一个软件源")

    source_root = runtime_dir / "catalog-sources" / profile
    source_root.mkdir(parents=True, exist_ok=True)
    discovered: dict[str, dict[str, str]] = {}
    source_status: list[dict[str, Any]] = []

    for feed in enabled_feeds:
        revision, packages = sync_feed(feed, source_root)
        for package in packages:
            discovered[package["name"]] = package
        source_status.append(
            {
                "name": feed["name"],
                "label": feed["label"],
                "revision": revision[:12],
                "count": len(packages),
            }
        )

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": source_status,
        "packages": list(discovered.values()),
    }
    cache_dir = runtime_dir / "package-catalog"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{profile}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return load_package_catalog(profile, profile_dir, runtime_dir)
