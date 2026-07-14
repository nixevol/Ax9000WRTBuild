from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import shlex
import signal
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request as UrlRequest, urlopen
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from web.server.catalog import (
    load_feed_sources,
    load_package_catalog,
    normalize_feed,
    refresh_package_catalog,
)

BuildProcess = asyncio.subprocess.Process | subprocess.Popen[bytes]

ROOT_DIR = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT_DIR / "profiles"
OUTPUT_DIR = ROOT_DIR / "outputs"
RUNTIME_DIR = ROOT_DIR / ".runtime"
FRONTEND_DIST = ROOT_DIR / "web" / "frontend" / "dist"

app = FastAPI(title="OpenWRT NSS 构建控制台")

PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
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
ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def normalize_plain_https_url(value: str, field_name: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
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
        raise ValueError(f"{field_name}必须是无账号、查询参数和片段的 HTTPS 地址")
    return value


class FeedSource(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=32)
    label: str = Field(default="", max_length=128)
    url: str = Field(min_length=1, max_length=512)
    branch: str = Field(default="main", min_length=1, max_length=128)
    kind: str = Field(default="custom", max_length=32)
    builtin: bool = False
    enabled: bool = True

    @model_validator(mode="after")
    def validate_source(self) -> "FeedSource":
        try:
            normalize_feed(self.model_dump())
        except ValueError as error:
            raise ValueError(str(error)) from error
        return self


class BuildOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    basePackages: list[str] | None = Field(default=None, max_length=512)
    selectedPackages: list[str] = Field(default_factory=list, max_length=2048)
    proxyPresets: list[str] = Field(default_factory=list, max_length=16)
    proxyCores: list[Literal["xray-core", "sing-box", "mihomo"]] = Field(
        default_factory=list, max_length=3
    )
    feeds: list[FeedSource] = Field(default_factory=list, max_length=12)
    lanIp: str = Field(default="192.168.32.1", max_length=15)
    netmask: str = Field(default="255.255.255.0", max_length=15)
    rootPassword: str = Field(default="password", min_length=1, max_length=128)
    theme: Literal[
        "Argon",
        "Bootstrap",
        "Spectra",
        "Aurora",
        "Alpha",
        "Design",
        "KuCat",
        "Material",
        "Material Design 3",
        "OpenWrt2020",
        "OpenWrt",
    ] = "Argon"
    docker: bool = False
    storeOs: bool = False
    nasMode: bool = False
    webServer: Literal["Nginx", "Uhttpd", "Lighttpd"] = "Nginx"
    quickPath: str = Field(default="openwrt", min_length=1, max_length=64)
    httpsAdmin: bool = False
    installedLanguages: list[Literal["en", "zh_cn"]] = Field(
        default_factory=lambda: ["en", "zh_cn"], max_length=2
    )
    defaultLanguage: Literal["auto", "en", "zh_cn"] = "auto"
    firewallBackend: Literal["firewall4", "iptables"] = "firewall4"
    runtimeMirror: Literal[
        "build-default", "official", "tencent", "aliyun", "tuna", "bfsu", "custom"
    ] = "build-default"
    customMirrorUrl: str = Field(default="", max_length=512)
    ipv6: bool = False
    bypassMode: bool = False
    ipv4Gateway: str = Field(default="", max_length=15)
    dhcpServer: bool = True
    pppoeUser: str = Field(default="", max_length=128)
    pppoePassword: str = Field(default="", max_length=128)
    wifiMode: Literal["band", "unified", "wizard"] = "band"
    wifiSsid: str = Field(default="", max_length=64)
    wifiPassword: str = Field(default="", max_length=63)
    exposePublic: bool = False
    exposedPorts: str = Field(default="", max_length=1024)
    rndis: bool = False
    hostname: str = Field(default="OpenWRT", min_length=1, max_length=63)
    customSignature: str = Field(default="", max_length=256)
    authorName: str = Field(default="", max_length=128)
    authorUrl: str = Field(default="", max_length=512)
    initScript: str = Field(default="", max_length=65536)

    @field_validator("basePackages", "selectedPackages")
    @classmethod
    def validate_packages(cls, packages: list[str] | None) -> list[str] | None:
        if packages is None:
            return None
        unique: list[str] = []
        for package in packages:
            if not PACKAGE_RE.fullmatch(package):
                raise ValueError(f"软件包名称无效: {package}")
            package = PACKAGE_ALIASES.get(package, package)
            if package not in unique:
                unique.append(package)
        return unique

    @field_validator("proxyPresets")
    @classmethod
    def validate_proxy_presets(cls, values: list[str]) -> list[str]:
        allowed = {"passwall", "passwall2", "homeproxy", "openclash", "v2raya"}
        unique: list[str] = []
        for value in values:
            if value not in allowed:
                raise ValueError(f"代理预设无效: {value}")
            if value not in unique:
                unique.append(value)
        return unique

    @model_validator(mode="before")
    @classmethod
    def migrate_proxy_cores(cls, values: Any) -> Any:
        if not isinstance(values, dict) or "proxyCores" in values:
            return values
        migrated = dict(values)
        legacy_cores = {
            "passwall": {"sing-box"},
            "passwall2": {"xray-core", "sing-box"},
            "homeproxy": {"sing-box"},
            "openclash": {"mihomo"},
            "v2raya": {"xray-core"},
        }
        cores: set[str] = set()
        for proxy in migrated.get("proxyPresets", []):
            cores.update(legacy_cores.get(proxy, set()))
        migrated["proxyCores"] = sorted(cores)
        return migrated

    @field_validator("installedLanguages")
    @classmethod
    def validate_languages(cls, values: list[str]) -> list[str]:
        unique = list(dict.fromkeys(values))
        if "en" not in unique:
            raise ValueError("LuCI 内置英语必须保留")
        return unique

    @field_validator("feeds")
    @classmethod
    def validate_feeds(cls, feeds: list[FeedSource]) -> list[FeedSource]:
        names = [feed.name for feed in feeds]
        if len(names) != len(set(names)):
            raise ValueError("软件源名称不能重复")
        return feeds

    @field_validator("lanIp", "ipv4Gateway")
    @classmethod
    def validate_ipv4(cls, value: str) -> str:
        if not value:
            return value
        try:
            return str(ipaddress.IPv4Address(value))
        except ipaddress.AddressValueError as error:
            raise ValueError("必须是有效的 IPv4 地址") from error

    @field_validator("netmask")
    @classmethod
    def validate_netmask(cls, value: str) -> str:
        try:
            ipaddress.IPv4Network(f"0.0.0.0/{value}")
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as error:
            raise ValueError("必须是有效的 IPv4 子网掩码") from error
        return value

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        if not HOSTNAME_RE.fullmatch(value):
            raise ValueError("主机名格式无效")
        return value

    @field_validator("quickPath")
    @classmethod
    def validate_quick_path(cls, value: str) -> str:
        normalized = value.strip("/")
        if not QUICK_PATH_RE.fullmatch(normalized):
            raise ValueError("快捷路径只能包含字母、数字、点、下划线和连字符")
        return normalized

    @field_validator(
        "rootPassword",
        "pppoeUser",
        "pppoePassword",
        "wifiPassword",
        "customSignature",
        "authorName",
    )
    @classmethod
    def validate_single_line(cls, value: str) -> str:
        if "\0" in value or "\r" in value or "\n" in value:
            raise ValueError("不能包含换行或 NUL 字符")
        return value

    @field_validator("wifiSsid")
    @classmethod
    def validate_wifi_ssid(cls, value: str) -> str:
        if "\0" in value or "\r" in value or "\n" in value:
            raise ValueError("Wi-Fi 名称不能包含换行或 NUL 字符")
        if len(value.encode("utf-8")) > 32:
            raise ValueError("Wi-Fi 名称不能超过 32 个 UTF-8 字节")
        return value

    @model_validator(mode="after")
    def validate_band_wifi_ssid(self) -> BuildOptions:
        if (
            self.wifiMode == "band"
            and self.wifiSsid
            and len(f"{self.wifiSsid}_2.4G".encode("utf-8")) > 32
        ):
            raise ValueError("按频段区分时，Wi-Fi 名称加 _2.4G 后不能超过 32 个 UTF-8 字节")
        return self

    @field_validator("wifiPassword")
    @classmethod
    def validate_wifi_password(cls, value: str) -> str:
        if value and not 8 <= len(value.encode("utf-8")) <= 63:
            raise ValueError("Wi-Fi 密码必须为 8 到 63 个 UTF-8 字节")
        return value

    @field_validator("initScript")
    @classmethod
    def validate_init_script(cls, value: str) -> str:
        if "\0" in value:
            raise ValueError("初始化脚本不能包含 NUL 字符")
        return value

    @field_validator("authorUrl")
    @classmethod
    def validate_https_url(cls, value: str) -> str:
        return normalize_plain_https_url(value, "作者外链")

    @field_validator("customMirrorUrl")
    @classmethod
    def normalize_custom_mirror_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @model_validator(mode="after")
    def validate_related_options(self) -> "BuildOptions":
        if self.bypassMode and not self.ipv4Gateway:
            raise ValueError("旁路由模式必须填写 IPv4 网关")
        if self.webServer == "Lighttpd" and self.httpsAdmin:
            raise ValueError("Lighttpd 暂不支持 HTTPS 管理选项")
        if self.defaultLanguage != "auto" and self.defaultLanguage not in self.installedLanguages:
            raise ValueError("默认语言必须已安装")
        if self.firewallBackend == "iptables":
            incompatible = {"homeproxy", "v2raya"} & set(self.proxyPresets)
            if incompatible:
                names = "、".join(sorted(incompatible))
                raise ValueError(f"{names} 依赖 Nftables，不能配合 Iptables 防火墙")
        if bool(self.authorName.strip()) != bool(self.authorUrl):
            raise ValueError("作者名称和作者外链必须同时填写")
        if self.runtimeMirror == "custom":
            self.customMirrorUrl = normalize_plain_https_url(
                self.customMirrorUrl, "自定义镜像地址"
            )
            if not self.customMirrorUrl:
                raise ValueError("选择自定义镜像时必须填写镜像地址")
        else:
            self.customMirrorUrl = ""

        ports: list[str] = []
        for token in self.exposedPorts.split():
            if not token.isascii() or not token.isdigit():
                raise ValueError(f"WAN 端口无效: {token}")
            port = int(token)
            if not 1 <= port <= 65535:
                raise ValueError(f"WAN 端口超出范围: {token}")
            if token not in ports:
                ports.append(token)
        if len(ports) > 128:
            raise ValueError("WAN 开放端口最多 128 个")
        if self.exposePublic and not ports:
            raise ValueError("允许 WAN 访问时至少填写一个端口")
        self.exposedPorts = " ".join(ports)
        return self


class BuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile: str = Field(default="ax9000", min_length=1, max_length=32)
    jobs: int = Field(default=0, ge=0, le=64)
    clean: bool = False
    options: BuildOptions = Field(default_factory=BuildOptions)

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, value: str) -> str:
        if not PROFILE_RE.fullmatch(value):
            raise ValueError("设备 profile 名称无效")
        return value


class SavedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    options: BuildOptions
    jobs: int = Field(default=0, ge=0, le=64)
    clean: bool = False


class CatalogRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    feeds: list[FeedSource] = Field(default_factory=list, max_length=12)


@dataclass
class LogEntry:
    ts: str
    text: str


class BuildState:
    def __init__(self) -> None:
        self.running = False
        self.profile: str | None = None
        self.jobs = 0
        self.clean = False
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.exit_code: int | None = None
        self.process: BuildProcess | None = None
        self.task: asyncio.Task[None] | None = None
        self.stop_requested = False
        self.container_name: str | None = None
        self.logs: list[LogEntry] = []
        self.clients: set[asyncio.Queue[LogEntry]] = set()

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "profile": self.profile,
            "jobs": self.jobs,
            "clean": self.clean,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "exitCode": self.exit_code,
            "stopping": self.stop_requested,
            "logs": [entry.__dict__ for entry in self.logs[-300:]],
        }


state = BuildState()
catalog_refresh_lock = asyncio.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def push_log(line: str) -> None:
    text = ANSI_ESCAPE_RE.sub("", line).replace("\r", "").rstrip("\n")
    if not text:
        return

    entry = LogEntry(ts=now_iso(), text=text)
    state.logs.append(entry)
    if len(state.logs) > 3000:
        del state.logs[: len(state.logs) - 3000]

    dead_clients: list[asyncio.Queue[LogEntry]] = []
    for queue in state.clients:
        try:
            queue.put_nowait(entry)
        except asyncio.QueueFull:
            dead_clients.append(queue)

    for queue in dead_clients:
        state.clients.discard(queue)


