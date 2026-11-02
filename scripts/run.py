"""Start the production services with the repository's .venv Python."""

import argparse
from contextlib import contextmanager
import importlib.metadata
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web"


@contextmanager
def launcher_lock(name):
    """OS releases this lock even if the launcher crashes."""
    directory = ROOT / "output"
    directory.mkdir(exist_ok=True)
    with (directory / f".{name}.lock").open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError(f"The {name} launcher is already running in this checkout.") from None
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class Services:
    def __init__(self, log_dir=None, launcher_name="app-launcher"):
        self.processes = []
        self.log_threads = []
        self.loggers = {}
        self.log_dir = Path(log_dir) if log_dir else ROOT / "output" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.launcher_name = launcher_name

    def record(self, name, message, level=logging.INFO):
        logger = self.loggers.get(name)
        if logger is None:
            logger = logging.Logger(name, level=logging.INFO)
            handler = RotatingFileHandler(
                self.log_dir / f"{name}.log", maxBytes=5 * 1024 * 1024,
                backupCount=3, encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z",
            ))
            logger.addHandler(handler)
            self.loggers[name] = logger
        logger.log(level, message)

    def close_logs(self):
        for thread in self.log_threads:
            thread.join(timeout=2)
        for logger in self.loggers.values():
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)

    def start(self, name, command, cwd=None):
        log_path = self.log_dir / f"{name}.log"
        print(f"Starting {name}... Logs: {log_path}", flush=True)
        self.record(self.launcher_name, f"Starting {name}; logs: {log_path}")
        self.record(name, "--- Process starting ---")
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(
            command, cwd=cwd or ROOT, env={**os.environ, "PYTHONUNBUFFERED": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", **options,
        )
        self.processes.append((name, process))

        def show_logs():
            with process.stdout:
                for line in process.stdout:
                    self.record(name, line.rstrip("\r\n"))
                    print(f"[{name}] {line.rstrip()}", flush=True)

        thread = threading.Thread(target=show_logs, daemon=True)
        self.log_threads.append(thread)
        thread.start()
        return process

    def check(self):
        for name, process in self.processes:
            code = process.poll()
            if code is not None:
                raise RuntimeError(f"{name} stopped (exit code {code}). See {self.log_dir / (name + '.log')}.")

    def wait_http(self, name, url, timeout=120):
        started = time.monotonic()
        deadline = started + timeout
        next_notice = started + 15
        while time.monotonic() < deadline:
            self.check()
            try:
                with urlopen(url, timeout=1):
                    print(f"{name} is listening at {url}", flush=True)
                    return
            except (OSError, URLError):
                now = time.monotonic()
                if now >= next_notice:
                    message = f"{name} is still starting ({int(now - started)}s elapsed; timeout {timeout}s)."
                    print(message, flush=True)
                    self.record(self.launcher_name, message)
                    next_notice = now + 15
                time.sleep(0.25)
        raise RuntimeError(f"{name} did not respond within {timeout} seconds. See {self.log_dir} for service logs.")

    def stop(self):
        print("\nStopping services started by this launcher...", flush=True)
        self.record(self.launcher_name, "Stopping services started by this launcher")
        for _, process in reversed(self.processes):
            if process.poll() is not None:
                continue
            if os.name == "nt":
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                except OSError:
                    pass
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            # Stop dependants first, leaving the backend available for final acknowledgements.
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait()


def require_packages(rag):
    packages = ["python-dotenv", "fastapi", "uvicorn", "supabase"]
    if rag:
        packages += ["sentence-transformers", "chromadb", "bm25s", "lingua-language-detector", "google-genai"]
    for package in packages:
        try:
            importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            raise RuntimeError(
                f"Missing Python package: {package}. Install requirements.txt into .venv first."
            ) from None


def require_settings(names):
    missing = [name for name in names if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(
            "Missing settings: " + ", ".join(missing)
            + ". Configure public settings in app.config.json and credentials in .env or the process environment."
        )


def configured_port(name, default):
    # main() loads app.config.json into os.environ before launching any services.
    try:
        port = int(os.getenv(name) or default)
    except ValueError:
        raise ValueError(f"{name} must be an integer between 1 and 65535; configure it in app.config.json") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535; configure it in app.config.json")
    return port


def port_available(name, host, port):
    with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as listener:
        try:
            listener.bind((host, port))
        except OSError:
            raise RuntimeError(
                f"{name} cannot bind {host}:{port}. Stop the existing service or check its host/port setting."
            ) from None


def local_url(host, port):
    host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    return f"http://{'[' + host + ']' if ':' in host else host}:{port}"


def run_app(services, without_rag, no_browser):
    node = shutil.which("node")
    if not node or not (FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next").is_file():
        raise RuntimeError("Install Node.js and run npm ci in web first.")
    if not (FRONTEND / ".next" / "BUILD_ID").is_file():
        raise RuntimeError("Build the dashboard with npm --prefix web run build first.")
    require_settings(["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"])
    backend_host = os.getenv("BACKEND_HOST") or "127.0.0.1"
    backend_port = configured_port("BACKEND_PORT", 8000)
    frontend_port = configured_port("FRONTEND_PORT", 3000)
    frontend_host = os.getenv('FRONTEND_HOST') or '127.0.0.1'
    backend_url = local_url(backend_host, backend_port)
    frontend_url = local_url(frontend_host, frontend_port)
    port_available("Backend", backend_host, backend_port)
    port_available("Web dashboard", frontend_host, frontend_port)
    if not without_rag:
        require_settings(["RAG_SERVICE_TOKEN"])
        rag_host = os.getenv("RAG_HTTP_HOST") or "127.0.0.1"
        rag_port = configured_port("RAG_HTTP_PORT", 8001)
        rag_url = local_url(rag_host, rag_port)
        rag_startup_timeout = int(os.getenv("RAG_STARTUP_TIMEOUT_SECONDS") or "600")
        if rag_startup_timeout <= 0:
            raise ValueError("RAG_STARTUP_TIMEOUT_SECONDS must be positive")
        port_available("RAG API", rag_host, rag_port)
        # These defaults apply only to this launch; explicit configuration values still win.
        os.environ.setdefault("RAG_SERVICE_URL", rag_url)
        os.environ.setdefault("RAG_BACKEND_URL", backend_url)
        os.environ.setdefault('RAG_INDEX_WORKER_MODE', 'embedded')
        if os.environ['RAG_INDEX_WORKER_MODE'] not in {'embedded', 'external'}:
            raise ValueError('RAG_INDEX_WORKER_MODE must be embedded or external')
    services.start("backend", [sys.executable, "-m", "backend"])
    services.wait_http("Backend", backend_url + "/health")
    if not without_rag:
        services.start("rag", [sys.executable, "-m", "rag.service"])
        services.wait_http("RAG API", rag_url + "/openapi.json", timeout=rag_startup_timeout)
        if os.environ['RAG_INDEX_WORKER_MODE'] == 'external':
            services.start("index-worker", [sys.executable, "-m", "rag.index_worker"])
    services.start("web", [node, "scripts/next.mjs", "start", '--hostname', frontend_host], cwd=FRONTEND)
    services.wait_http("Web dashboard", frontend_url + "/login")
    print(f"\nApp started: {frontend_url}/login\nAPI docs: {backend_url}/docs", flush=True)
    print("Listening checks do not verify Supabase, model access, or indexing success.", flush=True)
    print("Keep this terminal open. Press Ctrl+C to stop the app.\n", flush=True)
    if not no_browser:
        webbrowser.open(frontend_url + "/login")
    while True:
        services.check()
        time.sleep(0.5)


def configure_ocr_tailscale(services, host, port):
    enabled = os.getenv('MINERU_TAILSCALE_SERVE', 'false').strip().lower()
    if enabled not in {'true', 'false'}:
        raise ValueError('MINERU_TAILSCALE_SERVE must be true or false')
    if enabled == 'false':
        return
    if host not in {'127.0.0.1', '0.0.0.0'}:
        raise ValueError('Tailscale Serve requires MINERU_API_HOST to be 127.0.0.1 or 0.0.0.0')
    https_port = configured_port('MINERU_TAILSCALE_HTTPS_PORT', 443)
    tailscale = shutil.which('tailscale')
    if not tailscale:
        raise RuntimeError('Install Tailscale and add it to PATH, or set MINERU_TAILSCALE_SERVE to false.')
    command = [tailscale, 'serve', '--bg', '--yes', f'--https={https_port}',
               local_url('127.0.0.1', port)]
    print(f'Configuring Tailscale HTTPS port {https_port} for OCR port {port}...', flush=True)
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or '').strip()
        raise RuntimeError(f'Tailscale Serve failed. Ensure Tailscale is connected and HTTPS is enabled. {details}') from None
    except subprocess.TimeoutExpired:
        raise RuntimeError('Tailscale Serve timed out. Check Tailscale connectivity and HTTPS setup.') from None
    output = result.stdout.strip()
    if output:
        print(output, flush=True)
        services.record(services.launcher_name, output)


def run_ocr_service(services):
    try:
        version = importlib.metadata.version('mineru')
    except importlib.metadata.PackageNotFoundError:
        raise RuntimeError('Install requirements-ocr.txt into .venv-ocr first.') from None
    if version != '3.4.5':
        raise RuntimeError(f'Expected MinerU 3.4.5, found {version}; install requirements-ocr.txt.')
    executable = Path(sys.executable).with_name('mineru-api.exe' if os.name == 'nt' else 'mineru-api')
    if not executable.is_file():
        raise RuntimeError('mineru-api is missing from the current Python environment')
    host = os.getenv('MINERU_API_HOST') or '127.0.0.1'
    port = configured_port('MINERU_API_PORT', 8010)
    port_available('MinerU OCR', host, port)
    os.environ.setdefault('MINERU_API_OUTPUT_ROOT', str(ROOT / 'output' / 'mineru-api'))
    os.environ.setdefault('MINERU_API_MAX_CONCURRENT_REQUESTS', '1')
    os.environ.setdefault('MINERU_API_DISABLE_ACCESS_LOG', '1')
    services.start('ocr', [str(executable), '--host', host, '--port', str(port)])
    services.wait_http('MinerU OCR', local_url(host, port) + '/health', timeout=180)
    configure_ocr_tailscale(services, host, port)
    print('OCR ready. Models may still need a first document warmup. Ctrl+C stops this service.', flush=True)
    while True:
        services.check()
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", choices=["app", "youtube", "mobile", "ocr", "index"], default="app")
    parser.add_argument("--without-rag", action="store_true", help="Start only the backend and web dashboard")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the dashboard in a browser")
    args, extra = parser.parse_known_args()
    if extra and args.task not in {"youtube", "mobile", "index"}:
        parser.error("unrecognized arguments: " + " ".join(extra))
    if args.task != "app" and (args.without_rag or args.no_browser):
        parser.error("--without-rag and --no-browser apply only to the app task")
    sys.path.insert(0, str(ROOT))
    from shared.configuration import load_configuration
    load_configuration()
    os.chdir(ROOT)
    services = Services(launcher_name=f"{args.task}-launcher")
    print(f"Logs are saved in {services.log_dir}", flush=True)
    try:
        if args.task not in {"mobile", "ocr"}:
            require_packages(rag=args.task == "youtube" or not args.without_rag)
        with launcher_lock(args.task):
            try:
                if args.task == "mobile":
                    flutter = shutil.which("flutter")
                    if not flutter:
                        raise RuntimeError("Install Flutter and add its bin directory to PATH before starting mobile.")
                    # Only public client settings can enter the mobile build.
                    defines = []
                    for name in ('API_BASE_URL', 'SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY'):
                        if os.getenv(name) and not any(arg.startswith(f'--dart-define={name}=') for arg in extra):
                            defines.append(f'--dart-define={name}={os.environ[name]}')
                    process = services.start("mobile", [flutter, "run", *defines, *extra], cwd=ROOT / "mobile")
                    code = process.wait()
                    services.record(services.launcher_name, f"Mobile exited with code {code}",
                                    logging.ERROR if code else logging.INFO)
                    return code
                if args.task == 'ocr':
                    run_ocr_service(services)
                if args.task == 'index':
                    process = services.start('index-worker', [sys.executable, '-m', 'rag.index_worker', *extra])
                    return process.wait()
                if args.task == "youtube":
                    require_settings(["YOUTUBE_API_KEY"])
                    process = services.start("youtube", [sys.executable, "-m", "rag.app.youtube.pipeline", *extra])
                    return process.wait()
                run_app(services, args.without_rag, args.no_browser)
            finally:
                services.stop()
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        services.record(services.launcher_name, traceback.format_exc(), logging.ERROR)
        print(f"\nLauncher error: {error}", file=sys.stderr, flush=True)
        print(f"Details: {services.log_dir / (services.launcher_name + '.log')}", file=sys.stderr, flush=True)
        return 1
    finally:
        services.close_logs()


if __name__ == "__main__":
    # Next.js prints Unicode status markers even when Windows redirects stdout.
    # Keep log forwarding alive in consoles whose default encoding is cp1252.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, interrupt)
    sys.exit(main())
