#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import ipaddress
import json
import re
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


FEED_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$")
FEED_URL_RE = re.compile(
    r"^https://[a-zA-Z0-9.-]+(?::[0-9]{1,5})?/[a-zA-Z0-9._~%+/@:-]+$"
)
BRANCH_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$")
PACKAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9+_.-]{0,127}$")
PACKAGE_ALIASES = {
    "libzip": "libzip-mbedtls",
    "oaf": "kmod-oaf",
    "open-app-filter": "appfilter",
}
HOSTNAME_RE = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)
QUICK_PATH_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
BRANDING_MARKER = "OpenWRT generated branding"
STATUS_SOURCE = Path(
    "feeds/luci/modules/luci-mod-status/htdocs/luci-static/resources/"
    "view/status/include/10_system.js"
)
STATUS_TARGET = Path("www/luci-static/resources/view/status/include/10_system.js")
THEME_SIGNATURE_PATCHES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "Argon": (
        (
            "feeds/kiddin9/luci-theme-argon/ucode/template/themes/argon/footer_login.ut",
            "usr/share/ucode/luci/template/themes/argon/footer_login.ut",
            "argon_link",
        ),
    ),
    "Bootstrap": (
        (
            "feeds/luci/themes/luci-theme-bootstrap/ucode/template/themes/bootstrap/footer.ut",
            "usr/share/ucode/luci/template/themes/bootstrap/footer.ut",
            "ucode_prefix",
        ),
    ),
    "Spectra": (
        (
            "feeds/kiddin9/luci-theme-spectra/luasrc/view/themes/spectra/sysauth.htm",
            "usr/lib/lua/luci/view/themes/spectra/sysauth.htm",
            "lua_prefix",
        ),
    ),
    "Aurora": (
        (
            "feeds/kiddin9/luci-theme-aurora/ucode/template/themes/aurora/sysauth.ut",
            "usr/share/ucode/luci/template/themes/aurora/sysauth.ut",
            "ucode_prefix",
        ),
        (
            "feeds/kiddin9/luci-theme-aurora/ucode/template/themes/aurora/footer.ut",
            "usr/share/ucode/luci/template/themes/aurora/footer.ut",
            "ucode_prefix",
        ),
    ),
    "Alpha": (
        (
            "feeds/kiddin9/luci-theme-alpha/template/footer.ut",
            "usr/share/ucode/luci/template/themes/alpha/footer.ut",
            "alpha_prepend",
        ),
    ),
    "Design": (
        (
            "feeds/kiddin9/luci-theme-design/ucode/template/themes/design/footer.ut",
            "usr/share/ucode/luci/template/themes/design/footer.ut",
            "ucode_link",
        ),
    ),
    "KuCat": (
        (
            "feeds/kiddin9/luci-theme-kucat/ucode/template/themes/kucat/footer.ut",
            "usr/share/ucode/luci/template/themes/kucat/footer.ut",
            "ucode_link",
        ),
    ),
    "Material": (
        (
            "feeds/luci/themes/luci-theme-material/ucode/template/themes/material/footer.ut",
            "usr/share/ucode/luci/template/themes/material/footer.ut",
            "ucode_link",
        ),
    ),
    "Material Design 3": (
        (
            "feeds/kiddin9/luci-theme-material3/ucode/template/themes/material3/footer.ut",
            "usr/share/ucode/luci/template/themes/material3/footer.ut",
            "ucode_prefix",
        ),
    ),
    "OpenWrt2020": (
        (
            "feeds/luci/themes/luci-theme-openwrt-2020/ucode/template/themes/openwrt2020/footer.ut",
            "usr/share/ucode/luci/template/themes/openwrt2020/footer.ut",
            "ucode_prefix",
        ),
    ),
    "OpenWrt": (
        (
            "feeds/luci/themes/luci-theme-openwrt/ucode/template/themes/openwrt.org/footer.ut",
            "usr/share/ucode/luci/template/themes/openwrt.org/footer.ut",
            "ucode_prefix",
        ),
    ),
}
LUCI_LINK_PATTERN = re.compile(
    r'<a(?P<attrs>[^>]*href="https://github\.com/openwrt/luci"[^>]*)>'
    r'Powered by (?P<label>\{\{ version\.luciname \}\} '
    r'\(\{\{ version\.luciversion \}\}\))</a>'
)


def load_options(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("build options must be a JSON object")
    return data


def load_presets(profile_dir: Path | None) -> dict[str, Any]:
    path = (
        profile_dir / "presets.json"
        if profile_dir is not None
        else Path(__file__).resolve().parents[1]
        / "profiles"
        / "ax9000"
        / "presets.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("profile presets must be a JSON object")
    return data


def preset_map(presets: dict[str, Any], name: str) -> dict[str, dict[str, Any]]:
    entries = presets.get(name, [])
    if not isinstance(entries, list):
        raise ValueError(f"preset group must be a list: {name}")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError(f"invalid preset entry: {name}")
        identifier = entry["id"]
        if identifier in result:
            raise ValueError(f"duplicate preset id: {identifier}")
        result[identifier] = entry
    return result


def preset_packages(entry: dict[str, Any], name: str = "packages") -> set[str]:
    packages = entry.get(name, [])
    if not isinstance(packages, list):
        raise ValueError(f"preset package group must be a list: {entry.get('id')}")
    result: set[str] = set()
    for package in packages:
        if not isinstance(package, str) or not PACKAGE_RE.fullmatch(package):
            raise ValueError(f"invalid preset package: {package}")
        result.add(package)
    return result


def option_list(
    options: dict[str, Any], name: str, *, max_items: int = 2048
) -> list[str] | None:
    value = options.get(name)
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > max_items:
        raise ValueError(f"{name} must be a list containing at most {max_items} entries")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{name} must contain strings")
        if item not in result:
            result.append(item)
    return result


def read_profile_packages(profile_dir: Path | None) -> tuple[set[str], set[str]]:
    if profile_dir is None:
        return set(), set()
    enabled: set[str] = set()
    disabled: set[str] = set()
    for raw in (profile_dir / "packages.list").read_text(encoding="utf-8").splitlines():
        token = raw.split("#", 1)[0].strip()
        if not token:
            continue
        package = token[1:] if token.startswith("-") else token
        if not PACKAGE_RE.fullmatch(package):
            raise ValueError(f"invalid profile package: {token}")
        (disabled if token.startswith("-") else enabled).add(package)
    return enabled, disabled


def validate_https_url(value: str, name: str, *, allow_empty: bool = True) -> str:
    value = value.strip().rstrip("/")
    if not value and allow_empty:
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in value)
    ):
        raise ValueError(f"{name} must be a plain HTTPS URL")
    return value


