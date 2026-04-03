from __future__ import annotations

import argparse
import ctypes
import os
import socket
import subprocess
import sys
import time
import traceback
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONINFORMATION = 0x00000040

HOST = "127.0.0.1"
BROWSER_HOST = "localhost"
STARTUP_TIMEOUT_SECONDS = 180


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


if not _is_frozen():
    backend_dir = _project_root() / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


from app.core.config import settings


LAUNCHER_LOG_FILE = settings.APP_HOME / "launcher.log"
SERVER_LOG_FILE = settings.APP_HOME / "server.log"


def show_message(title: str, message: str, style: int = MB_OK | MB_ICONINFORMATION) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, title, style)


def append_log(log_file: Path, message: str) -> None:
    settings.APP_HOME.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")


def reset_log(log_file: Path) -> None:
    settings.APP_HOME.mkdir(parents=True, exist_ok=True)
    log_file.write_text("", encoding="utf-8")


def find_available_port(preferred_port: int, host: str = HOST, attempts: int = 30) -> int:
    for port in range(preferred_port, preferred_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port

    raise RuntimeError(
        f"无法找到可用端口，尝试范围：{preferred_port}-{preferred_port + attempts - 1}"
    )


def build_server_command(port: int) -> list[str]:
    if _is_frozen():
        return [sys.executable, "--serve", "--port", str(port)]

    return [sys.executable, str(Path(__file__).resolve()), "--serve", "--port", str(port)]


def launch_server_process(port: int) -> subprocess.Popen[bytes]:
    command = build_server_command(port)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    append_log(LAUNCHER_LOG_FILE, f"启动服务器子进程：{' '.join(command)}")
    return subprocess.Popen(
        command,
        cwd=str(settings.APP_HOME),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def wait_for_healthcheck(server_process: subprocess.Popen[bytes], url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        exit_code = server_process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"服务进程已提前退出，退出码：{exit_code}。请查看日志：{SERVER_LOG_FILE}"
            )

        try:
            with urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except URLError as exc:
            last_error = exc
        except OSError as exc:
            last_error = exc

        time.sleep(0.5)

    if last_error is None:
        raise RuntimeError(f"服务启动超时。请查看日志：{SERVER_LOG_FILE}")
    raise RuntimeError(f"服务启动失败：{last_error}。请查看日志：{SERVER_LOG_FILE}")


def stop_server_process(server_process: subprocess.Popen[bytes] | None) -> None:
    if server_process is None or server_process.poll() is not None:
        return

    append_log(LAUNCHER_LOG_FILE, f"停止服务器子进程，PID={server_process.pid}")
    server_process.terminate()

    try:
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()
        server_process.wait(timeout=5)


def run_server_process(port: int) -> int:
    reset_log(SERVER_LOG_FILE)
    append_log(SERVER_LOG_FILE, f"服务器模式启动，端口：{port}")

    try:
        import uvicorn

        from app.main import app

        config = uvicorn.Config(
            app=app,
            host=HOST,
            port=port,
            log_level="warning",
            access_log=False,
            loop="asyncio",
            http="h11",
            ws="none",
            lifespan="on",
        )
        server = uvicorn.Server(config)
        append_log(SERVER_LOG_FILE, "Uvicorn 配置完成，准备启动")
        server.run()
        append_log(SERVER_LOG_FILE, f"Uvicorn 已退出，should_exit={server.should_exit}")
        return 0
    except Exception as exc:
        append_log(SERVER_LOG_FILE, "服务器启动异常：\n" + "".join(traceback.format_exception(exc)))
        return 1


def run_parent_process() -> int:
    reset_log(LAUNCHER_LOG_FILE)
    append_log(LAUNCHER_LOG_FILE, "启动程序")

    server_process: subprocess.Popen[bytes] | None = None

    try:
        port = find_available_port(settings.DEFAULT_PORT)
        url = f"http://{BROWSER_HOST}:{port}"
        server_process = launch_server_process(port)
        append_log(LAUNCHER_LOG_FILE, f"服务器子进程 PID={server_process.pid}")

        wait_for_healthcheck(server_process, f"{url}/health", STARTUP_TIMEOUT_SECONDS)
        append_log(LAUNCHER_LOG_FILE, f"服务已启动：{url}")
        webbrowser.open(url)

        show_message(
            settings.APP_NAME,
            "\n".join(
                [
                    "程序已启动，浏览器会自动打开。",
                    "",
                    f"访问地址：{url}",
                    f"数据目录：{settings.APP_HOME}",
                    f"启动日志：{LAUNCHER_LOG_FILE}",
                    f"服务日志：{SERVER_LOG_FILE}",
                    "",
                    "关闭浏览器后，点击“确定”即可停止本地服务。",
                ]
            ),
        )
        return 0
    except Exception as exc:
        append_log(LAUNCHER_LOG_FILE, "启动失败：\n" + "".join(traceback.format_exception(exc)))
        show_message(
            "启动失败",
            f"{exc}\n\n启动日志：{LAUNCHER_LOG_FILE}\n服务日志：{SERVER_LOG_FILE}",
            MB_OK | MB_ICONERROR,
        )
        return 1
    finally:
        stop_server_process(server_process)
        append_log(LAUNCHER_LOG_FILE, "程序已退出")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=settings.DEFAULT_PORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exit_code = run_server_process(args.port) if args.serve else run_parent_process()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
