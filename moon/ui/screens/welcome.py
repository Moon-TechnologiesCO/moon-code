"""Start screen: logo, quick actions and recent projects."""

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

from moon import __version__
from moon.core.config import Settings
from moon.ui.dialogs import NewProjectDialog, OpenFolderDialog, PickDialog, PromptDialog, ShortcutsDialog
from moon.ui.widgets.chrome import TitleBar
from moon.ui.widgets.common import Clickable

LOGO = [
    "███╗   ███╗ ██████╗  ██████╗ ███╗   ██╗",
    "████╗ ████║██╔═══██╗██╔═══██╗████╗  ██║",
    "██╔████╔██║██║   ██║██║   ██║██╔██╗ ██║",
    "██║╚██╔╝██║██║   ██║██║   ██║██║╚██╗██║",
    "██║ ╚═╝ ██║╚██████╔╝╚██████╔╝██║ ╚████║",
    "╚═╝     ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝",
]
LOGO_COLORS = ["#c7d2fe", "#a5b4fc", "#93a8fb", "#7aa2f7", "#9d8cf5", "#bb9af7"]

MENU = [  # key, codicon, emoji fallback, label, action
    ("n", "\uea7f", "📄", "New File", "new_file"),
    ("o", "\ueaf7", "📂", "Open Folder", "open_folder"),
    ("p", "\ueb44", "✨", "New Project", "new_project"),
    ("r", "\uea82", "🕘", "Open Recent", "open_recent"),
    (".", "\ueaf4", "📍", "Open Current Folder", "open_current"),
    ("s", "\ueb51", "⚙️", "Settings", "open_settings"),
    ("k", "\U000f030c", "⌨️", "Keyboard Shortcuts", "shortcuts"),
    ("q", "\uea6e", "⏻", "Quit", "app.request_quit"),
]


def _short(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home):] if path.startswith(home) else path


class WelcomeScreen(Screen):
    BINDINGS = [Binding("full_stop" if key == "." else key, action, label, show=False) for key, _, _, label, action in MENU] + [
        Binding(str(n), f"open_recent_index({n - 1})", show=False) for n in range(1, 10)
    ] + [Binding("u", "app.install_update", "Update", show=False)]

    def __init__(self, settings: Settings, update: str | None = None):
        super().__init__()
        self.settings = settings
        self.update = update

    def compose(self) -> ComposeResult:
        yield TitleBar("Moon Code", self.settings.nerd_font)
        with Vertical(id="welcome-body"):
            with Center():
                yield Static(self._logo(), id="logo")
            with Center():
                yield Static("C   O   D   E", id="logo-subtitle")
            with Center():
                yield Static("The code editor that lives in your terminal", id="tagline")
            with Center():
                with Vertical(id="welcome-menu"):
                    for key, codicon, emoji, label, action in MENU:
                        target = action if "." in action else f"screen.{action}"
                        icon = codicon if self.settings.nerd_font else emoji
                        with Horizontal(classes="menu-row"):
                            yield Clickable(f"[$primary]{icon}[/]  {label}", target, classes="menu-label")
                            yield Static(key, classes="menu-key")
            recent = [p for p in self.settings.recent_projects if Path(p).is_dir()][:5]
            if recent:
                with Center():
                    with Vertical(id="welcome-recent"):
                        yield Static("Recent", classes="recent-title")
                        for index, path in enumerate(recent, start=1):
                            with Horizontal(classes="menu-row"):
                                yield Clickable(f"{Path(path).name}  [dim]{_short(path)}[/dim]",
                                                f"screen.open_recent_index({index - 1})", classes="menu-label")
                                yield Static(str(index), classes="menu-key")
            with Center():
                with Horizontal(id="welcome-update", classes="menu-row"):
                    yield Clickable("", "app.install_update", classes="menu-label", id="welcome-update-label")
                    yield Static("u", classes="menu-key")
            with Center():
                yield Static(self._footer(), id="welcome-footer")

    def on_mount(self) -> None:
        self.query_one("#run-button").display = False  # nothing to run before a folder is open
        self._show_update_row()

    def _logo(self) -> Text:
        text = Text(justify="left")
        for line, color in zip(LOGO, LOGO_COLORS):
            text.append(line + "\n", style=f"bold {color}")
        text.rstrip()
        return text

    def _footer(self) -> str:
        return f"v{__version__}  ·  Moon Technologies"

    def show_update(self, tag: str) -> None:
        self.update = tag
        if self.is_mounted:  # otherwise on_mount shows it once the screen exists
            self._show_update_row()

    def _show_update_row(self) -> None:
        row = self.query_one("#welcome-update")
        row.display = bool(self.update)
        if self.update:
            icon = "\ueba5" if self.settings.nerd_font else "⬆️"
            self.query_one("#welcome-update-label", Clickable).update(f"{icon}  Update to {self.update}")

    # --- Actions ------------------------------------------------------------

    def action_new_file(self) -> None:
        default = str(Path(self.settings.projects_dir) / "untitled.py")

        def create(value: str | None) -> None:
            if not value:
                return
            path = Path(value).expanduser().resolve()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=True)
            except OSError as error:
                self.notify(f"Couldn't create {path}: {error.strerror}", severity="error")
                return
            self.app.open_workspace(path.parent, path)

        self.app.push_screen(PromptDialog("New File", value=default, hint="Full path of the new file"), create)

    def action_open_folder(self) -> None:
        self.app.push_screen(OpenFolderDialog(Path.cwd()), self._open)

    def action_new_project(self) -> None:
        self.app.push_screen(NewProjectDialog(Path(self.settings.projects_dir)), self._open)

    def action_open_recent(self) -> None:
        items = [(_short(p), Path(p)) for p in self.settings.recent_projects if Path(p).is_dir()]
        if not items:
            self.notify("No recent folders yet.")
            return
        self.app.push_screen(PickDialog("Open Recent", items, "Recent folders"), self._open)

    def action_open_recent_index(self, index: int) -> None:
        recent = [p for p in self.settings.recent_projects if Path(p).is_dir()]
        if index < len(recent):
            self._open(Path(recent[index]))

    def action_open_current(self) -> None:
        self._open(Path.cwd())

    def action_open_settings(self) -> None:
        self.app.open_settings()

    def action_shortcuts(self) -> None:
        self.app.push_screen(ShortcutsDialog())

    def action_toggle_sidebar(self) -> None:
        """Title bar button; nothing to toggle on the welcome screen."""

    def action_toggle_zen(self) -> None:
        """Title bar button; nothing to toggle on the welcome screen."""

    def action_run_active(self) -> None:
        self.notify("Open a folder or file first.")

    def _open(self, folder: Path | None) -> None:
        if folder is not None:
            self.app.open_workspace(folder)
