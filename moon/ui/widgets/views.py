"""Sidebar views: Explorer, Search, Source Control, Extensions and the Moon AI chat."""

from collections.abc import Iterable
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Checkbox, DirectoryTree, Input, OptionList, Select, Static, Switch
from textual.widgets.option_list import Option

from moon.core import files, git
from moon.core.icons import icon_text
from moon.extensions import Extension
from moon.services import ollama
from moon.ui.widgets.common import Clickable, SectionTitle


class OpenFile(Message):
    """Ask the workspace to open a file (optionally at a line)."""

    def __init__(self, path: Path, line: int | None = None, focus: bool = True) -> None:
        super().__init__()
        self.path = path
        self.line = line
        self.focus = focus


# --- Explorer ---------------------------------------------------------------


class ExplorerAction(Message):
    """Ask the workspace to do something with a file or folder (rename, delete, new_file…)."""

    def __init__(self, action: str, path: Path, mouse: tuple[int, int] | None = None) -> None:
        super().__init__()
        self.action = action
        self.path = path
        self.mouse = mouse


class ProjectTree(DirectoryTree):
    """Directory tree with file icons that hides dependency/build folders."""

    BINDINGS = [
        Binding("f2", "explorer('rename')", "Rename", show=False),
        Binding("delete", "explorer('delete')", "Delete", show=False),
        Binding("shift+f10,menu", "explorer('menu')", "Menu", show=False),
    ]

    GIT_COLORS = {"M": "#e2c08d", "A": "#81b88b", "?": "#73c991", "D": "#c74e39", "R": "#73c991", "U": "#e5534b"}

    def __init__(self, path: Path, nerd: bool, **kwargs):
        super().__init__(path, **kwargs)
        self.nerd = nerd
        self.git_status: dict[Path, str] = {}  # file or folder -> status letter, like VS Code's decorations

    def set_git_status(self, changes: list[tuple[str, str]]) -> None:
        status: dict[Path, str] = {}
        root = Path(self.path).resolve()
        for code, relative in changes:
            letter = "U" if code in ("??", "?") else code[0]
            path = root / relative.split(" -> ")[-1].rstrip("/")
            status[path] = letter
            for parent in path.parents:  # folders show that something inside changed
                if parent == root or root not in parent.parents:
                    break
                status.setdefault(parent, "•")
        self.git_status = status
        self.refresh()

    @property
    def selected_path(self) -> Path:
        node = self.cursor_node
        return Path(node.data.path) if node is not None and node.data is not None else Path(self.path)

    def action_explorer(self, action: str) -> None:
        mouse = None
        if action == "menu" and self.cursor_node is not None:
            region = self.content_region
            mouse = (region.x + 4, region.y + self.cursor_line - self.scroll_offset.y + 1)
        self.post_message(ExplorerAction(action, self.selected_path, mouse))

    async def _on_click(self, event: events.Click) -> None:
        if event.button == 3:  # right click: select the row under the mouse and open the menu
            line = event.y + self.scroll_offset.y
            node = self.get_node_at_line(line)
            if node is not None:
                self.move_cursor(node)
            self.focus()
            event.stop()
            self.post_message(ExplorerAction("menu", self.selected_path, (event.screen_x, event.screen_y)))
            return
        await super()._on_click(event)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [p for p in paths if p.name not in files.IGNORED_DIRS and p.name != ".DS_Store"]

    def render_label(self, node, base_style, style) -> Text:
        path = Path(node.data.path)
        label = icon_text(path, self.nerd, expanded=node.is_expanded)
        label.append(" ")
        status = self.git_status.get(path.resolve())
        name_style = style
        if status:
            color = self.GIT_COLORS.get(status, "#e2c08d")
            name_style = style + Style(color=color)
        label.append(path.name, name_style)
        if status:
            label.append(f"  {status}", Style(color=self.GIT_COLORS.get(status, "#8a93b8"), dim=status == "•"))
        if path.name.startswith(".") and not status:
            label.stylize("dim", 2)
        return label


