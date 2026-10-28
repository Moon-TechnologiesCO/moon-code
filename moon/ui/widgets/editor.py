"""Code editor: syntax highlighting, IntelliSense, find/replace, diagnostics and smart editing."""

import re
from pathlib import Path

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Input, Static, TextArea
from textual.widgets.text_area import Selection

from moon.core import clipboard
from moon.core.completion import suggestions, word_at, word_before
from moon.core.languages import language_for
from moon.core.themes import PALETTES, editor_theme
from moon.services.intellisense import CompletionItem, Diagnostic, IntelliSense, Location as CodeLocation
from moon.ui.widgets.common import Clickable
from moon.ui.widgets.intellisense import CompletionMenu, HoverCard, SignatureHint

Location = tuple[int, int]

PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "`": "`"}
CLOSERS = {")", "]", "}", '"', "'", "`"}
MEMBER_ACCESS = (".", "->", "::")


class CodeEditor(TextArea):
    """TextArea with a file behind it, wired to IntelliSense."""

    BINDINGS = [
        Binding("ctrl+a", "select_all", "Select all", show=False),
        Binding("ctrl+space,ctrl+@", "trigger_suggest", "Suggest", show=False),
        Binding("f12", "go_to_definition", "Go to Definition", show=False),
        Binding("alt+h", "show_hover", "Show Hover", show=False),
    ]

    class DirtyChanged(Message):
        def __init__(self, editor: "CodeEditor") -> None:
            super().__init__()
            self.editor = editor

    class DiagnosticsChanged(Message):
        def __init__(self, editor: "CodeEditor") -> None:
            super().__init__()
            self.editor = editor

    class GoTo(Message):
        """Ask the workspace to open a location (go to definition)."""

        def __init__(self, location: CodeLocation) -> None:
            super().__init__()
            self.location = location

    def __init__(self, path: Path, text: str, *, theme: str, tab_size: int, line_numbers: bool,
                 word_wrap: bool, autocomplete: bool, intellisense: IntelliSense | None = None,
                 nerd: bool = True, **kwargs):
        super().__init__(text, show_line_numbers=line_numbers, tab_behavior="indent",
                         soft_wrap=word_wrap, **kwargs)
        self.path = path
        self.language_info = language_for(path)
        self.indent_width = tab_size
        self.indent_type = "spaces"
        self.autocomplete = autocomplete
        self.intellisense = intellisense
        self.nerd = nerd
        self.saved_text = text
        self.diagnostics: list[Diagnostic] = []
        self._was_dirty = False
        self._serial = 0
        self._anchor: tuple[int, int] | None = None
        self._items: list[CompletionItem] = []
        self._shown: list[CompletionItem] = []
        self._lint_timer: Timer | None = None
        self._hover_timer: Timer | None = None
        for palette in PALETTES:
            self.register_theme(editor_theme(palette))
        self.theme = theme
        if self.language_info.syntax in self.available_languages:
            self.language = self.language_info.syntax

    def on_mount(self) -> None:
        self._schedule_lint(0.2)

    def action_paste(self) -> None:
        text = clipboard.paste()  # what you copied in other apps, not only inside Moon Code
        if text is not None:
            self.app._clipboard = text  # TextArea pastes from the app's clipboard buffer
        super().action_paste()

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
        self._schedule_lint()

    @property
    def provider(self):
        return self.intellisense.provider_for(self.path) if self.intellisense else None

    def _floating(self, kind):
        widgets = self.screen.query(kind)
        return widgets.first() if widgets else None

    # --- Suggestions --------------------------------------------------------

    @property
    def menu(self) -> CompletionMenu | None:
        return self._floating(CompletionMenu)

    def _prefix(self) -> str:
        row, column = self.cursor_location
        return word_before(self.document.get_line(row), column)

    def action_trigger_suggest(self) -> None:
        self.trigger_completion(explicit=True)

    def trigger_completion(self, explicit: bool = False) -> None:
        if not self.autocomplete or self.menu is None:
            return
        row, column = self.cursor_location
        line = self.document.get_line(row)
        prefix = word_before(line, column)
        start = column - len(prefix)
        member = line[:start].endswith(MEMBER_ACCESS)
        if not (prefix or member or explicit):
            self.hide_completions()
            return
        anchor = (row, start)
        if anchor == self._anchor and self._items:
            self._render(prefix)  # same word: just filter what we already have
            return
        self._anchor = anchor
        current = word_at(line, column)
        words = suggestions(self.text, prefix, self.language_info.name, limit=12, current=current) if prefix else []
        self._items = [CompletionItem(word, "text") for word in words]
        self._render(prefix)
        if self.intellisense is not None:
            self._serial += 1
            serial, text = self._serial, self.text
            self.run_worker(lambda: self._fetch(serial, anchor, text, row, column),
                            thread=True, exclusive=True, group="suggest")

    def _fetch(self, serial: int, anchor, text: str, row: int, column: int) -> None:
        try:
            provider = self.provider
            items = provider.complete(self.path, text, row, column) if provider else []
        except Exception:  # A language server hiccup must never break typing.
            items = []
        self.app.call_from_thread(self._fetched, serial, anchor, items)

    def _fetched(self, serial: int, anchor, items: list[CompletionItem]) -> None:
        if serial != self._serial or anchor != self._anchor or not items:
            return
        smart = {item.label for item in items}
        self._items = items + [item for item in self._items if item.label not in smart]
        self._render(self._prefix())

    def _render(self, prefix: str) -> None:
        menu = self.menu
        if menu is None:
            return
        lowered = prefix.lower()
        items = self._items
        if not prefix.startswith("_"):  # like VS Code: _private and __dunder__ names only when you ask
            public = [item for item in items if not item.label.startswith("_")]
            items = public or items
        starts = [item for item in items if item.label.lower().startswith(lowered)]
        contains = [item for item in items if lowered and lowered in item.label.lower() and item not in starts]
        shown = (starts + contains)[:60]
        if not shown or (len(shown) == 1 and shown[0].label == prefix):
            menu.display = False
            return
        self._shown = shown
        width = menu.show_items(shown, prefix, self.nerd)
        x, y = self.cursor_screen_offset
        height = min(len(shown), 10) + 2
        screen_height = self.screen.size.height
        top = y + 1 if y + 1 + height <= screen_height else max(y - height, 0)
        menu.styles.width = width
        menu.styles.offset = (max(x - len(prefix) - 3, 0), top)
        menu.display = True

    def hide_completions(self) -> None:
        if self.menu is not None:
            self.menu.display = False
        self._anchor = None
        self._items = []

    def accept_completion(self) -> None:
        menu = self.menu
        if menu is None or menu.highlighted is None or not self._shown:
            return
        item = self._shown[menu.highlighted]
        row, column = self.cursor_location
        prefix = self._prefix()
        self.replace(item.insert or item.label, (row, column - len(prefix)), (row, column))
        self.hide_completions()

    # --- Signature help -----------------------------------------------------

    def _request_signature(self) -> None:
        if self.intellisense is None or self._floating(SignatureHint) is None:
            return
        row, column = self.cursor_location
        text = self.text

        def fetch() -> None:
            try:
                provider = self.provider
                signature = provider.signature(self.path, text, row, column) if provider else None
            except Exception:
                signature = None
            self.app.call_from_thread(self._show_signature, signature, (row, column))

        self.run_worker(fetch, thread=True, exclusive=True, group="signature")

    def _show_signature(self, signature, location) -> None:
        hint = self._floating(SignatureHint)
        if hint is None:
            return
        if signature is None or self.cursor_location[0] != location[0]:
            hint.display = False
            return
        hint.show_signature(signature)
        x, y = self.cursor_screen_offset
        lines = 2 if "\n" in str(hint.render()) else 1
        hint.styles.offset = (max(x - 2, 0), max(y - lines - 2, 0))
        hint.display = True

    def hide_signature(self) -> None:
        hint = self._floating(SignatureHint)
        if hint is not None:
            hint.display = False

    # --- Hover, definition --------------------------------------------------

    def action_show_hover(self) -> None:
        row, column = self.cursor_location
        x, y = self.cursor_screen_offset
        self._hover_at(row, column, (x, y + 1))

    def _hover_at(self, row: int, column: int, screen: tuple[int, int]) -> None:
        line = self.document.get_line(row) if row < self.document.line_count else ""
        problems = [d for d in self.diagnostics if d.line <= row <= d.end_line]
        if not word_at(line, column) and not problems:
            return
        text = self.text

        def fetch() -> None:
            try:
                provider = self.provider
                doc = provider.hover(self.path, text, row, column) if provider and word_at(line, column) else None
            except Exception:
                doc = None
            self.app.call_from_thread(self._show_hover, doc, problems, screen)

        self.run_worker(fetch, thread=True, exclusive=True, group="hover")

    def _show_hover(self, doc: str | None, problems: list[Diagnostic], screen: tuple[int, int]) -> None:
        card = self._floating(HoverCard)
        if card is None or not (doc or problems):
            return
        from rich.text import Text

        content = Text()
        for problem in problems:
            color = {"error": "#f7768e", "warning": "#e0af68"}.get(problem.severity, "#7dcfff")
            content.append(f"● {problem.message}", style=color)
            content.append(f"  {problem.source}\n" if problem.source else "\n", style="dim")
        if doc:
            if problems:
                content.append("\n")
            lines = doc.strip().split("\n")
            content.append(lines[0] + "\n", style="bold")
            content.append("\n".join(lines[1:18]).strip())
        card.update(content)
        x, y = screen
        card.styles.offset = (max(min(x, self.screen.size.width - 72), 0), y)
        card.display = True

    def hide_hover(self) -> None:
        card = self._floating(HoverCard)
        if card is not None:
            card.display = False

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._hover_timer is not None:
            self._hover_timer.stop()
        self.hide_hover()
        if self.intellisense is None:
            return
        row, column = self.get_target_document_location(event)
        screen = (event.screen_x, event.screen_y + 1)
        self._hover_timer = self.set_timer(0.7, lambda: self._hover_at(row, column, screen))

    def on_leave(self, event: events.Leave) -> None:
        if self._hover_timer is not None:
            self._hover_timer.stop()

    def action_go_to_definition(self) -> None:
        row, column = self.cursor_location
        self._definition_at(row, column)

    def _definition_at(self, row: int, column: int) -> None:
        if self.intellisense is None:
            return
        text = self.text

        def fetch() -> None:
            try:
                provider = self.provider
                location = provider.definition(self.path, text, row, column) if provider else None
            except Exception:
                location = None
            if location is None:
                self.app.call_from_thread(self.app.notify, "No definition found.", severity="warning")
            else:
                self.app.call_from_thread(self.post_message, self.GoTo(location))

        self.run_worker(fetch, thread=True, exclusive=True, group="definition")

    async def _on_click(self, event: events.Click) -> None:
        if event.ctrl:  # ctrl+click: go to definition, like VS Code
            row, column = self.get_target_document_location(event)
            self.move_cursor((row, column))
            self._definition_at(row, column)
            event.stop()
            return
        await super()._on_click(event)

    # --- Diagnostics --------------------------------------------------------

    def _schedule_lint(self, delay: float = 0.6) -> None:
        if self.intellisense is None or not self.is_mounted:
            return
        if self._lint_timer is not None:
            self._lint_timer.stop()
        self._lint_timer = self.set_timer(delay, self._lint)

    def _lint(self) -> None:
        text = self.text

        def run() -> None:
            try:
                provider = self.provider
                found = provider.diagnostics(self.path, text) if provider else None
            except Exception:
                found = None
            if found is not None:  # language servers push theirs through the workspace instead
                self.app.call_from_thread(self.set_diagnostics, found)

        self.run_worker(run, thread=True, exclusive=True, group="lint")

    def set_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = sorted(diagnostics, key=lambda d: (d.line, d.column))
        self._build_highlight_map()
        self.refresh()
        self.post_message(self.DiagnosticsChanged(self))

    def _build_highlight_map(self) -> None:
        super()._build_highlight_map()
        lines = self.document.lines
        for problem in getattr(self, "diagnostics", []):
            name = f"moon.{problem.severity}"
            for row in range(problem.line, min(problem.end_line, len(lines) - 1) + 1):
                text = lines[row] if row < len(lines) else ""
                start = problem.column if row == problem.line else 0
                end = problem.end_column if row == problem.end_line else len(text)
                if start >= end:  # zero-width problem: mark the word (or the line end) it points at
                    end = max(start + 1, start + len(re.match(r"\w*", text[start:]).group(0)))
                start_byte = len(text[:start].encode())
                end_byte = len(text[:end].encode())
                self._highlights[row].append((start_byte, end_byte if end_byte > start_byte else None, name))

    # --- Keys ---------------------------------------------------------------

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
            closed = False
            for widget in (menu, self._floating(SignatureHint), self._floating(HoverCard)):
                if widget is not None and widget.display:
                    widget.display = False
                    closed = True
            self._anchor = None
            if closed:
                event.prevent_default()
                event.stop()
                return
        self.hide_hover()
        if self._smart_edit(event):
            event.prevent_default()
            event.stop()
            self._after_typing(event)
            return
        await super()._on_key(event)
        self._after_typing(event)

    def _after_typing(self, event: events.Key) -> None:
        char = event.character or ""
        if char and (char.isalnum() or char == "_"):
            self.call_after_refresh(self.trigger_completion)
        elif char in (".", ">", ":"):
            self.call_after_refresh(self.trigger_completion)
        elif event.key == "backspace" and self.menu is not None and self.menu.display:
            self.call_after_refresh(self.trigger_completion)
        else:
            self.hide_completions()
        if char in ("(", ","):
            self.call_after_refresh(self._request_signature)
        elif char == ")" or event.key in ("enter", "up", "down"):
            self.hide_signature()

    def _on_blur(self, event: events.Blur) -> None:
        self.hide_completions()
        self.hide_signature()
        self.hide_hover()

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