def option_string(
    options: dict[str, Any],
    name: str,
    default: str = "",
    *,
    max_length: int = 1024,
    allow_newlines: bool = False,
) -> str:
    value = options.get(name, default)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if len(value) > max_length or "\0" in value:
        raise ValueError(f"{name} is too long or contains a NUL byte")
    if not allow_newlines and ("\r" in value or "\n" in value):
        raise ValueError(f"{name} must be a single line")
    return value


def option_bool(options: dict[str, Any], name: str, default: bool = False) -> bool:
    value = options.get(name, default)
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def validate_ipv4(value: str, name: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError as error:
        raise ValueError(f"{name} must be a valid IPv4 address") from error


def branding_values(options: dict[str, Any]) -> tuple[str, str, str]:
    signature = option_string(options, "customSignature", max_length=256).strip()
    author_name = option_string(options, "authorName", max_length=128).strip()
    author_url = validate_https_url(
        option_string(options, "authorUrl", max_length=512), "authorUrl"
    )
    if bool(author_name) != bool(author_url):
        raise ValueError("authorName and authorUrl must be configured together")
    return signature, author_name, author_url


def replace_once(text: str, needle: str, replacement: str, path: Path) -> str:
    if text.count(needle) != 1:
        raise ValueError(f"branding anchor changed or is ambiguous: {path}")
    return text.replace(needle, replacement, 1)


def patch_signature_template(
    text: str, mode: str, signature: str, source_path: Path
) -> str:
    ucode_signature = (
        "{{ entityencode(" + json.dumps(signature, ensure_ascii=True) + ") }}"
    )
    marker = f"<!-- {BRANDING_MARKER} -->"

    if mode == "ucode_prefix":
        return replace_once(
            text,
            "Powered by",
            f"Powered by {marker}<span class=\"openwrt-signature\">"
            f"{ucode_signature}</span> /",
            source_path,
        )
    if mode == "lua_prefix":
        return replace_once(
            text,
            "Powered by",
            f"Powered by {marker}<span class=\"openwrt-signature\">"
            f"{html.escape(signature)}</span> |",
            source_path,
        )
    if mode == "alpha_prepend":
        needle = (
            '<a href="https://github.com/derisamedia/luci-theme-alpha">'
            "{{ version.distname }} {{ version.distversion }} | Alpha OS Theme v3.9.7</a>"
        )
        return replace_once(
            text,
            needle,
            f"{marker}<span class=\"openwrt-signature\">Powered by "
            f"{ucode_signature}</span> / {needle}",
            source_path,
        )
    if mode in {"ucode_link", "argon_link"}:
        matches = list(LUCI_LINK_PATTERN.finditer(text))
        if len(matches) != 1:
            raise ValueError(f"branding anchor changed or is ambiguous: {source_path}")
        match = matches[0]
        luci_link = f"<a{match.group('attrs')}>{match.group('label')}</a>"
        if mode == "argon_link":
            replacement = (
                f"{marker}<span class=\"luci-link openwrt-signature\" "
                f"style=\"color: var(--primary)\">Powered by "
                f"{ucode_signature}</span>\n\t\t{luci_link}"
            )
        else:
            replacement = (
                f"{marker}<span class=\"openwrt-signature\">Powered by "
                f"{ucode_signature}</span> / {luci_link}"
            )
        return text[: match.start()] + replacement + text[match.end() :]
    raise ValueError(f"unsupported branding patch mode: {mode}")


def clear_generated_overlay(path: Path) -> None:
    if not path.exists():
        return
    if BRANDING_MARKER not in path.read_text(encoding="utf-8"):
        raise ValueError(f"branding overlay conflicts with an existing file: {path}")
    path.unlink()


def configure_branding(
    options_path: Path, source_dir: Path, profile_dir: Path | None = None
) -> None:
    options = load_options(options_path)
    presets = load_presets(profile_dir)
    themes = preset_map(presets, "themes")
    theme = option_string(options, "theme", "Argon", max_length=64)
    if theme not in themes or theme not in THEME_SIGNATURE_PATCHES:
        raise ValueError(f"unsupported theme branding: {theme}")
    signature, author_name, author_url = branding_values(options)

    files_dir = source_dir / "files"
    status_target = files_dir / STATUS_TARGET
    clear_generated_overlay(status_target)
    for patches in THEME_SIGNATURE_PATCHES.values():
        for _, target, _ in patches:
            clear_generated_overlay(files_dir / target)

    if author_url:
        status_source = source_dir / STATUS_SOURCE
        if not status_source.is_file():
            raise ValueError(f"LuCI status source not found: {status_source}")
        status_text = status_source.read_text(encoding="utf-8")
        closing = "\n\t\t];"
        author_fields = (
            ",\n\t\t\t// "
            + BRANDING_MARKER
            + "\n\t\t\t(document.documentElement.lang || '').toLowerCase().startsWith('zh') "
            "? '固件作者' : 'Firmware Author',\n"
            "\t\t\tE('a', {\n"
            f"\t\t\t\thref: {json.dumps(author_url)},\n"
            "\t\t\t\ttarget: '_blank',\n"
            "\t\t\t\trel: 'noopener noreferrer'\n"
            f"\t\t\t}}, [{json.dumps(author_name, ensure_ascii=False)}])"
        )
        status_text = replace_once(
            status_text, closing, author_fields + closing, status_source
        )
        status_target.parent.mkdir(parents=True, exist_ok=True)
        status_target.write_text(status_text, encoding="utf-8")

    if signature:
        for source, target, mode in THEME_SIGNATURE_PATCHES[theme]:
            source_path = source_dir / source
            if not source_path.is_file():
                raise ValueError(f"theme branding source not found: {source_path}")
            patched = patch_signature_template(
                source_path.read_text(encoding="utf-8"), mode, signature, source_path
            )
            target_path = files_dir / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(patched, encoding="utf-8")


def configure_feeds(options_path: Path, source_dir: Path) -> None:
    options = load_options(options_path)
    feeds = options.get("feeds")
    if feeds is None or feeds == []:
        return
    if not isinstance(feeds, list) or len(feeds) > 12:
        raise ValueError("feeds must be a list containing at most 12 entries")

    normalized: list[tuple[str, str, str, bool]] = []
    seen: set[str] = set()
    for item in feeds:
        if not isinstance(item, dict):
            raise ValueError("invalid feed entry")
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        branch = str(item.get("branch", "")).strip() or "main"
        enabled = item.get("enabled", True)
        if not FEED_NAME_RE.fullmatch(name) or name in seen:
            raise ValueError(f"invalid or duplicate feed name: {name}")
        if not FEED_URL_RE.fullmatch(url) or "/../" in url or url.endswith("/.."):
            raise ValueError(f"invalid HTTPS feed URL: {name}")
        if not BRANCH_RE.fullmatch(branch) or branch.startswith("-") or ".." in branch:
            raise ValueError(f"invalid feed branch: {name}")
        if type(enabled) is not bool:
            raise ValueError(f"feed enabled flag must be boolean: {name}")
        seen.add(name)
        normalized.append((name, url, branch, enabled))

    config_path = source_dir / "feeds.conf.default"
    lines = config_path.read_text(encoding="utf-8").splitlines()
    configured_names = {item[0] for item in normalized}
    source_line = re.compile(r"^\s*src-[^\s]+\s+([^\s]+)\s+")
    kept = [
        line
        for line in lines
        if not (
            (match := source_line.match(line))
            and match.group(1) in configured_names
        )
    ]
    kept.extend(
        f"src-git {name} {url};{branch}"
        for name, url, branch, enabled in normalized
        if enabled
    )
    config_path.write_text("\n".join(kept) + "\n", encoding="utf-8")



def configure_ipv6_default(source_dir: Path, enabled: bool) -> None:
    config_path = source_dir / "config" / "Config-build.in"
    text = config_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?m)^(?P<indent>[ \t]*)config IPV6\n"
        r"(?P<value_indent>[ \t]*)def_bool [yn][ \t]*$"
    )
    match = pattern.search(text)
    if match is None:
        raise ValueError("config IPV6 default was not found")
    replacement = (
        f"{match.group('indent')}config IPV6\n"
        f"{match.group('value_indent')}def_bool {'y' if enabled else 'n'}"
    )
    config_path.write_text(pattern.sub(replacement, text, count=1), encoding="utf-8")