class ExplorerView(Vertical):
    def __init__(self, root: Path, nerd: bool, **kwargs):
        super().__init__(**kwargs)
        self.root = root
        self.nerd = nerd

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-header"):
            yield SectionTitle("EXPLORER")
            yield Clickable(" ＋ ", "screen.new_file", "New file", classes="view-action")
            yield Clickable(" 🗀 ", "screen.new_folder", "New folder", classes="view-action")
            yield Clickable(" ⟳ ", "screen.refresh_explorer", "Refresh", classes="view-action")
        yield Static(self.root.name.upper() or str(self.root), classes="project-name")
        yield ProjectTree(self.root, self.nerd, id="project-tree")

    @on(DirectoryTree.FileSelected)
    def _open(self, event: DirectoryTree.FileSelected) -> None:
        # Like VS Code: the first click opens the file and keeps you in the explorer;
        # selecting the file that is already open moves the cursor into the editor.
        event.stop()
        self.post_message(OpenFile(Path(event.path), focus=False))

    def reload(self) -> None:
        self.query_one(ProjectTree).reload()


# --- Search -----------------------------------------------------------------


class SearchView(Vertical):
    def __init__(self, root: Path, **kwargs):
        super().__init__(**kwargs)
        self.root = root
        self.matches: list[files.Match] = []

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-header"):
            yield SectionTitle("SEARCH")
        yield Input(placeholder="Search in files (Enter)", id="search-input")
        yield Static("", id="search-summary", classes="muted")
        yield OptionList(id="search-results")

    def focus_input(self) -> None:
        self.query_one("#search-input", Input).focus()

    @on(Input.Submitted, "#search-input")
    def _submit(self, event: Input.Submitted) -> None:
        event.stop()
        self.query_one("#search-summary", Static).update("Searching…")
        self._search(event.value.strip())

    @work(thread=True, exclusive=True)
    def _search(self, query: str) -> None:
        matches = files.search(self.root, query)
        self.app.call_from_thread(self._show, query, matches)

    def _show(self, query: str, matches: list[files.Match]) -> None:
        self.matches = matches
        results = self.query_one("#search-results", OptionList)
        results.clear_options()
        for match in matches:
            text = Text.assemble((f"{match.path}", "bold"), (f":{match.line}  ", "dim"), match.text[:120])
            results.add_option(Option(text))
        count = len(matches)
        summary = f"{count} result{'s' if count != 1 else ''}" if query else ""
        self.query_one("#search-summary", Static).update(summary)

    @on(OptionList.OptionSelected, "#search-results")
    def _open(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        match = self.matches[event.option_index]
        self.post_message(OpenFile(self.root / match.path, match.line))


# --- Source control -----------------------------------------------------------


class ScmView(Vertical):
    STATUS_LABELS = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed", "?": "untracked", "??": "untracked"}

    def __init__(self, root: Path, **kwargs):
        super().__init__(**kwargs)
        self.root = root
        self.changes: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-header"):
            yield SectionTitle("SOURCE CONTROL")
            yield Clickable(" ⟳ ", "screen.refresh_scm", "Refresh", classes="view-action")
        yield Static("", id="scm-branch", classes="muted")
        yield OptionList(id="scm-changes")
        yield Static("Tip: run git commands in the terminal (ctrl+j).", classes="muted hint")

    def refresh_changes(self) -> None:
        self._load()

    @work(thread=True, exclusive=True)
    def _load(self) -> None:
        branch = git.branch(self.root)
        changes = git.changes(self.root)
        self.app.call_from_thread(self._show, branch, changes)

    def _show(self, branch: str | None, changes: list[tuple[str, str]]) -> None:
        self.changes = changes
        header = self.query_one("#scm-branch", Static)
        header.update(f"⎇ {branch} · {len(changes)} change{'s' if len(changes) != 1 else ''}" if branch else "Not a git repository.")
        options = self.query_one("#scm-changes", OptionList)
        options.clear_options()
        for status, path in changes:
            label = self.STATUS_LABELS.get(status, status)
            options.add_option(Option(Text.assemble((f"{status:>2} ", "bold"), path, (f"  {label}", "dim"))))

    @on(OptionList.OptionSelected, "#scm-changes")
    def _open(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        path = self.root / self.changes[event.option_index][1]
        if path.is_file():
            self.post_message(OpenFile(path))


# --- Extensions ---------------------------------------------------------------


class ExtensionToggled(Message):
    def __init__(self, extension_id: str, enabled: bool) -> None:
        super().__init__()
        self.extension_id = extension_id
        self.enabled = enabled


class ExtensionCard(Horizontal):
    def __init__(self, extension: Extension, enabled: bool, **kwargs):
        super().__init__(classes="extension-card", **kwargs)
        self.extension = extension
        self.enabled = enabled

    def compose(self) -> ComposeResult:
        yield Static(self.extension.icon, classes="extension-icon")
        with Vertical(classes="extension-text"):
            badge = "built-in" if self.extension.builtin else "user"
            yield Static(Text.assemble((self.extension.name, "bold"), (f"  {badge}", "dim")))
            yield Static(self.extension.description, classes="muted")
        yield Switch(value=self.enabled, classes="extension-switch")

    @on(Switch.Changed)
    def _toggle(self, event: Switch.Changed) -> None:
        event.stop()
        self.post_message(ExtensionToggled(self.extension.id, event.value))


class ExtensionsView(Vertical):
    def __init__(self, extensions: list[Extension], disabled: list[str], folder: Path, **kwargs):
        super().__init__(**kwargs)
        self.extensions = extensions
        self.disabled = disabled
        self.folder = folder

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-header"):
            yield SectionTitle("EXTENSIONS")
            yield Clickable(" ＋ ", "screen.create_extension", "Create an extension", classes="view-action")
        with VerticalScroll(id="extension-list"):
            for extension in self.extensions:
                yield ExtensionCard(extension, extension.id not in self.disabled)
        yield Static(f"Your extensions live in:\n{self.folder}", classes="muted hint")


# --- Moon AI ------------------------------------------------------------------


class AIChatView(Vertical):
    """Chat with a local Ollama model, optionally about the active file."""

    def __init__(self, model: str, url: str, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.url = url
        self.history: list[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-header"):
            yield SectionTitle("MOON AI")
            yield Clickable(" 🗑 ", "screen.clear_ai", "Clear chat", classes="view-action")
            yield Clickable(" ✕ ", "screen.toggle_ai", "Close", classes="view-action")
        yield Select([(self.model, self.model)], value=self.model, allow_blank=False, id="ai-model")
        yield VerticalScroll(Static("Ask anything about your code. Runs locally with Ollama.", classes="muted"), id="ai-log")
        yield Checkbox("Include active file", value=True, id="ai-context")
        yield Input(placeholder="Ask Moon AI… (Enter)", id="ai-input")

    def on_mount(self) -> None:
        self._load_models()

    @work(thread=True)
    def _load_models(self) -> None:
        models = ollama.list_models(self.url)
        self.app.call_from_thread(self._set_models, models)

    def _set_models(self, models: list[str]) -> None:
        if not models:
            self.query_one("#ai-log", VerticalScroll).mount(
                Static("Ollama isn't running. Install it from ollama.com and run `ollama pull gemma3n:e2b`.", classes="ai-error"))
            return
        select = self.query_one("#ai-model", Select)
        select.set_options([(m, m) for m in models])
        select.value = self.model if self.model in models else models[0]

    @on(Select.Changed, "#ai-model")
    def _model_changed(self, event: Select.Changed) -> None:
        if isinstance(event.value, str):
            self.model = event.value

    @property
    def include_file(self) -> bool:
        return self.query_one("#ai-context", Checkbox).value

    def clear(self) -> None:
        self.history.clear()
        log = self.query_one("#ai-log", VerticalScroll)
        log.remove_children()

    def ask(self, question: str, context: str | None = None) -> None:
        log = self.query_one("#ai-log", VerticalScroll)
        log.mount(Static(Text.assemble(("You  ", "bold"), question), classes="ai-question"))
        reply = Static("…", classes="ai-reply")
        log.mount(reply)
        log.scroll_end(animate=False)
        content = f"{question}\n\n{context}" if context else question
        self.history.append({"role": "user", "content": content})
        self._stream(reply)

    @work(thread=True, exclusive=True)
    def _stream(self, reply: Static) -> None:
        system = {"role": "system", "content": "You are Moon AI, a concise coding assistant inside the Moon Code editor."}
        text = ""
        try:
            for piece in ollama.stream_chat(self.model, [system, *self.history], self.url):
                text += piece
                self.app.call_from_thread(reply.update, text)
        except OSError as error:
            text = f"Couldn't reach Ollama at {self.url}: {error}"
            self.app.call_from_thread(reply.update, text)
        self.history.append({"role": "assistant", "content": text})
        self.app.call_from_thread(self.query_one("#ai-log", VerticalScroll).scroll_end, animate=False)
