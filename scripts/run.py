"""Start the production services with the repository's .venv Python."""

import argparse
from contextlib import contextmanager
import importlib.metadata
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.parse import urlsplit
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
    def __init__(self):
        self.processes = []

    def start(self, name, command, cwd=None):
        print(f"Starting {name}...", flush=True)
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
                    print(f"[{name}] {line.rstrip()}", flush=True)

        threading.Thread(target=show_logs, daemon=True).start()
        return process

    def check(self):
        for name, process in self.processes:
            code = process.poll()
            if code is not None:
                raise RuntimeError(f"{name} stopped (exit code {code}). See its logs above.")

    def wait_http(self, name, url, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.check()
            try:
                with urlopen(url, timeout=1):
                    print(f"{name} is listening at {url}", flush=True)
                    return
            except (OSError, URLError):
                time.sleep(0.25)
        raise RuntimeError(f"{name} did not respond within {timeout} seconds. See its logs above.")

    def stop(self):
        print("\nStopping services started by this launcher...", flush=True)
        for _, process in reversed(self.processes):
            if os.name == "nt":
                # Include Next.js descendants; terminating only Node leaves the port occupied.
                if process.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 5
        for _, process in self.processes:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        if os.name != "nt":
            for _, process in self.processes:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


def require_packages(rag):
    packages = ["python-dotenv", "fastapi", "uvicorn", "supabase"]
    if rag:
        packages += ["sentence-transformers", "chromadb", "bm25s", "lingua-language-detector", "ollama"]
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
        raise RuntimeError("Configure these settings in the root .env: " + ", ".join(missing))


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


def start_ollama(services):
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    fallback = os.getenv("LLM_FALLBACK_ENABLED", "true").strip().lower() == "true"
    if provider != "ollama" and not fallback:
        return
    host = os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434"
    if urlsplit(host).hostname not in {"localhost", "127.0.0.1", "::1"}:
        print("Using the configured external Ollama server.", flush=True)
        return
    try:
        with urlopen(host.rstrip("/") + "/api/tags", timeout=2):
            print("Using the already-running Ollama server.", flush=True)
            return
    except (OSError, URLError):
        pass
    executable = shutil.which("ollama")
    if not executable:
        if provider == "ollama":
            raise RuntimeError("Install Ollama and pull OLLAMA_MODEL before using the Ollama provider.")
        print("Ollama is unavailable; optional local LLM fallback will be unavailable.", flush=True)
        return
    services.start("ollama", [executable, "serve"])
    services.wait_http("Ollama", host.rstrip("/") + "/api/tags")


def run_app(services, without_rag, no_browser):
    node = shutil.which("node")
    if not node or not (FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next").is_file():
        raise RuntimeError("Install Node.js and run npm ci in web first.")
    if not (FRONTEND / ".next" / "BUILD_ID").is_file():
        raise RuntimeError("Build the dashboard with npm --prefix web run build first.")
    require_settings(["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "JWT_SECRET"])
    backend_host = os.getenv("BACKEND_HOST") or "127.0.0.1"
    backend_port = int(os.getenv("BACKEND_PORT") or "8000")
    frontend_port = int(os.getenv("FRONTEND_PORT") or "3000")
    backend_url = local_url(backend_host, backend_port)
    frontend_url = f"http://localhost:{frontend_port}"
    port_available("Backend", backend_host, backend_port)
    port_available("Web dashboard", "0.0.0.0", frontend_port)
    if not without_rag:
        require_settings(["RAG_SERVICE_TOKEN"])
        rag_host = os.getenv("RAG_HTTP_HOST", "127.0.0.1")
        rag_port = int(os.getenv("RAG_HTTP_PORT", "8001"))
        rag_url = local_url(rag_host, rag_port)
        port_available("RAG API", rag_host, rag_port)
        # These defaults apply only to this launch; explicit .env values still win.
        os.environ.setdefault("RAG_SERVICE_URL", rag_url)
        os.environ.setdefault("RAG_BACKEND_URL", backend_url)
        start_ollama(services)
    services.start("backend", [sys.executable, "-m", "backend"])
    services.wait_http("Backend", backend_url + "/health")
    if not without_rag:
        services.start("rag", [sys.executable, "-m", "rag.service"])
        services.wait_http("RAG API", rag_url + "/openapi.json")
        services.start("index-worker", [sys.executable, "-m", "rag.index_worker"])
    services.start("web", [node, "scripts/next.mjs", "start"], cwd=FRONTEND)
    services.wait_http("Web dashboard", frontend_url + "/login")
    print(f"\nApp started: {frontend_url}/login\nAPI docs: {backend_url}/docs", flush=True)
    print("Listening checks do not verify Supabase, model access, or indexing success.", flush=True)
    print("Keep this terminal open. Press Ctrl+C to stop the app.\n", flush=True)
    if not no_browser:
        webbrowser.open(frontend_url + "/login")
    while True:
        services.check()
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", choices=["app", "youtube"], default="app")
    parser.add_argument("--without-rag", action="store_true", help="Start only the backend and web dashboard")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the dashboard in a browser")
    args, extra = parser.parse_known_args()
    if extra and args.task != "youtube":
        parser.error("unrecognized arguments: " + " ".join(extra))
    if args.task == "youtube" and (args.without_rag or args.no_browser):
        parser.error("--without-rag and --no-browser apply only to the app task")
    os.chdir(ROOT)
    services = Services()
    try:
        require_packages(rag=args.task == "youtube" or not args.without_rag)
        from dotenv import load_dotenv
        if not (ROOT / ".env").is_file():
            raise RuntimeError("Create and configure the root .env before launching. See README.md.")
        load_dotenv(ROOT / ".env")
        with launcher_lock("youtube" if args.task == "youtube" else "app"):
            try:
                if args.task == "youtube":
                    require_settings(["YOUTUBE_API_KEY"])
                    process = services.start("youtube", [sys.executable, "-m", "rag.app.youtube.pipeline", *extra])
                    return process.wait()
                run_app(services, args.without_rag, args.no_browser)
            finally:
                services.stop()
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError, ValueError) as error:
        print(f"\nLauncher error: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, interrupt)
    sys.exit(main())