def parse_packages(options: dict[str, Any]) -> tuple[set[str], set[str]]:
    enabled: set[str] = set()

    selected = options.get("selectedPackages", [])
    if not isinstance(selected, list) or len(selected) > 2048:
        raise ValueError("selectedPackages must be a list containing at most 2048 entries")
    for package in selected:
        if not isinstance(package, str) or not PACKAGE_RE.fullmatch(package):
            raise ValueError(f"invalid selected package name: {package}")
        enabled.add(PACKAGE_ALIASES.get(package, package))

    return enabled, set()


def expand_package_groups(packages: set[str], presets: dict[str, Any]) -> None:
    groups = presets.get("packageGroups", {})
    if not isinstance(groups, dict):
        raise ValueError("packageGroups must be an object")

    for primary, members in groups.items():
        if not isinstance(primary, str) or not PACKAGE_RE.fullmatch(primary):
            raise ValueError("invalid package group name")
        if not isinstance(members, list):
            raise ValueError(f"package group {primary} must be a list")
        normalized: set[str] = set()
        for member in members:
            if not isinstance(member, str) or not PACKAGE_RE.fullmatch(member):
                raise ValueError(f"invalid package in group {primary}: {member}")
            normalized.add(PACKAGE_ALIASES.get(member, member))
        if primary in packages:
            packages.update(normalized)


