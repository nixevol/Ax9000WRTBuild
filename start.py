#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SHUTDOWN_TIMEOUT = 5
FRONTEND_PORT = 9000
BACKEND_PORT = 9001


def validate_environment() -> str:
    if sys.version_info < (3, 11):
        raise RuntimeError("需要 Python 3.11 或更高版本")

    missing = [
        module
        for module in ("fastapi", "uvicorn")
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        requirements = ROOT_DIR / "requirements.txt"
        command = f'"{sys.executable}" -m pip install -r "{requirements}"'
        raise RuntimeError(f"当前 Python 缺少后端依赖，请先运行：\n{command}")

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("未找到 npm，请先安装 Node.js 与 npm")
    if not (ROOT_DIR / "node_modules").is_dir():
        raise RuntimeError("前端依赖尚未安装，请先在项目根目录运行：npm install")
    return npm


def request_stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass


def force_stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def stop_services(services: list[tuple[str, subprocess.Popen[bytes]]]) -> None:
    for _, process in reversed(services):
        request_stop(process)

    deadline = time.monotonic() + SHUTDOWN_TIMEOUT
    for _, process in reversed(services):
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            force_stop(process)

    for _, process in reversed(services):
        if process.poll() is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass


def start_service(name: str, command: list[str]) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {"cwd": ROOT_DIR}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True

    process = subprocess.Popen(command, **options)
    print(f"[{name}] 已启动，PID={process.pid}", flush=True)
    return process


def handle_shutdown_signal(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    try:
        npm = validate_environment()
    except RuntimeError as error:
        print(f"启动失败：{error}", file=sys.stderr)
        return 1

    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, handle_shutdown_signal)

    services: list[tuple[str, subprocess.Popen[bytes]]] = []
    commands = [
        (
            "后端",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "web.server.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(BACKEND_PORT),
                "--reload",
            ],
        ),
        ("前端", [npm, "run", "web:dev"]),
    ]

    try:
        for name, command in commands:
            services.append((name, start_service(name, command)))

        print("\nOpenWRT 开发服务正在启动：", flush=True)
        print(f"  前端：http://localhost:{FRONTEND_PORT}", flush=True)
        print(f"  后端：http://localhost:{BACKEND_PORT}", flush=True)
        print("按 Ctrl+C 同时停止前后端。\n", flush=True)

        while True:
            for name, process in services:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"[{name}] 已退出，退出码 {exit_code}", file=sys.stderr)
                    return exit_code or 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n正在停止前后端...", flush=True)
        return 0
    except OSError as error:
        print(f"启动失败：{error}", file=sys.stderr)
        return 1
    finally:
        stop_services(services)


if __name__ == "__main__":
    raise SystemExit(main())
