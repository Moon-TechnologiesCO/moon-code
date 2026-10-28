"""Code editor: syntax highlighting, autocomplete, find/replace and line comments."""

from pathlib import Path

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, OptionList, Static, TextArea
from textual.widgets.text_area import Selection

from moon.core.completion import suggestions, word_at, word_before
from moon.core.languages import language_for
from moon.core.themes import PALETTES, editor_theme
from moon.ui.widgets.common import Clickable

Location = tuple[int, int]

PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "`": "`"}
CLOSERS = {")", "]", "}", '"', "'", "`"}


class CompletionMenu(OptionList, can_focus=False):
    """Floating suggestion list. Keys are handled by the editor, so it never takes focus."""


class CodeEditor(TextArea):
    """TextArea with a file behind it."""

    BINDINGS = [Binding("ctrl+a", "select_all", "Select all", show=False)]

    class DirtyChanged(Message):
        def __init__(self, editor: "CodeEditor") -> None:
            super().__init__()
            self.editor = editor

    def __init__(self, path: Path, text: str, *, theme: str, tab_size: int, line_numbers: bool,
                 word_wrap: bool, autocomplete: bool, **kwargs):
        super().__init__(text, show_line_numbers=line_numbers, tab_behavior="indent",
                         soft_wrap=word_wrap, **kwargs)
        self.path = path
        self.language_info = language_for(path)
        self.indent_width = tab_size
        self.indent_type = "spaces"
        self.autocomplete = autocomplete
        self.saved_text = text
        self._was_dirty = False
        for palette in PALETTES:
            self.register_theme(editor_theme(palette))
        self.theme = theme
        if self.language_info.syntax in self.available_languages:
            self.language = self.language_info.syntax

    @property
    def dirty(self) -> bool:
        return self.text != self.saved_text

    def save(self) -> None:
        self.path.write_text(self.text, encoding="utf-8")
        self.saved_text = self.text
        self._notify_dirty()

    def reload(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        self.replace(text, (0, 0), self.document.end)
        self.saved_text = text
        self._notify_dirty()

    def _notify_dirty(self) -> None:
        if self.dirty != self._was_dirty:
            self._was_dirty = self.dirty
            self.post_message(self.DirtyChanged(self))

    @on(TextArea.Changed)
    def _changed(self) -> None:
        self._notify_dirty()

    # --- Autocomplete -------------------------------------------------------

    @property
    def menu(self) -> CompletionMenu | None:
        menus = self.screen.query(CompletionMenu)
        return menus.first() if menus else None

    def _prefix(self) -> str:
        row, column = self.cursor_location
        return word_before(self.document.get_line(row), column)

    def update_completions(self) -> None:
        menu = self.menu
        if menu is None:
            return
        prefix = self._prefix()
        row, column = self.cursor_location
        current = word_at(self.document.get_line(row), column)
        items = suggestions(self.text, prefix, self.language_info.name, current=current) if self.autocomplete else []
        if not items:
            menu.display = False
            return
        menu.clear_options()
        menu.add_options(items)
        menu.highlighted = 0
        x, y = self.cursor_screen_offset
        menu.styles.offset = (max(x - len(prefix), 0), y + 1)
        menu.display = True

    def hide_completions(self) -> None:
        if self.menu is not None:
            self.menu.display = False

    def accept_completion(self) -> None:
        menu = self.menu
        if menu is None or menu.highlighted is None:
            return
        word = str(menu.get_option_at_index(menu.highlighted).prompt)
        prefix = self._prefix()
        row, column = self.cursor_location
        self.replace(word, (row, column - len(prefix)), (row, column))
        menu.display = False

    async def _on_key(self, event: events.Key) -> None:
        menu = self.menu
        if menu is not None and menu.display:
            if event.key in ("down", "up"):
                menu.action_cursor_down() if event.key == "down" else menu.action_cursor_up()
                event.prevent_default()
                event.stop()
                return
            if event.key in ("tab", "enter"):
                self.accept_completion()
                event.prevent_default()
                event.stop()
                return
            if event.key == "escape":
                menu.display = False
                event.prevent_default()
                event.stop()
                return
        if self._smart_edit(event):
            event.prevent_default()
            event.stop()
            self.hide_completions()
            return
        await super()._on_key(event)
        if event.character and (event.character.isalnum() or event.character == "_"):
            self.call_after_refresh(self.update_completions)
        elif event.key == "backspace" and menu is not None and menu.display:
            self.call_after_refresh(self.update_completions)
        else:
            self.hide_completions()

    def _on_blur(self, event: events.Blur) -> None:
        self.hide_completions()

    # --- Smart editing: auto-indent, indent-aware backspace, bracket pairs -----

    def _smart_edit(self, event: events.Key) -> bool:
        """Handle the key like VS Code would. Returns True if it was handled."""
        if self.read_only or self.selected_text:
            return False
        row, column = self.cursor_location
        line = self.document.get_line(row)
        before, after = line[:column], line[column:]

        if event.key == "enter":
            indent = before[: len(before) - len(before.lstrip())]
            stripped = before.rstrip()
            if stripped.endswith((":", "{", "[", "(")):
                indent += " " * self.indent_width
            if stripped.endswith(("{", "[", "(")) and after[:1] in ("}", "]", ")"):
                closing_indent = indent[: max(len(indent) - self.indent_width, 0)]
                self.insert("\n" + indent + "\n" + closing_indent)
                self.move_cursor((row + 1, len(indent)))
            else:
                self.insert("\n" + indent)
            return True

        if event.key == "backspace" and before and not before.strip() and column % self.indent_width == 0:
            self.delete((row, column - self.indent_width), (row, column))
            return True

        if event.key == "backspace" and before and after and (before[-1], after[0]) in PAIRS.items():
            self.delete((row, column - 1), (row, column + 1))
            return True

        char = event.character
        if not char or len(char) != 1:
            return False
        if char in CLOSERS and after.startswith(char):
            self.move_cursor((row, column + 1))
            return True
        if char in PAIRS:
            is_quote = char in "\"'`"
            if is_quote and before[-1:].isalnum():
                return False
            if after[:1].isalnum() or after[:1] == "_":
                return False
            self.insert(char + PAIRS[char])
            self.move_cursor((row, column + 1))
            return True
        return False

    # --- Editing helpers ----------------------------------------------------

    def toggle_comment(self) -> None:
        token = self.language_info.comment
        if not token:
            return
        start, end = sorted(self.selection)
        rows = range(start[0], end[0] + 1)
        lines = [self.document.get_line(row) for row in rows]
        code_lines = [line for line in lines if line.strip()]
        commented = bool(code_lines) and all(line.lstrip().startswith(token) for line in code_lines)
        indent = min((len(l) - len(l.lstrip()) for l in code_lines), default=0)
        new_lines = []
        for line in lines:
            if not line.strip():
                new_lines.append(line)
            elif commented:
                position = line.index(token)
                cut = len(token) + (1 if line[position + len(token):position + len(token) + 1] == " " else 0)
                new_lines.append(line[:position] + line[position + cut:])
            else:
                new_lines.append(line[:indent] + token + " " + line[indent:])
        last = rows[-1]
        self.replace("\n".join(new_lines), (rows[0], 0), (last, len(self.document.get_line(last))))

    def go_to_line(self, line: int) -> None:
        row = min(max(line - 1, 0), self.document.line_count - 1)
        self.move_cursor((row, 0), center=True)

    def location_of(self, index: int) -> Location:
        before = self.text[:index]
        row = before.count("\n")
        return row, index - (before.rfind("\n") + 1)

    def index_of(self, location: Location) -> int:
        row, column = location
        lines = self.text.split("\n")
        return sum(len(line) + 1 for line in lines[:row]) + column

    def find_next(self, query: str, backwards: bool = False) -> bool:
        if not query:
            return False
        text, needle = self.text.lower(), query.lower()
        start, end = sorted(self.selection)
        if backwards:
            index = text.rfind(needle, 0, self.index_of(start))
            index = text.rfind(needle) if index < 0 else index
        else:
            index = text.find(needle, self.index_of(end))
            index = text.find(needle) if index < 0 else index
        if index < 0:
            return False
        self.selection = Selection(self.location_of(index), self.location_of(index + len(query)))
        self.scroll_cursor_visible(center=True)
        return True

    def count_matches(self, query: str) -> int:
        return self.text.lower().count(query.lower()) if query else 0

    def replace_current(self, query: str, replacement: str) -> None:
        start, end = sorted(self.selection)
        if self.get_text_range(start, end).lower() == query.lower() and query:
            self.replace(replacement, start, end)
        self.find_next(query)

    def replace_all(self, query: str, replacement: str) -> int:
        if not query:
            return 0
        import re

        pattern = re.compile(re.escape(query), re.IGNORECASE)
        new_text, count = pattern.subn(lambda _: replacement, self.text)
        if count:
            self.replace(new_text, (0, 0), self.document.end)
        return count


class FindBar(Horizontal):
    """Find (ctrl+f) and replace (ctrl+h) bar shown above the editor."""

    def compose(self) -> ComposeResult:
        with Vertical(id="find-fields"):
            yield Input(placeholder="Find", id="find-input")
            yield Input(placeholder="Replace", id="replace-input")
        with Vertical(id="find-actions"):
            with Horizontal():
                yield Static("", id="find-count")
                yield Clickable(" ↑ ", "screen.find_previous", "Previous match", classes="find-button")
                yield Clickable(" ↓ ", "screen.find_next", "Next match (Enter)", classes="find-button")
                yield Clickable(" ✕ ", "screen.close_find", "Close (Esc)", classes="find-button")
            with Horizontal(id="replace-actions"):
                yield Clickable(" Replace ", "screen.replace_one", "Replace (Enter)", classes="find-button")
                yield Clickable(" All ", "screen.replace_all", "Replace all", classes="find-button")

    def open(self, replace: bool, initial: str = "") -> None:
        self.display = True
        self.set_class(replace, "replace-mode")
        field = self.query_one("#find-input", Input)
        if initial:
            field.value = initial
        field.focus()

    @property
    def query_text(self) -> str:
        return self.query_one("#find-input", Input).value

    @property
    def replacement(self) -> str:
        return self.query_one("#replace-input", Input).value

    def show_count(self, count: int) -> None:
        self.query_one("#find-count", Static).update(f"{count} result{'s' if count != 1 else ''}" if self.query_text else "")