def config_symbol(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("CONFIG_") and "=" in stripped:
        return stripped.split("=", 1)[0]
    if stripped.startswith("# CONFIG_") and stripped.endswith(" is not set"):
        return stripped[2:].split(" ", 1)[0]
    return ""


def parse_ports(raw: str, enabled: bool) -> list[int]:
    tokens = raw.split()
    if len(tokens) > 128:
        raise ValueError("exposedPorts contains too many entries")
    ports: list[int] = []
    for token in tokens:
        if not token.isascii() or not token.isdigit():
            raise ValueError(f"invalid WAN port: {token}")
        port = int(token)
        if not 1 <= port <= 65535:
            raise ValueError(f"WAN port out of range: {token}")
        if port not in ports:
            ports.append(port)
    if enabled and not ports:
        raise ValueError("at least one WAN port is required when public access is enabled")
    return ports


def render_build_options(
    options_path: Path, source_dir: Path, profile_dir: Path | None = None
) -> None:
    options = load_options(options_path)
    presets = load_presets(profile_dir)
    wifi_mode = option_string(options, "wifiMode", "band", max_length=16)
    if wifi_mode not in {"band", "unified", "wizard"}:
        raise ValueError("wifiMode must be band, unified, or wizard")
    requested, explicitly_disabled = parse_packages(options)
    profile_packages, profile_disabled = read_profile_packages(profile_dir)

    selected_base = option_list(options, "basePackages", max_items=512)
    if selected_base is None:
        selected_base_set = set(profile_packages)
    else:
        selected_base_set: set[str] = set()
        for package in selected_base:
            if not PACKAGE_RE.fullmatch(package):
                raise ValueError(f"invalid base package name: {package}")
            if profile_packages and package not in profile_packages:
                raise ValueError(f"unknown base package: {package}")
            selected_base_set.add(package)
    requested.update(selected_base_set)
    expand_package_groups(requested, presets)

    theme = option_string(options, "theme", "Argon", max_length=64)
    themes = preset_map(presets, "themes")
    if theme not in themes:
        raise ValueError(f"unsupported theme: {theme}")
    theme_entry = themes[theme]
    theme_packages = preset_packages(theme_entry)
    media_url = str(theme_entry.get("mediaUrl", "")).strip()
    if not media_url.startswith("/luci-static/"):
        raise ValueError(f"invalid theme media URL: {theme}")

    web_server = option_string(options, "webServer", "Nginx", max_length=32)
    web_servers = preset_map(presets, "webServers")
    if web_server not in web_servers:
        raise ValueError(f"unsupported web server: {web_server}")
    web_entry = web_servers[web_server]
    https_admin = option_bool(options, "httpsAdmin")
    if https_admin and not bool(web_entry.get("supportsHttps", False)):
        raise ValueError(f"{web_server} does not support the HTTPS admin option")

    required_packages = presets.get("requiredPackages", [])
    if not isinstance(required_packages, list):
        raise ValueError("requiredPackages must be a list")
    required = set()
    for package in required_packages:
        if not isinstance(package, str) or not PACKAGE_RE.fullmatch(package):
            raise ValueError(f"invalid required package: {package}")
        required.add(package)
    required.update(theme_packages)
    if wifi_mode == "wizard":
        required.add("luci-app-wizard")

    disabled = set(explicitly_disabled) | profile_disabled
    disabled.update(profile_packages - selected_base_set)

    all_theme_packages = set().union(
        *(preset_packages(entry) for entry in themes.values())
    )
    disabled.update(all_theme_packages - theme_packages)

    web_packages = preset_packages(web_entry)
    if https_admin:
        web_packages.update(preset_packages(web_entry, "httpsPackages"))
    required.update(web_packages)
    all_web_packages = {
        "luci",
        "luci-ssl",
        "luci-nginx",
        "luci-lighttpd",
        "lighttpd-mod-openssl",
    }
    for entry in web_servers.values():
        all_web_packages.update(preset_packages(entry))
        all_web_packages.update(preset_packages(entry, "httpsPackages"))
    disabled.update(all_web_packages - web_packages)

    features = preset_map(presets, "features")
    all_feature_packages: set[str] = set()
    enabled_feature_packages: set[str] = set()
    for identifier, entry in features.items():
        packages = preset_packages(entry)
        all_feature_packages.update(packages)
        if option_bool(options, identifier):
            enabled_feature_packages.update(packages)
    required.update(enabled_feature_packages)

    firewall_backend = option_string(
        options, "firewallBackend", "firewall4", max_length=32
    )
    firewall_backends = preset_map(presets, "firewallBackends")
    if firewall_backend not in firewall_backends:
        raise ValueError(f"unsupported firewall backend: {firewall_backend}")
    firewall_entry = firewall_backends[firewall_backend]
    firewall_packages = preset_packages(firewall_entry)
    required.update(firewall_packages)
    all_firewall_packages: set[str] = set()
    for entry in firewall_backends.values():
        all_firewall_packages.update(preset_packages(entry))
        all_firewall_packages.update(preset_packages(entry, "disabledPackages"))
    disabled.update(all_firewall_packages - firewall_packages)
    disabled.update(preset_packages(firewall_entry, "disabledPackages"))

    proxies = preset_map(presets, "proxies")
    proxy_cores = preset_map(presets, "proxyCores")
    selected_proxies = option_list(options, "proxyPresets", max_items=16) or []
    selected_proxy_cores = option_list(options, "proxyCores", max_items=16) or []
    all_proxy_packages: set[str] = set()
    enabled_proxy_packages: set[str] = set()
    for entry in proxies.values():
        all_proxy_packages.update(preset_packages(entry))
    for identifier in selected_proxies:
        entry = proxies.get(identifier)
        if entry is None:
            raise ValueError(f"unsupported proxy preset: {identifier}")
        compatible = entry.get("firewallBackends", [])
        if not isinstance(compatible, list) or firewall_backend not in compatible:
            raise ValueError(
                f"proxy preset {identifier} is incompatible with {firewall_backend}"
            )
        enabled_proxy_packages.update(preset_packages(entry))
    for identifier in selected_proxy_cores:
        entry = proxy_cores.get(identifier)
        if entry is None:
            raise ValueError(f"unsupported proxy core: {identifier}")
        enabled_proxy_packages.update(preset_packages(entry))
    for entry in proxy_cores.values():
        all_proxy_packages.update(preset_packages(entry))
    required.update(enabled_proxy_packages)
    disabled.update(all_proxy_packages - enabled_proxy_packages)

    languages = preset_map(presets, "languages")
    installed_languages = option_list(
        options, "installedLanguages", max_items=8
    ) or ["en"]
    if "en" not in installed_languages:
        raise ValueError("English is built into LuCI and must remain enabled")
    for identifier in installed_languages:
        if identifier not in languages:
            raise ValueError(f"unsupported language: {identifier}")
    default_language = option_string(
        options, "defaultLanguage", "auto", max_length=16
    )
    if default_language not in {"auto", *languages.keys()}:
        raise ValueError(f"unsupported default language: {default_language}")
    if default_language != "auto" and default_language not in installed_languages:
        raise ValueError("default language must be installed")

    all_language_packages: set[str] = set()
    enabled_language_packages: set[str] = set()
    for identifier, entry in languages.items():
        packages = preset_packages(entry)
        all_language_packages.update(packages)
        if identifier in installed_languages:
            enabled_language_packages.update(packages)
    for entry in features.values():
        all_language_packages.update(preset_packages(entry, "zhCnPackages"))
    for entry in proxies.values():
        all_language_packages.update(preset_packages(entry, "zhCnPackages"))
    base_translations = presets.get("zhCnPackageTranslations", {})
    if not isinstance(base_translations, dict):
        raise ValueError("zhCnPackageTranslations must be an object")
    for base_package, translation in base_translations.items():
        if (
            not isinstance(base_package, str)
            or not PACKAGE_RE.fullmatch(base_package)
            or not isinstance(translation, str)
            or not PACKAGE_RE.fullmatch(translation)
        ):
            raise ValueError("invalid base package translation mapping")
        all_language_packages.add(translation)
        if "zh_cn" in installed_languages and (
            base_package in selected_base_set or base_package in requested
        ):
            enabled_language_packages.add(translation)
    if "zh_cn" in installed_languages:
        for identifier, entry in features.items():
            if option_bool(options, identifier):
                enabled_language_packages.update(
                    preset_packages(entry, "zhCnPackages")
                )
        for identifier in selected_proxies:
            enabled_language_packages.update(
                preset_packages(proxies[identifier], "zhCnPackages")
            )
        if wifi_mode == "wizard":
            enabled_language_packages.add("luci-i18n-wizard-zh-cn")
    required.update(enabled_language_packages)
    disabled.update(all_language_packages - enabled_language_packages)

    ipv6 = option_bool(options, "ipv6")
    proxy_requires_kernel_ipv6 = any(
        bool(proxies[identifier].get("requiresKernelIpv6", False))
        for identifier in selected_proxies
    )
    kernel_ipv6 = (
        ipv6
        or bool(firewall_entry.get("requiresKernelIpv6", False))
        or proxy_requires_kernel_ipv6
    )
    configure_ipv6_default(source_dir, kernel_ipv6)
    if ipv6:
        required.update({"ds-lite", "odhcp6c", "odhcpd-ipv6only"})
        required.add("luci-proto-ipv6")
    else:
        disabled.update(
            {"ds-lite", "luci-proto-ipv6", "odhcp6c", "odhcpd-ipv6only"}
        )

    sysctl_path = source_dir / "files" / "etc" / "sysctl.d" / "99-disable-ipv6.conf"
    if ipv6:
        sysctl_path.unlink(missing_ok=True)
    else:
        sysctl_path.parent.mkdir(parents=True, exist_ok=True)
        sysctl_path.write_text(
            "net.ipv6.conf.all.disable_ipv6=1\n"
            "net.ipv6.conf.default.disable_ipv6=1\n"
            "net.ipv6.conf.lo.disable_ipv6=1\n",
            encoding="utf-8",
        )

    managed_alternatives = (
        (all_theme_packages - theme_packages)
        | (all_web_packages - web_packages)
        | (all_firewall_packages - firewall_packages)
        | (all_feature_packages - enabled_feature_packages)
        | (all_proxy_packages - enabled_proxy_packages)
        | (all_language_packages - enabled_language_packages)
    )
    conflicting_packages = (requested - required) & managed_alternatives
    if conflicting_packages:
        names = ", ".join(sorted(conflicting_packages))
        raise ValueError(f"packages conflict with managed selections: {names}")
    for identifier, entry in proxies.items():
        packages = entry.get("packages", [])
        frontend = packages[0] if isinstance(packages, list) and packages else ""
        if frontend in requested and identifier not in selected_proxies:
            raise ValueError(f"use proxyPresets to select {frontend}")

    disabled.difference_update(required)
    enabled = (requested | required) - disabled
    controlled_packages = (
        enabled
        | disabled
        | all_proxy_packages
        | all_theme_packages
        | all_web_packages
        | all_feature_packages
        | all_firewall_packages
        | all_language_packages
    )
    controlled_symbols = {f"CONFIG_PACKAGE_{package}" for package in controlled_packages}
    controlled_symbols.add("CONFIG_IPV6")
    controlled_symbols.add("CONFIG_LUCI_LANG_zh_Hans")

    config_path = source_dir / ".config"
    existing_lines = config_path.read_text(encoding="utf-8").splitlines()
    config_path.write_text(
        "\n".join(
            line for line in existing_lines if config_symbol(line) not in controlled_symbols
        )
        + "\n",
        encoding="utf-8",
    )

    config_lines = [f"CONFIG_PACKAGE_{package}=y" for package in sorted(enabled)]
    config_lines.extend(
        f"# CONFIG_PACKAGE_{package} is not set" for package in sorted(disabled)
    )
    config_lines.append(
        "CONFIG_LUCI_LANG_zh_Hans=y"
        if "zh_cn" in installed_languages
        else "# CONFIG_LUCI_LANG_zh_Hans is not set"
    )
    config_lines.append("CONFIG_IPV6=y" if kernel_ipv6 else "# CONFIG_IPV6 is not set")
    (source_dir / ".build-options.config").write_text(
        "\n".join(config_lines) + "\n", encoding="utf-8"
    )

    lan_ip = validate_ipv4(
        option_string(options, "lanIp", "192.168.32.1", max_length=15), "lanIp"
    )
    netmask = option_string(options, "netmask", "255.255.255.0", max_length=15)
    try:
        ipaddress.IPv4Network(f"0.0.0.0/{netmask}")
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as error:
        raise ValueError("netmask must be a valid IPv4 netmask") from error

    password = option_string(options, "rootPassword", "password", max_length=128)
    if not password:
        raise ValueError("rootPassword cannot be empty")
    hostname = option_string(options, "hostname", "OpenWRT", max_length=63)
    if not HOSTNAME_RE.fullmatch(hostname):
        raise ValueError("hostname is invalid")
    quick_path = option_string(options, "quickPath", "openwrt", max_length=64).strip("/")
    if not quick_path:
        quick_path = "openwrt"
    if not QUICK_PATH_RE.fullmatch(quick_path):
        raise ValueError("quickPath must be a safe path segment")

    bypass_mode = option_bool(options, "bypassMode")
    gateway = option_string(options, "ipv4Gateway", max_length=15)
    if gateway:
        gateway = validate_ipv4(gateway, "ipv4Gateway")
    if bypass_mode and not gateway:
        raise ValueError("ipv4Gateway is required in bypass mode")

    wifi_ssid = option_string(options, "wifiSsid", max_length=64)
    if len(wifi_ssid.encode("utf-8")) > 32:
        raise ValueError("wifiSsid must not exceed 32 UTF-8 bytes")
    if (
        wifi_mode == "band"
        and wifi_ssid
        and len(f"{wifi_ssid}_2.4G".encode("utf-8")) > 32
    ):
        raise ValueError(
            "wifiSsid with the _2.4G suffix must not exceed 32 UTF-8 bytes"
        )
    wifi_password = option_string(options, "wifiPassword", max_length=63)
    if wifi_password and not 8 <= len(wifi_password.encode("utf-8")) <= 63:
        raise ValueError("wifiPassword must contain 8 to 63 UTF-8 bytes")

    pppoe_user = option_string(options, "pppoeUser", max_length=128)
    pppoe_password = option_string(options, "pppoePassword", max_length=128)
    branding_values(options)

    runtime_mirrors = preset_map(presets, "runtimeMirrors")
    runtime_mirror = option_string(
        options, "runtimeMirror", "build-default", max_length=32
    )
    if runtime_mirror not in runtime_mirrors:
        raise ValueError(f"unsupported runtime mirror: {runtime_mirror}")
    if runtime_mirror == "custom":
        custom_mirror_url = validate_https_url(
            option_string(options, "customMirrorUrl", max_length=512),
            "customMirrorUrl",
        )
        if not custom_mirror_url:
            raise ValueError("customMirrorUrl is required for a custom mirror")
        runtime_mirror_url = custom_mirror_url
    else:
        runtime_mirror_url = validate_https_url(
            str(runtime_mirrors[runtime_mirror].get("baseUrl", "")),
            "runtime mirror URL",
        )
    runtime_mirror_sed = (
        runtime_mirror_url.replace("\\", "\\\\")
        .replace("&", "\\&")
        .replace("#", "\\#")
    )
    unpublished_runtime_feeds = presets.get("unpublishedRuntimeFeeds", [])
    if not isinstance(unpublished_runtime_feeds, list):
        raise ValueError("unpublishedRuntimeFeeds must be a list")
    if len(unpublished_runtime_feeds) > 32:
        raise ValueError("unpublishedRuntimeFeeds contains too many entries")
    for feed in unpublished_runtime_feeds:
        if not isinstance(feed, str) or not FEED_NAME_RE.fullmatch(feed):
            raise ValueError(f"invalid unpublished runtime feed: {feed}")
    init_script = option_string(
        options, "initScript", max_length=65536, allow_newlines=True
    )
    expose_public = option_bool(options, "exposePublic")
    ports = parse_ports(
        option_string(options, "exposedPorts", max_length=1024), expose_public
    )

    sq = lambda value: shlex.quote(str(value))
    uci = [
        "#!/bin/sh",
        "set +e",
        f"uci -q set system.@system[0].hostname={sq(hostname)}",
        "uci -q commit system",
        f"printf '%s\\n%s\\n' {sq(password)} {sq(password)} | passwd root",
        f"uci -q set network.lan.ipaddr={sq(lan_ip)}",
        f"uci -q set network.lan.netmask={sq(netmask)}",
        f"uci -q set luci.main.lang={sq(default_language)}",
    ]

    if bypass_mode:
        uci.extend(
            [
                f"uci -q set network.lan.gateway={sq(gateway)}",
                f"uci -q set network.lan.dns={sq(gateway)}",
            ]
        )
    if pppoe_user:
        uci.extend(
            [
                "uci -q set network.wan.proto='pppoe'",
                f"uci -q set network.wan.username={sq(pppoe_user)}",
                f"uci -q set network.wan.password={sq(pppoe_password)}",
            ]
        )
    if not ipv6:
        uci.extend(
            [
                "uci -q delete network.wan6",
                "uci -q delete network.globals.ula_prefix",
                "uci -q set dhcp.lan.ra='disabled'",
                "uci -q set dhcp.lan.dhcpv6='disabled'",
                "uci -q set dhcp.lan.ndp='disabled'",
                "/etc/init.d/odhcpd disable 2>/dev/null",
                "sysctl -p /etc/sysctl.d/99-disable-ipv6.conf >/dev/null 2>&1",
            ]
        )

    uci.append(
        "uci -q set dhcp.lan.ignore='0'"
        if option_bool(options, "dhcpServer", True)
        else "uci -q set dhcp.lan.ignore='1'"
    )

    if wifi_ssid and wifi_mode != "wizard":
        uci.extend(
            [
                f"wifi_ssid={sq(wifi_ssid)}",
                f"wifi_password={sq(wifi_password)}",
                f"wifi_mode={sq(wifi_mode)}",
                "uci -q show wireless | sed -n 's/^wireless\\.\\([^=]*\\)=wifi-device$/\\1/p' | while IFS= read -r section; do",
                "  uci -q set \"wireless.$section.disabled=0\"",
                "done",
                "uci -q show wireless | sed -n 's/^wireless\\.\\([^=]*\\)=wifi-iface$/\\1/p' | while IFS= read -r section; do",
                "  mode=\"$(uci -q get \"wireless.$section.mode\")\"",
                "  [ \"$mode\" = 'ap' ] || continue",
                "  ssid=\"$wifi_ssid\"",
                "  encryption='sae-mixed'",
                "  if [ \"$wifi_mode\" = 'band' ]; then",
                "    device=\"$(uci -q get \"wireless.$section.device\")\"",
                "    band=\"$(uci -q get \"wireless.$device.band\")\"",
                "    hwmode=\"$(uci -q get \"wireless.$device.hwmode\")\"",
                "    case \"$band:$hwmode\" in",
                "      2g:*|*:11g|*:11ng) ssid=\"${wifi_ssid}_2.4G\"; encryption='psk2' ;;",
                "      5g:*|6g:*|*:11a|*:11na|*:11ac|*:11axa) ssid=\"${wifi_ssid}_5G\" ;;",
                "    esac",
                "  fi",
                "  uci -q set \"wireless.$section.disabled=0\"",
                "  uci -q set \"wireless.$section.ssid=$ssid\"",
                "  if [ -n \"$wifi_password\" ]; then",
                "    uci -q set \"wireless.$section.encryption=$encryption\"",
                "    uci -q set \"wireless.$section.key=$wifi_password\"",
                "  else",
                "    uci -q set \"wireless.$section.encryption=none\"",
                "    uci -q delete \"wireless.$section.key\"",
                "  fi",
                "done",
            ]
        )

    if expose_public:
        for port in ports:
            uci.extend(
                [
                    f"uci -q set firewall.open_{port}=rule",
                    f"uci -q set firewall.open_{port}.name='Allow-WAN-{port}'",
                    f"uci -q set firewall.open_{port}.src='wan'",
                    f"uci -q set firewall.open_{port}.dest_port='{port}'",
                    f"uci -q set firewall.open_{port}.proto='tcp udp'",
                    f"uci -q set firewall.open_{port}.target='ACCEPT'",
                ]
            )

    if web_server == "Nginx":
        uci.extend(
            [
                "uci -q delete nginx._lan.listen",
                "uci -q delete nginx._redirect2ssl.listen",
            ]
        )
        if https_admin:
            uci.extend(
                [
                    "uci -q set nginx._lan=server",
                    "uci -q add_list nginx._lan.listen='443 ssl default_server'",
                    "uci -q set nginx._lan.uci_manage_ssl='self-signed'",
                    "uci -q set nginx._lan.ssl_certificate='/etc/nginx/conf.d/_lan.crt'",
                    "uci -q set nginx._lan.ssl_certificate_key='/etc/nginx/conf.d/_lan.key'",
                    "uci -q set nginx._redirect2ssl=server",
                    "uci -q add_list nginx._redirect2ssl.listen='80'",
                ]
            )
            if ipv6:
                uci.extend(
                    [
                        "uci -q add_list nginx._lan.listen='[::]:443 ssl default_server'",
                        "uci -q add_list nginx._redirect2ssl.listen='[::]:80'",
                    ]
                )
        else:
            uci.extend(
                [
                    "uci -q set nginx._lan=server",
                    "uci -q add_list nginx._lan.listen='80 default_server'",
                    "uci -q delete nginx._lan.uci_manage_ssl",
                    "uci -q delete nginx._lan.ssl_certificate",
                    "uci -q delete nginx._lan.ssl_certificate_key",
                    "uci -q set nginx._redirect2ssl=disable",
                ]
            )
            if ipv6:
                uci.append("uci -q add_list nginx._lan.listen='[::]:80 default_server'")
    elif web_server == "Uhttpd":
        uci.extend(
            [
                "uci -q delete uhttpd.main.listen_http",
                "uci -q delete uhttpd.main.listen_https",
                "uci -q add_list uhttpd.main.listen_http='0.0.0.0:80'",
            ]
        )
        if ipv6:
            uci.append("uci -q add_list uhttpd.main.listen_http='[::]:80'")
        if https_admin:
            uci.extend(
                [
                    "uci -q add_list uhttpd.main.listen_https='0.0.0.0:443'",
                    "uci -q set uhttpd.main.redirect_https='1'",
                ]
            )
            if ipv6:
                uci.append("uci -q add_list uhttpd.main.listen_https='[::]:443'")
        else:
            uci.append("uci -q set uhttpd.main.redirect_https='0'")

    uci.extend(
        [
            f"uci -q set luci.main.mediaurlbase={sq(media_url)}",
            "uci -q commit network",
            "uci -q commit dhcp",
            "uci -q commit wireless",
            "uci -q commit firewall",
            "uci -q commit luci",
            "uci -q commit nginx",
            "uci -q commit uhttpd",
        ]
    )
    if web_server == "Nginx":
        uci.extend(
            [
                "/etc/init.d/uhttpd disable 2>/dev/null",
                "/etc/init.d/lighttpd disable 2>/dev/null",
                "/etc/init.d/nginx enable 2>/dev/null",
            ]
        )
    elif web_server == "Uhttpd":
        uci.extend(
            [
                "/etc/init.d/nginx disable 2>/dev/null",
                "/etc/init.d/lighttpd disable 2>/dev/null",
                "/etc/init.d/uhttpd enable 2>/dev/null",
            ]
        )
    else:
        uci.extend(
            [
                "/etc/init.d/nginx disable 2>/dev/null",
                "/etc/init.d/uhttpd disable 2>/dev/null",
                "/etc/init.d/lighttpd enable 2>/dev/null",
            ]
        )

    uci.extend(
        [
            "if [ -d /etc/apk ]; then",
            "  mkdir -p /etc/apk/repositories.d",
            "  touch /etc/apk/repositories.d/distfeeds.list",
            "  if [ ! -e /etc/apk/repositories.d/customfeeds.list ]; then",
            "    cat >/etc/apk/repositories.d/customfeeds.list <<'EOF_APK_FEEDS'",
            "# Add custom APK repositories here.",
            "# https://example.com/path/to/packages.adb",
            "EOF_APK_FEEDS",
            "  fi",
            "  if ! grep -qxF '/etc/apk/repositories.d/customfeeds.list' /etc/sysupgrade.conf 2>/dev/null; then",
            "    echo '/etc/apk/repositories.d/customfeeds.list' >>/etc/sysupgrade.conf",
            "  fi",
            "fi",
        ]
    )

    if runtime_mirror_url:
        uci.extend(
            [
                f"runtime_mirror={sq(runtime_mirror_sed)}",
                "for feed_file in /etc/opkg/distfeeds.conf /etc/apk/repositories /etc/apk/repositories.d/distfeeds.list; do",
                "  [ -f \"$feed_file\" ] || continue",
                "  sed -i \"s#https\\?://downloads.openwrt.org#$runtime_mirror#g\" \"$feed_file\"",
                "done",
            ]
        )

    if unpublished_runtime_feeds:
        uci.extend(
            [
                "for feed_file in /etc/apk/repositories /etc/apk/repositories.d/distfeeds.list; do",
                "  [ -f \"$feed_file\" ] || continue",
            ]
        )
        for feed in unpublished_runtime_feeds:
            uci.append(
                f"  sed -i '\\|/{feed}/packages\\.adb| "
                "{ /^[[:space:]]*#/! s|^|# |; }' \"$feed_file\""
            )
        uci.append("done")

    if "openclash" in selected_proxies and "mihomo" in selected_proxy_cores:
        uci.extend(
            [
                "mkdir -p /etc/openclash/core",
                "ln -sf /usr/libexec/mihomo-core /etc/openclash/core/clash_meta",
            ]
        )

    quick_dir = f"/www/{quick_path}"
    quick_file = f"{quick_dir}/index.html"
    uci.extend(
        [
            f"rm -f {sq(quick_dir)}",
            f"mkdir -p {sq(quick_dir)}",
            f"cat >{sq(quick_file)} <<'EOF'",
            '<html><head><meta http-equiv="refresh" content="0; url=/cgi-bin/luci" /></head></html>',
            "EOF",
        ]
    )
    uci.append("exit 0")

    defaults_dir = source_dir / "files" / "etc" / "uci-defaults"
    defaults_dir.mkdir(parents=True, exist_ok=True)
    options_script = defaults_dir / "98-custom-web-options"
    options_script.write_text("\n".join(uci) + "\n", encoding="utf-8")
    options_script.chmod(0o755)

    init_path = defaults_dir / "99-user-init"
    if init_script.strip():
        init_path.write_text(
            "#!/bin/sh\nset +e\n" + init_script.strip() + "\nexit 0\n",
            encoding="utf-8",
        )
        init_path.chmod(0o755)
    else:
        init_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    feeds_parser = subparsers.add_parser("feeds")
    feeds_parser.add_argument("options", type=Path)
    feeds_parser.add_argument("--source", type=Path, default=Path.cwd())

    options_parser = subparsers.add_parser("options")
    options_parser.add_argument("options", type=Path)
    options_parser.add_argument("--source", type=Path, default=Path.cwd())
    options_parser.add_argument("--profile-dir", type=Path)

    branding_parser = subparsers.add_parser("branding")
    branding_parser.add_argument("options", type=Path)
    branding_parser.add_argument("--source", type=Path, default=Path.cwd())
    branding_parser.add_argument("--profile-dir", type=Path)

    args = parser.parse_args()
    if args.command == "feeds":
        configure_feeds(args.options, args.source)
    elif args.command == "options":
        render_build_options(args.options, args.source, args.profile_dir)
    else:
        configure_branding(args.options, args.source, args.profile_dir)


if __name__ == "__main__":
    main()
