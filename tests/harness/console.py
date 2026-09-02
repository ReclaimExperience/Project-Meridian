"""The guest-exec channel: a serial console the harness can read and write.

PRD 7.4 calls for "a guest exec channel for assertions once booted". ADR-015
ships no SSH daemon and the image carries no guest agent, so the console is the
channel — the same one a support engineer would use, which is a point in its
favour: nothing exists in the image purely to be tested.

Everything read is mirrored into the serial log, so boot diagnosis is unchanged
and a failing run still leaves the full transcript behind as evidence.
"""

from __future__ import annotations

import re
import socket
import threading
import time
from pathlib import Path

# Matches a shell prompt at end of buffer: "[mtest@meridian ~]$ " / "# " / "$ ".
PROMPT = re.compile(r"[\$#]\s*$")
LOGIN_PROMPT = re.compile(r"login:\s*$", re.IGNORECASE)
PASSWORD_PROMPT = re.compile(r"password:\s*$", re.IGNORECASE)

# Escape sequences the shell and systemd emit. OSC must be listed first and
# must accept BOTH terminators: modern shells emit OSC 3008 session markers
# ending in ST (ESC backslash), not BEL, and a BEL-only pattern leaves the whole
# marker in the transcript — where it looked exactly like a failed systemd unit.
ANSI = re.compile(
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC ... BEL | ST
    r"|\][0-9]{2,};[^\x1b\n]*(?:\x1b\\)?"  # ST-terminated OSC with ESC already lost
    r"|\x1b\[[0-9;?]*[A-Za-z]"  # CSI
    r"|\x1b[=>]"  # keypad modes
)


class ConsoleError(RuntimeError):
    pass


class Console:
    """A bidirectional serial console."""

    def __init__(
        self,
        socket_path: str | Path,
        log_path: str | Path,
        connect_timeout: float = 60.0,
    ):
        self.socket_path = str(socket_path)
        self.log_path = Path(log_path)
        self._buffer = ""
        self._lock = threading.Lock()
        self._closed = threading.Event()

        deadline = time.monotonic() + connect_timeout
        while time.monotonic() < deadline:
            try:
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._sock.connect(self.socket_path)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(0.5)
        else:
            raise ConsoleError(f"serial socket {self.socket_path} never appeared")

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("w", buffering=1, errors="replace")
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    # ----------------------------------------------------------------- pump --

    def _pump(self) -> None:
        """Drain the socket forever, into both the buffer and the log."""
        while not self._closed.is_set():
            try:
                chunk = self._sock.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            with self._lock:
                self._buffer += text
            try:
                self._log.write(text)
            except ValueError:  # log closed underneath us during shutdown
                break

    def transcript(self) -> str:
        with self._lock:
            return self._buffer

    def close(self) -> None:
        self._closed.set()
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._sock.close()
        finally:
            if not self._log.closed:
                self._log.close()

    # ----------------------------------------------------------------- wait --

    def wait_for(
        self, pattern: str | re.Pattern, timeout: float = 120.0, poll: float = 0.5
    ) -> str:
        """Block until `pattern` appears in the transcript, or raise.

        This is how the harness waits for anything on the console. PRD WP-03
        forbids tests that sleep on a wall clock instead of waiting for a
        condition, and the failure message carries the tail of the transcript so
        a timeout is diagnosable without re-running.
        """
        compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if compiled.search(self._clean()):
                return self._clean()
            time.sleep(poll)
        tail = "\n  ".join(self._clean().strip().split("\n")[-25:])
        raise ConsoleError(
            f"timed out after {timeout:.0f}s waiting for {compiled.pattern!r}.\n"
            f"Last of the console:\n  {tail}"
        )

    def _clean(self) -> str:
        return ANSI.sub("", self.transcript())

    # ----------------------------------------------------------------- write --

    def send(self, text: str) -> None:
        self._sock.sendall(text.encode())

    def send_line(self, line: str = "") -> None:
        self.send(line + "\n")

    # ----------------------------------------------------------------- login --

    def login(self, user: str, password: str, timeout: float = 300.0) -> None:
        """Log in on the console, tolerating a getty that is not up yet.

        Nudges with a newline rather than assuming the prompt has already been
        printed: by the time the harness attaches, the login banner may have
        scrolled past or may not have been emitted at all.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.send_line()
            try:
                self.wait_for(LOGIN_PROMPT, timeout=10)
                break
            except ConsoleError:
                continue
        else:
            raise ConsoleError(
                f"no login prompt within {timeout:.0f}s — is a serial getty running?"
            )

        self.send_line(user)
        self.wait_for(PASSWORD_PROMPT, timeout=30)
        self.send_line(password)
        # A wrong password re-prompts rather than erroring, so watch for both.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            clean = self._clean()
            if re.search(r"Login incorrect", clean, re.IGNORECASE):
                raise ConsoleError(f"login as {user!r} was rejected")
            if PROMPT.search(clean.rstrip()):
                return
            time.sleep(0.5)
        raise ConsoleError(f"no shell prompt after logging in as {user!r}")

    # ------------------------------------------------------------------ run --

    def wait_until(
        self,
        command: str,
        predicate,
        timeout: float = 300.0,
        poll: float = 3.0,
        description: str = "",
    ) -> str:
        """Re-run `command` until `predicate(output)` holds, or raise.

        The harness's condition-wait primitive. PRD WP-03 forbids tests that
        sleep on a wall clock, and polling a real command is the difference
        between "the desktop is up" and "90 seconds have passed".
        """
        import time as _time

        deadline = _time.monotonic() + timeout
        last = ""
        while _time.monotonic() < deadline:
            _status, last = self.run(command, timeout=min(60.0, timeout))
            if predicate(last):
                return last
            _time.sleep(poll)
        raise ConsoleError(
            f"timed out after {timeout:.0f}s waiting for "
            f"{description or predicate!r} via {command!r}.\n"
            f"  last output: {last.strip()[:400]!r}"
        )

    def run(self, command: str, timeout: float = 60.0) -> tuple[int, str]:
        """Run a command, returning (exit_status, output).

        The exit status is fetched with a sentinel echo rather than parsed out
        of the prompt: a command whose output happens to look like a prompt
        would otherwise be read as having finished early.
        """
        marker = f"__done_{int(time.monotonic() * 1000)}__"
        with self._lock:
            self._buffer = ""
        self.send_line(f"{command}; echo {marker}$?")
        pattern = re.compile(rf"{marker}(\d+)")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            match = pattern.search(self._clean())
            if match:
                output = self._clean()
                body = output.split(f"echo {marker}$?", 1)[-1]
                body = pattern.split(body)[0]
                return int(match.group(1)), body.strip()
            time.sleep(0.3)
        tail = "\n  ".join(self._clean().strip().split("\n")[-25:])
        raise ConsoleError(
            f"command timed out after {timeout:.0f}s: {command!r}\n"
            f"Last of the console:\n  {tail}"
        )
