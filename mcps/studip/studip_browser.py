"""Persistent, user-authenticated Firefox session for the Stud.IP API client."""

import json
import os
import queue
import threading
from concurrent.futures import Future
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


HOST = os.environ.get("STUDIP_BASE_URL", "https://studip.example.edu").rstrip("/")
_host_url = urlparse(HOST)
if _host_url.scheme != "https" or not _host_url.hostname:
    raise RuntimeError("STUDIP_BASE_URL must be an HTTPS URL")
ALLOWED_API_HOST = _host_url.hostname
DATA_DIR = Path(
    os.environ.get(
        "STUDIP_DATA_DIR",
        Path.home() / ".local" / "share" / "studip-mcp",
    )
).expanduser()
PROFILE_DIR = Path(
    os.environ.get("STUDIP_BROWSER_PROFILE_DIR", DATA_DIR / "browser-profile")
).expanduser()


class BrowserResponse:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", errors="replace")

    def json(self) -> dict:
        return json.loads(self.content)


class BrowserSession:
    """Make HTTP requests through a persistent browser context without exporting cookies."""

    def __init__(self) -> None:
        self._commands: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._start_error: Exception | None = None
        self._thread_lock = threading.Lock()

    def _ensure_worker(self) -> None:
        with self._thread_lock:
            if self._thread is None or not self._thread.is_alive():
                self._ready.clear()
                self._start_error = None
                self._thread = threading.Thread(
                    target=self._worker,
                    name="studip-browser-session",
                    daemon=True,
                )
                self._thread.start()

        if not self._ready.wait(timeout=30):
            raise RuntimeError("Timed out starting the Stud.IP browser session")
        if self._start_error:
            raise RuntimeError(f"Could not start the Stud.IP browser session: {self._start_error}")

    def _worker(self) -> None:
        try:
            playwright = sync_playwright().start()
        except Exception as exc:
            self._start_error = exc
            self._ready.set()
            return

        self._ready.set()
        context = None
        try:
            while True:
                operation, arguments, future = self._commands.get()
                if operation == "stop":
                    if context is not None:
                        context.close()
                    future.set_result(None)
                    return

                try:
                    if context is None:
                        PROFILE_DIR.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        PROFILE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
                        os.chmod(PROFILE_DIR.parent, 0o700)
                        os.chmod(PROFILE_DIR, 0o700)
                        context = playwright.firefox.launch_persistent_context(
                            user_data_dir=str(PROFILE_DIR),
                            headless=False,
                        )

                    if operation == "open_login":
                        page = context.pages[0] if context.pages else context.new_page()
                        page.goto(HOST, wait_until="domcontentloaded", timeout=60_000)
                        future.set_result({"opened": True, "url": page.url})
                    elif operation == "get":
                        response = context.request.get(
                            arguments["url"],
                            params=arguments["params"],
                            timeout=arguments["timeout_ms"],
                        )
                        future.set_result({
                            "status_code": response.status,
                            "content": response.body(),
                        })
                    else:
                        raise ValueError(f"Unknown browser-session operation: {operation}")
                except Exception as exc:
                    future.set_exception(exc)
        finally:
            if context is not None:
                context.close()
            playwright.stop()

    def _run(self, operation: str, **arguments):
        self._ensure_worker()
        future: Future = Future()
        self._commands.put((operation, arguments, future))
        try:
            return future.result(timeout=90)
        except PlaywrightError as exc:
            raise RuntimeError(f"Stud.IP browser operation failed: {exc}") from exc

    def open_login(self) -> dict:
        """Open Stud.IP in the dedicated browser for the user to sign in."""
        return self._run("open_login")

    def get(self, url: str, params: dict | None = None, timeout: int = 30) -> BrowserResponse:
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or parsed_url.hostname != ALLOWED_API_HOST:
            raise ValueError("The authenticated browser session only allows HTTPS requests to Stud.IP")
        result = self._run(
            "get",
            url=url,
            params=params,
            timeout_ms=timeout * 1000,
        )
        return BrowserResponse(result["status_code"], result["content"])

    def close(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            return
        future: Future = Future()
        self._commands.put(("stop", {}, future))
        future.result(timeout=30)
        self._thread.join(timeout=30)
