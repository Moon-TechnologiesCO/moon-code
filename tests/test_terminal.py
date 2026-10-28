import select
import time

from moon.services.pty_terminal import PtySession
from moon.ui.widgets.terminal import key_to_bytes


def test_key_mapping():
    assert key_to_bytes("enter", None) == b"\r"
    assert key_to_bytes("ctrl+c", None) == b"\x03"
    assert key_to_bytes("up", None, app_cursor=True) == b"\x1bOA"
    assert key_to_bytes("a", "a") == b"a"


def test_pty_session_runs_commands(tmp_path):
    session = PtySession(tmp_path, 60, 6, shell="/bin/sh")
    session.write(b"echo moon-ok\r")
    deadline = time.time() + 5
    while time.time() < deadline and "moon-ok" not in "".join(session.screen.display[1:]):
        if select.select([session.fd], [], [], 0.1)[0]:
            session.read()
    session.close()
    assert any("moon-ok" in line for line in session.screen.display[1:])