def read_key_value_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("\"'")
    return result


def read_package_list(profile: str) -> list[str]:
    path = PROFILES_DIR / profile / "packages.list"
    if not path.exists():
        return []

    packages: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            packages.append(line)
    return packages


def read_profile_metadata(profile: str) -> dict[str, Any]:
    path = PROFILES_DIR / profile / "metadata.json"
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def read_profile_json(profile: str, filename: str) -> dict[str, Any]:
    path = PROFILES_DIR / profile / filename
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def profile_directory(profile: str) -> Path:
    if not PROFILE_RE.fullmatch(profile):
        raise HTTPException(status_code=404, detail=f"未知设备 profile: {profile}")
    profile_dir = PROFILES_DIR / profile
    if not profile_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"未知设备 profile: {profile}")
    return profile_dir


def probe_repository_url(url: str) -> dict[str, Any]:
    request = UrlRequest(url, method="HEAD", headers={"User-Agent": "OpenWRT/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
        return {"url": url, "ok": 200 <= status < 400, "status": status}
    except HTTPError as error:
        if error.code not in {403, 405}:
            return {"url": url, "ok": False, "status": error.code}
        fallback = UrlRequest(
            url,
            method="GET",
            headers={"User-Agent": "OpenWRT/1.0", "Range": "bytes=0-0"},
        )
        try:
            with urlopen(fallback, timeout=10) as response:
                status = response.status
            return {"url": url, "ok": 200 <= status < 400, "status": status}
        except HTTPError as fallback_error:
            return {"url": url, "ok": False, "status": fallback_error.code}
        except (OSError, URLError) as fallback_error:
            return {
                "url": url,
                "ok": False,
                "status": None,
                "error": str(fallback_error),
            }
    except (OSError, URLError) as error:
        return {"url": url, "ok": False, "status": None, "error": str(error)}


def saved_config_path(profile: str) -> Path:
    profile_directory(profile)
    return RUNTIME_DIR / "saved-configs" / f"{profile}.json"


def read_saved_config(profile: str) -> SavedConfig | None:
    path = saved_config_path(profile)
    if not path.is_file():
        return None
    try:
        return SavedConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"本地配置无法读取: {error}") from error


def write_saved_config(profile: str, config: SavedConfig) -> None:
    path = saved_config_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    try:
        temporary.write_text(
            config.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def delete_saved_config(profile: str) -> None:
    saved_config_path(profile).unlink(missing_ok=True)


def list_profiles() -> list[dict[str, Any]]:
    if not PROFILES_DIR.exists():
        return []

    profiles: list[dict[str, Any]] = []
    for item in sorted(PROFILES_DIR.iterdir()):
        if not item.is_dir():
            continue
        env = read_key_value_file(item / "profile.env")
        profiles.append(
            {
                "name": item.name,
                "targetDir": env.get("TARGET_DIR", ""),
                "openwrtTarget": env.get("OPENWRT_TARGET", ""),
                "deviceId": env.get("DEVICE_ID", ""),
                "repoBranch": env.get("REPO_BRANCH", ""),
                "packages": read_package_list(item.name),
                "metadata": read_profile_metadata(item.name),
                "presets": read_profile_json(item.name, "presets.json"),
                "defaultOptions": read_profile_json(
                    item.name, "default-options.json"
                ),
                "feeds": load_feed_sources(item),
            }
        )
    return profiles


def classify_artifact(name: str) -> tuple[str, str]:
    lower = name.lower()
    if lower.endswith(".zip"):
        return "archive", "固件归档"
    if lower.endswith(".config"):
        return "config", "配置"
    if "sysupgrade" in lower:
        return "sysupgrade", "升级包"
    if "initramfs" in lower and "factory" in lower:
        return "initramfs-factory", "临时启动"
    if "factory" in lower:
        return "factory", "刷机包"
    if "kernel" in lower or "uimage" in lower:
        return "kernel", "内核"
    if "uboot" in lower or "u-boot" in lower:
        return "uboot", "UBoot"
    return "other", "其他"


def list_artifacts(profile: str) -> list[dict[str, Any]]:
    directory = OUTPUT_DIR / profile
    if not directory.exists():
        return []

    archives = sorted(
        (item for item in directory.glob("OpenWRT-*.zip") if item.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    artifacts: list[dict[str, Any]] = []
    for item in archives[:1]:
        stat = item.stat()
        artifact_type, artifact_label = classify_artifact(item.name)
        artifacts.append(
            {
                "name": item.name,
                "size": stat.st_size,
                "type": artifact_type,
                "typeLabel": artifact_label,
                "modifiedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return artifacts


def package_artifacts(profile: str) -> Path:
    directory = OUTPUT_DIR / profile
    if not directory.is_dir():
        raise RuntimeError("构建输出目录不存在")

    for old_archive in directory.glob("OpenWRT-*.zip"):
        old_archive.unlink()
    files = sorted(
        item
        for item in directory.iterdir()
        if item.is_file()
        and not item.name.startswith(".")
        and item.suffix.lower() != ".zip"
    )
    if not files:
        raise RuntimeError("构建完成但没有找到固件产物")

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    archive = directory / f"OpenWRT-AX9000-{timestamp}.zip"
    temporary = directory / f".{archive.name}.tmp"
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as bundle:
            for item in files:
                bundle.write(item, arcname=item.name)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    return archive


async def stream_reader(reader: asyncio.StreamReader, prefix: str = "") -> None:
    while True:
        line = await reader.readline()
        if not line:
            break
        await push_log(f"{prefix}{line.decode(errors='replace')}")


def prepare_build(request: BuildRequest) -> None:
    state.running = True
    state.profile = request.profile
    state.jobs = min(64, max(0, int(request.jobs or 0)))
    state.clean = request.clean
    state.started_at = now_iso()
    state.ended_at = None
    state.exit_code = None
    state.process = None
    state.task = None
    state.stop_requested = False
    state.container_name = f"openwrt-builder-{uuid4().hex[:12]}"
    state.logs.clear()


async def terminate_process(process: BuildProcess) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        await asyncio.to_thread(
            subprocess.run,
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.send_signal(signal.SIGTERM)


async def wait_for_process(process: BuildProcess) -> int:
    if isinstance(process, asyncio.subprocess.Process):
        return await process.wait()
    return await asyncio.to_thread(process.wait)


async def stream_windows_process(process: subprocess.Popen[bytes]) -> None:
    assert process.stdout is not None
    while True:
        line = await asyncio.to_thread(process.stdout.readline)
        if line:
            await push_log(line.decode(errors="replace"))
            continue
        if process.poll() is not None:
            return


async def stop_container(container_name: str | None) -> None:
    if not container_name:
        return
    try:
        await asyncio.to_thread(
            subprocess.run,
            ["docker", "stop", "-t", "10", container_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        await push_log(f"停止 Docker 容器失败: {error}")


async def run_build(request: BuildRequest) -> None:
    safe_jobs = state.jobs
    is_windows = os.name == "nt"
    options_file: Path | None = None
    process: BuildProcess | None = None
    code = 1

    await push_log(
        f"开始构建 {request.profile}，线程={safe_jobs or '自动'}，clean={'是' if request.clean else '否'}"
    )

    try:
        RUNTIME_DIR.mkdir(exist_ok=True)
        options_file = RUNTIME_DIR / f"build-options-{uuid4().hex}.json"
        options_payload = request.options.model_dump()
        if not options_payload["feeds"]:
            options_payload["feeds"] = load_feed_sources(
                profile_directory(request.profile)
            )
        options_file.write_text(
            json.dumps(options_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if is_windows:
            script = ROOT_DIR / "scripts" / "build-docker.ps1"
            command = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-Profile",
                request.profile,
                "-Jobs",
                str(safe_jobs),
                "-OptionsFile",
                str(options_file),
                "-ContainerName",
                state.container_name or "openwrt-local-builder-run",
            ]
            if request.clean:
                command.append("-Clean")
        else:
            rel_options = options_file.relative_to(ROOT_DIR).as_posix()
            root_arg = shlex.quote(str(ROOT_DIR))
            profile_arg = shlex.quote(request.profile)
            container_arg = shlex.quote(state.container_name or "openwrt-local-builder-run")
            options_arg = shlex.quote(f"/workspace/{rel_options}")
            shell = (
                f"docker build -t openwrt-local-builder:25.12 {root_arg} && "
                f"docker run --rm --name {container_arg} -e PROFILE={profile_arg} "
                f"-e JOBS={safe_jobs} -e CLEAN={1 if request.clean else 0} "
                f"-e BUILD_OPTIONS_FILE={options_arg} "
                f"-v {shlex.quote(f'{ROOT_DIR}:/workspace')} "
                "-v openwrt-build-work:/work openwrt-local-builder:25.12"
            )
            command = ["bash", "-lc", shell]

        if state.stop_requested:
            code = 130
            return

        if is_windows:
            process = subprocess.Popen(
                command,
                cwd=ROOT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=ROOT_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        state.process = process
        if state.stop_requested:
            await terminate_process(process)

        if is_windows:
            await stream_windows_process(process)
        else:
            assert process.stdout is not None
            assert process.stderr is not None
            await asyncio.gather(stream_reader(process.stdout), stream_reader(process.stderr))
        code = await wait_for_process(process)
        if state.stop_requested and code != 0:
            code = 130
        elif code == 0:
            try:
                archive = await asyncio.to_thread(package_artifacts, request.profile)
            except Exception as error:
                code = 1
                raise RuntimeError(f"固件打包失败: {error}") from error
            await push_log(f"固件产物已打包: {archive.name}")
    except Exception as error:
        detail = str(error) or repr(error)
        await push_log(f"构建进程异常: {detail}")
        if process and process.returncode is None:
            await terminate_process(process)
            await wait_for_process(process)
    finally:
        was_stopped = state.stop_requested
        state.running = False
        state.ended_at = now_iso()
        state.exit_code = code
        state.process = None
        state.task = None
        state.stop_requested = False
        state.container_name = None
        if options_file:
            try:
                options_file.unlink(missing_ok=True)
            except OSError as error:
                await push_log(f"临时配置清理失败: {error}")
        if was_stopped and code == 130:
            await push_log("构建已停止")
        else:
            await push_log("构建完成" if code == 0 else f"构建失败，退出码 {code}")


@app.get("/api/profiles")
async def profiles() -> dict[str, Any]:
    return {"profiles": list_profiles()}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return state.snapshot()


@app.get("/api/artifacts/{profile}")
async def artifacts(profile: str) -> dict[str, Any]:
    profile_directory(profile)
    return {"artifacts": list_artifacts(profile)}


@app.get("/api/runtime-mirror/{profile}/{mirror_id}")
async def runtime_mirror_compatibility(
    profile: str, mirror_id: str
) -> dict[str, Any]:
    profile_directory(profile)
    presets = read_profile_json(profile, "presets.json")
    mirrors = presets.get("runtimeMirrors", [])
    if not isinstance(mirrors, list):
        raise HTTPException(status_code=500, detail="运行时镜像配置无效")
    mirror = next(
        (
            item
            for item in mirrors
            if isinstance(item, dict) and item.get("id") == mirror_id
        ),
        None,
    )
    if mirror is None:
        raise HTTPException(status_code=404, detail="未知运行时镜像")
    if mirror_id == "build-default":
        return {
            "mirrorId": mirror_id,
            "checked": False,
            "supported": True,
            "message": "使用构建源码生成的默认软件源",
            "checks": [],
        }
    if mirror_id == "custom":
        return {
            "mirrorId": mirror_id,
            "checked": False,
            "supported": None,
            "message": "自定义地址需要自行确认仓库兼容性",
            "checks": [],
        }

    base_url = normalize_plain_https_url(
        str(mirror.get("baseUrl", "")), "运行时镜像地址"
    )
    paths = presets.get("runtimeRepositoryPaths", [])
    if not isinstance(paths, list) or not paths:
        raise HTTPException(status_code=500, detail="缺少运行时仓库检查路径")
    normalized_paths: list[str] = []
    for path in paths:
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or ".." in path.split("/")
            or any(character.isspace() for character in path)
        ):
            raise HTTPException(status_code=500, detail="运行时仓库检查路径无效")
        normalized_paths.append(path)

    checks = await asyncio.gather(
        *(
            asyncio.to_thread(probe_repository_url, f"{base_url}/{path}")
            for path in normalized_paths
        )
    )
    supported = all(check["ok"] for check in checks)
    failed = sum(not check["ok"] for check in checks)
    return {
        "mirrorId": mirror_id,
        "checked": True,
        "supported": supported,
        "message": "全部仓库可用" if supported else f"{failed} 个必需仓库不可用",
        "checks": checks,
    }


@app.get("/api/package-catalog/{profile}")
async def package_catalog(profile: str) -> dict[str, Any]:
    profile_dir = profile_directory(profile)
    return load_package_catalog(profile, profile_dir, RUNTIME_DIR)


@app.get("/api/saved-config/{profile}")
async def get_saved_config(profile: str) -> dict[str, Any]:
    try:
        config = read_saved_config(profile)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return {
        "saved": config is not None,
        "options": config.options.model_dump() if config else None,
        "jobs": config.jobs if config else 0,
        "clean": config.clean if config else False,
    }


@app.put("/api/saved-config/{profile}")
async def put_saved_config(profile: str, config: SavedConfig) -> dict[str, Any]:
    try:
        write_saved_config(profile, config)
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"本地配置保存失败: {error}") from error
    return {"saved": True}


@app.delete("/api/saved-config/{profile}")
async def remove_saved_config(profile: str) -> dict[str, Any]:
    try:
        delete_saved_config(profile)
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"本地配置删除失败: {error}") from error
    return {"saved": False}


@app.post("/api/package-catalog/{profile}/refresh")
async def refresh_catalog(profile: str, request: CatalogRefreshRequest) -> dict[str, Any]:
    profile_dir = profile_directory(profile)
    if catalog_refresh_lock.locked():
        raise HTTPException(status_code=409, detail="软件库正在同步")

    feeds = [feed.model_dump() for feed in request.feeds] or load_feed_sources(profile_dir)
    async with catalog_refresh_lock:
        try:
            return await asyncio.to_thread(
                refresh_package_catalog,
                profile,
                profile_dir,
                RUNTIME_DIR,
                feeds,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise HTTPException(status_code=502, detail=f"软件库同步失败: {error}") from error


@app.post("/api/build")
async def build(request: BuildRequest) -> dict[str, Any]:
    if state.running:
        raise HTTPException(status_code=409, detail="已有构建正在运行")

    profile_names = {profile["name"] for profile in list_profiles()}
    if request.profile not in profile_names:
        raise HTTPException(status_code=400, detail=f"未知设备 profile: {request.profile}")

    prepare_build(request)
    state.task = asyncio.create_task(run_build(request))
    return state.snapshot()


@app.post("/api/stop")
async def stop() -> dict[str, Any]:
    process = state.process
    if not state.running:
        return state.snapshot()

    state.stop_requested = True
    await push_log("正在停止构建")
    await stop_container(state.container_name)
    if process is not None:
        await terminate_process(process)
    return state.snapshot()


@app.get("/api/logs/stream")
async def logs_stream(request: Request) -> StreamingResponse:
    queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=500)
    state.clients.add(queue)

    async def event_generator():
        try:
            for entry in state.logs[-300:]:
                yield f"data: {json.dumps(entry.__dict__, ensure_ascii=False)}\n\n"

            while not await request.is_disconnected():
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(entry.__dict__, ensure_ascii=False)}\n\n"
        finally:
            state.clients.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


OUTPUT_DIR.mkdir(exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=OUTPUT_DIR), name="artifacts")

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        dist_root = FRONTEND_DIST.resolve()
        target = (dist_root / full_path).resolve()
        if not target.is_relative_to(dist_root):
            raise HTTPException(status_code=404, detail="页面不存在")
        if target.is_file():
            return FileResponse(target)
        return FileResponse(dist_root / "index.html")
