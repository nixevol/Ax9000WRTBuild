#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


VLMCS_VERSION_BLOCK = """PKG_NAME:=vlmcsd
PKG_VERSION:=svn1113
PKG_RELEASE:=2

PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/Wind4/vlmcsd/tar.gz/$(PKG_VERSION)?
"""

VLMCS_APK_VERSION_BLOCK = """PKG_NAME:=vlmcsd
PKG_UPSTREAM_VERSION:=svn1113
PKG_VERSION:=1113
PKG_RELEASE:=2

PKG_SOURCE:=$(PKG_NAME)-$(PKG_UPSTREAM_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/Wind4/vlmcsd/tar.gz/$(PKG_UPSTREAM_VERSION)?
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_UPSTREAM_VERSION)
"""

PASSWALL_MENU_DEPENDENCY = "\tdepends on PACKAGE_$(PKG_NAME)"
PASSWALL_MENU_VISIBILITY = "\tvisible if PACKAGE_$(PKG_NAME)"


def patch_vlmcsd(source_dir: Path) -> bool:
    makefile = source_dir / "feeds" / "kiddin9" / "vlmcsd" / "Makefile"
    if not makefile.exists():
        return False

    text = makefile.read_text(encoding="utf-8")
    if VLMCS_APK_VERSION_BLOCK in text:
        return False
    if VLMCS_VERSION_BLOCK in text:
        makefile.write_text(
            text.replace(VLMCS_VERSION_BLOCK, VLMCS_APK_VERSION_BLOCK, 1),
            encoding="utf-8",
        )
        return True

    match = re.search(r"(?m)^PKG_VERSION:=(\S+)$", text)
    if match and match.group(1)[0].isdigit():
        return False
    version = match.group(1) if match else "<missing>"
    raise ValueError(f"unsupported vlmcsd package version: {version}")


def patch_passwall_menu_dependencies(source_dir: Path) -> list[str]:
    patched: list[str] = []
    for package in ("luci-app-passwall", "luci-app-passwall2"):
        makefile = source_dir / "feeds" / "kiddin9" / package / "Makefile"
        if not makefile.exists():
            continue
        text = makefile.read_text(encoding="utf-8")
        if PASSWALL_MENU_VISIBILITY in text:
            makefile.write_text(
                text.replace(PASSWALL_MENU_VISIBILITY + "\n", "", 1),
                encoding="utf-8",
            )
            patched.append(package)
            continue
        dependency_count = text.count(PASSWALL_MENU_DEPENDENCY)
        if dependency_count == 0:
            continue
        if dependency_count != 1:
            raise ValueError(f"unsupported {package} configuration menu")
        makefile.write_text(
            text.replace(PASSWALL_MENU_DEPENDENCY + "\n", "", 1),
            encoding="utf-8",
        )
        patched.append(package)
    return patched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()

    if patch_vlmcsd(args.source.resolve()):
        print("Patched vlmcsd version for APK compatibility")
    patched_passwall = patch_passwall_menu_dependencies(args.source.resolve())
    if patched_passwall:
        print(
            "Patched recursive PassWall menu dependencies: "
            + ", ".join(patched_passwall)
        )


if __name__ == "__main__":
    main()
