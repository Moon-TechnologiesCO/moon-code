"""Integrated terminal widget: draws a PtySession and sends it the keys you type."""

import asyncio
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widget import Widget

from moon.core.themes import Palette
from moon.services.pty_terminal import PtySession

ANSI_NAMES = ["black", "red", "green", "brown", "blue", "magenta", "cyan", "white"]

# pyte stores private modes shifted by 5; this is "cursor keys in application mode" (ESC[?1h).
DECCKM = 1 << 5

KEY_BYTES = {
    "enter": b"\r", "tab": b"\t", "shift+tab": b"\x1b[Z", "backspace": b"\x7f", "escape": b"\x1b",
    "delete": b"\x1b[3~", "insert": b"\x1b[2~", "home": b"\x1b[H", "end": b"\x1b[F",
    "pageup": b"\x1b[5~", "pagedown": b"\x1b[6~",
    "up": b"\x1b[A", "down": b"\x1b[B", "right": b"\x1b[C", "left": b"\x1b[D",
    "ctrl+left": b"\x1b[1;5D", "ctrl+right": b"\x1b[1;5C",
    "f1": b"\x1bOP", "f2": b"\x1bOQ", "f3": b"\x1bOR", "f4": b"\x1bOS",
    "f6": b"\x1b[17~", "f7": b"\x1b[18~", "f8": b"\x1b[19~", "f9": b"\x1b[20~",
    "f10": b"\x1b[21~", "f11": b"\x1b[23~", "f12": b"\x1b[24~",
}
APP_CURSOR = {"up": b"\x1bOA", "down": b"\x1bOB", "right": b"\x1bOC", "left": b"\x1bOD"}


def key_to_bytes(key: str, character: str | None, app_cursor: bool = False) -> bytes | None:
    if app_cursor and key in APP_CURSOR:
        return APP_CURSOR[key]
    if key in KEY_BYTES:
        return KEY_BYTES[key]
    if key.startswith("ctrl+") and len(key) == 6 and key[-1].isalpha():
        return bytes([ord(key[-1]) & 0x1F])
    if key.startswith("alt+") and character:
        return b"\x1b" + character.encode()
    if character:
        return character.encode()
    return None


class TerminalView(Widget, can_focus=True):
    """A real shell inside the editor."""

    class Exited(Message):
        pass

    def __init__(self, cwd: Path, palette: Palette, **kwargs):
        super().__init__(**kwargs)
        self.cwd = cwd
        self.palette = palette
        self.session: PtySession | None = None
        self._pending: list[str] = []

    # --- Lifecycle ----------------------------------------------------------

    def _start(self) -> None:
        width, height = max(self.size.width, 20), max(self.size.height, 3)
        self.session = PtySession(self.cwd, width, height)
        asyncio.get_running_loop().add_reader(self.session.fd, self._on_output)
        for command in self._pending:
            self.session.write(command.encode() + b"\r")
        self._pending.clear()

    def _stop(self) -> None:
        if self.session is not None:
            try:
                asyncio.get_running_loop().remove_reader(self.session.fd)
            except (RuntimeError, ValueError, OSError):
                pass
            self.session.close()
            self.session = None

    def restart(self) -> None:
        self._stop()
        if self.size.width:
            self._start()
        self.refresh()

    def on_resize(self, event: events.Resize) -> None:
        if not event.size.width or not event.size.height:
            return
        if self.session is None:
            self._start()
        else:
            self.session.resize(event.size.width, event.size.height)
        self.refresh()

    def on_unmount(self) -> None:
        self._stop()

    def _on_output(self) -> None:
        if self.session is None:
            return
        if not self.session.read():
            self._stop()
            self.post_message(self.Exited())
        self.refresh()

    # --- Input --------------------------------------------------------------

    def run(self, command: str) -> None:
        """Type a command into the shell and press Enter."""
        if self.session is None:
            self._pending.append(command)
            if self.size.width:
                self._start()
            return
        self.session.write(b"\x15" + command.encode() + b"\r")  # ctrl+u clears what was typed first

    def on_key(self, event: events.Key) -> None:
        if self.session is None:
            if event.key == "enter":
                self.restart()
            event.stop()
            return
        app_cursor = DECCKM in self.session.screen.mode
        data = key_to_bytes(event.key, event.character, app_cursor)
        if data is not None:
            self.session.write(data)
            event.stop()
            event.prevent_default()

    def on_paste(self, event: events.Paste) -> None:
        if self.session is not None:
            self.session.write(event.text.encode())
        event.stop()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        if self.session is not None:
            self.session.screen.prev_page()
            self.refresh()
        event.stop()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        if self.session is not None:
            self.session.screen.next_page()
            self.refresh()
        event.stop()

    # --- Drawing ------------------------------------------------------------

    def _color(self, value: str, foreground: bool) -> str | None:
        if value == "default":
            return self.palette.foreground if foreground else None
        bright = value.startswith("bright")
        name = value.removeprefix("bright")
        if name in ANSI_NAMES:
            return self.palette.ansi[ANSI_NAMES.index(name) + (8 if bright else 0)]
        if len(value) == 6:
            return f"#{value}"
        return None

    def render(self) -> Text:
        if self.session is None:
            return Text("Terminal closed. Press Enter to start a new shell.", style=self.palette.muted)
        screen = self.session.screen
        cursor_x, cursor_y = screen.cursor.x, screen.cursor.y
        show_cursor = self.has_focus and not screen.cursor.hidden
        output = Text(no_wrap=True, overflow="crop")
        for y in range(screen.lines):
            row = screen.buffer[y]
            for x in range(screen.columns):
                char = row[x]
                fg = self._color(char.fg, True)
                bg = self._color(char.bg, False)
                if char.reverse:
                    fg, bg = bg or self.palette.background, fg
                style = Style(color=fg, bgcolor=bg, bold=char.bold, italic=char.italics,
                              underline=char.underscore)
                if show_cursor and x == cursor_x and y == cursor_y:
                    style = Style(color=self.palette.background, bgcolor=self.palette.foreground)
                output.append(char.data or " ", style)
            if y < screen.lines - 1:
                output.append("\n")
        return output
