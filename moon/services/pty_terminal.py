"""A shell running in a pseudo-terminal, with its screen emulated by pyte."""

import fcntl
import os
import pty
import signal
import struct
import termios
import warnings
from pathlib import Path

import pyte


def default_shell() -> str:
    return os.environ.get("SHELL") or "/bin/bash"


class PtySession:
    """Owns the shell process. The UI feeds keys in and draws `screen`."""

    def __init__(self, cwd: Path, columns: int = 80, rows: int = 24, shell: str | None = None):
        self.screen = pyte.HistoryScreen(columns, rows, history=2000)
        self.screen.set_mode(pyte.modes.LNM)
        self.stream = pyte.ByteStream(self.screen)
        self.alive = True

        with warnings.catch_warnings():
            # The child only calls exec, so forking from a threaded process is safe here.
            warnings.simplefilter("ignore", DeprecationWarning)
            pid, fd = pty.fork()
        if pid == 0:
            os.chdir(cwd)
            env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor", MOON_CODE="1")
            program = shell or default_shell()
            os.execvpe(program, [program], env)
        self.pid, self.fd = pid, fd
        self.resize(columns, rows)

    def read(self) -> bool:
        """Read whatever the shell printed. Returns False once the shell has exited."""
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            data = b""
        if not data:
            self.alive = False
            return False
        self.stream.feed(data)
        return True

    def write(self, data: bytes) -> None:
        if self.alive:
            try:
                os.write(self.fd, data)
            except OSError:
                self.alive = False

    def resize(self, columns: int, rows: int) -> None:
        columns, rows = max(columns, 10), max(rows, 2)
        self.screen.resize(rows, columns)
        try:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
        except OSError:
            pass

    def close(self) -> None:
        if self.alive:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            pass
        self.alive = False
