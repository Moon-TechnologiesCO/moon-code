"""Window chrome: macOS-style title bar, activity bar and status bar."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from moon.ui.widgets.common import Clickable

VIEWS = [
    ("explorer", "📁", "Explorer"),
    ("search", "🔍", "Search"),
    ("scm", "🌿", "Source Control"),
    ("extensions", "🧩", "Extensions"),
]


class TitleBar(Horizontal):
    """Traffic lights on the left, title centered, run button on the right."""

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        with Horizontal(id="traffic-lights"):
            yield Clickable("●", "app.request_quit", "Quit", classes="light close")
            yield Clickable("●", "screen.toggle_sidebar", "Toggle sidebar", classes="light minimize")
            yield Clickable("●", "screen.toggle_zen", "Zen mode", classes="light zoom")
        yield Static(self._title, id="title-text")
        with Horizontal(id="title-actions"):
            yield Clickable(" ▶ Run ", "screen.run_active", "Run active file (F5)", id="run-button")
            yield Clickable(" ⌘ ", "app.command_palette", "Command palette (F1)", classes="title-icon")

    def set_title(self, title: str) -> None:
        self._title = title
        self.query_one("#title-text", Static).update(title)


class ActivityBar(Vertical):
    """Icon column on the far left that switches the sidebar view."""

    def compose(self) -> ComposeResult:
        for view, icon, label in VIEWS:
            yield Clickable(icon, f"screen.show_view('{view}')", label, id=f"activity-{view}", classes="activity")
        yield Clickable("🤖", "screen.toggle_ai", "Moon AI (ctrl+l)", id="activity-ai", classes="activity")
        yield Static(classes="activity-spacer")
        yield Clickable("⚙", "screen.open_settings", "Settings", id="activity-settings", classes="activity")

    def set_active(self, view: str | None) -> None:
        for item in self.query(".activity"):
            item.set_class(item.id == f"activity-{view}", "active")


class StatusBar(Horizontal):
    """Bottom bar with branch, cursor position, indentation, language and theme."""

    def compose(self) -> ComposeResult:
        yield Static("", id="status-branch", classes="status-item")
        yield Clickable("", "app.install_update", "Install the update and restart", id="status-update", classes="status-item")
        yield Static(classes="status-spacer")
        yield Static("", id="status-cursor", classes="status-item")
        yield Static("", id="status-indent", classes="status-item")
        yield Static("UTF-8", classes="status-item")
        yield Static("LF", classes="status-item")
        yield Static("", id="status-language", classes="status-item")
        yield Clickable("", "screen.pick_theme", "Change color theme", id="status-theme", classes="status-item")

    def show(self, item: str, text: str) -> None:
        widget = self.query_one(f"#status-{item}", Static)
        widget.update(text)
        widget.display = bool(text)
