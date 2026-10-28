"""Modal dialogs: quick open, pickers, prompts, open folder and new project."""

from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, OptionList, Select, Static
from textual.widgets.option_list import Option

from moon.core import files
from moon.core.icons import icon_text
from moon.core.projects import TEMPLATES, create_project


class Dialog(ModalScreen):
    """Base for all dialogs: Escape closes with no result."""

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class PickDialog(Dialog):
    """Filterable list (Quick Open, Open Recent, Color Theme…). Returns the chosen value."""

    def __init__(self, title: str, items: list[tuple[str, object]], placeholder: str = "Type to filter",
                 fuzzy: bool = True, nerd: bool = False, file_icons: bool = False):
        super().__init__(classes="dialog-screen")
        self.title_text = title
        self.items = items
        self.placeholder = placeholder
        self.fuzzy = fuzzy
        self.nerd = nerd
        self.file_icons = file_icons
        self.shown: list[tuple[str, object]] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog picker"):
            yield Static(self.title_text, classes="dialog-title")
            yield Input(placeholder=self.placeholder, id="picker-input")
            yield OptionList(id="picker-options")

    def on_mount(self) -> None:
        self._filter("")

    @on(Input.Changed, "#picker-input")
    def _changed(self, event: Input.Changed) -> None:
        self._filter(event.value)

    def _filter(self, query: str) -> None:
        labels = [label for label, _ in self.items]
        if self.fuzzy and query:
            lookup = dict(self.items)
            self.shown = [(label, lookup[label]) for label in files.fuzzy_filter(query, labels, limit=60)]
        else:
            self.shown = [(l, v) for l, v in self.items if query.lower() in l.lower()][:200]
        options = self.query_one("#picker-options", OptionList)
        options.clear_options()
        for label, _ in self.shown:
            if self.file_icons:
                path = Path(label)
                name, parent = path.name, str(path.parent) if str(path.parent) != "." else ""
                options.add_option(Option(Text.assemble(icon_text(path, self.nerd), " ", (name, "bold"), (f"  {parent}", "dim"))))
            else:
                options.add_option(Option(label))
        if self.shown:
            options.highlighted = 0

    def on_key(self, event) -> None:
        options = self.query_one("#picker-options", OptionList)
        if event.key == "down":
            options.action_cursor_down()
            event.stop()
        elif event.key == "up":
            options.action_cursor_up()
            event.stop()

    @on(Input.Submitted, "#picker-input")
    def _submit(self) -> None:
        options = self.query_one("#picker-options", OptionList)
        if options.highlighted is not None and self.shown:
            self.dismiss(self.shown[options.highlighted][1])

    @on(OptionList.OptionSelected, "#picker-options")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.shown[event.option_index][1])


class PromptDialog(Dialog):
    """Single text field. Returns the text, or None when cancelled."""

    def __init__(self, title: str, placeholder: str = "", value: str = "", hint: str = ""):
        super().__init__(classes="dialog-screen")
        self.title_text = title
        self.placeholder = placeholder
        self.value = value
        self.hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog prompt"):
            yield Static(self.title_text, classes="dialog-title")
            yield Input(value=self.value, placeholder=self.placeholder, id="prompt-input")
            if self.hint:
                yield Static(self.hint, classes="muted")

    @on(Input.Submitted)
    def _submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)


class ConfirmDialog(Dialog):
    """Yes / No question. Returns True or False (None if dismissed)."""

    def __init__(self, title: str, message: str, yes: str = "Yes", no: str = "Cancel"):
        super().__init__(classes="dialog-screen")
        self.title_text, self.message, self.yes, self.no = title, message, yes, no

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog confirm"):
            yield Static(self.title_text, classes="dialog-title")
            yield Static(self.message)
            with Horizontal(classes="dialog-buttons"):
                yield Button(self.no, id="no")
                yield Button(self.yes, id="yes", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#yes", Button).focus()

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class FolderTree(DirectoryTree):
    def filter_paths(self, paths):
        return [p for p in paths if p.is_dir() and not p.name.startswith(".")]


class OpenFolderDialog(Dialog):
    """Browse to a folder or type its path. Returns the folder."""

    def __init__(self, start: Path):
        super().__init__(classes="dialog-screen")
        self.start = start

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog folder"):
            yield Static("Open Folder", classes="dialog-title")
            yield Input(value=str(self.start), id="folder-path")
            yield FolderTree(Path.home(), id="folder-tree")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Open", id="open", variant="primary")

    @on(DirectoryTree.DirectorySelected)
    def _picked(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#folder-path", Input).value = str(event.path)

    @on(Input.Submitted, "#folder-path")
    def _submit(self) -> None:
        self._open()

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open":
            self._open()
        else:
            self.dismiss(None)

    def _open(self) -> None:
        path = Path(self.query_one("#folder-path", Input).value).expanduser()
        if path.is_dir():
            self.dismiss(path.resolve())
        else:
            self.notify(f"{path} is not a folder.", severity="error")


class NewProjectDialog(Dialog):
    """Name + template + location. Creates the project and returns its folder."""

    def __init__(self, projects_dir: Path):
        super().__init__(classes="dialog-screen")
        self.projects_dir = projects_dir

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog project"):
            yield Static("New Project", classes="dialog-title")
            yield Static("Name", classes="field-label")
            yield Input(placeholder="my-app", id="project-name")
            yield Static("Template", classes="field-label")
            yield Select([(t.name, t.id) for t in TEMPLATES], value="python", allow_blank=False, id="project-template")
            yield Static("Location", classes="field-label")
            yield Input(value=str(self.projects_dir), id="project-location")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Create", id="create", variant="primary")

    @on(Input.Submitted)
    def _submit(self) -> None:
        self._create()

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self._create()
        else:
            self.dismiss(None)

    def _create(self) -> None:
        name = self.query_one("#project-name", Input).value
        template = self.query_one("#project-template", Select).value
        location = Path(self.query_one("#project-location", Input).value).expanduser()
        try:
            folder = create_project(location, name, str(template))
        except (ValueError, FileExistsError, OSError) as error:
            self.notify(str(error), severity="error")
            return
        self.dismiss(folder)


class ContextMenu(Dialog):
    """Right-click menu at the mouse position. Returns the chosen action id."""

    def __init__(self, items: list[tuple[str, str, str]], x: int, y: int):
        """`items` are (label, shortcut, action id); a label of "-" draws a separator."""
        super().__init__(classes="context-screen")
        self.items = items
        self.position = (x, y)

    def compose(self) -> ComposeResult:
        options = []
        for label, shortcut, action in self.items:
            if label == "-":
                options.append(None)
            else:
                options.append(Option(Text.assemble(f" {label:<22}", (f"{shortcut:>8} ", "dim")), id=action))
        yield OptionList(*options, id="context-menu")

    def on_mount(self) -> None:
        menu = self.query_one("#context-menu", OptionList)
        width = 34
        height = len(self.items) + 2
        x = min(self.position[0], max(self.size.width - width, 0))
        y = min(self.position[1], max(self.size.height - height, 0))
        menu.styles.offset = (x, y)
        menu.highlighted = 0
        menu.focus()

    @on(OptionList.OptionSelected, "#context-menu")
    def _chosen(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def on_click(self, event) -> None:
        if event.widget is self:  # a click outside the menu closes it
            self.dismiss(None)


class ShortcutsDialog(Dialog):
    SHORTCUTS = [
        ("General", [("F1 / ctrl+shift+p", "Command palette"), ("ctrl+p", "Quick open file"), ("ctrl+q", "Quit")]),
        ("Files", [("ctrl+n", "New file"), ("ctrl+o", "Open folder"), ("ctrl+s", "Save"), ("ctrl+w", "Close editor"),
                   ("ctrl+pageup/down", "Previous / next editor"), ("F2 / Del", "Rename / delete (explorer)"),
                   ("right click", "Explorer menu")]),
        ("Editing", [("ctrl+z / ctrl+y", "Undo / redo"), ("ctrl+c / x / v", "Copy / cut / paste"), ("ctrl+a", "Select all"),
                     ("ctrl+f / ctrl+h", "Find / replace"), ("ctrl+g", "Go to line"), ("ctrl+/", "Toggle comment")]),
        ("IntelliSense", [("ctrl+space", "Trigger suggestions"), ("tab / enter", "Accept suggestion"),
                          ("F12 / ctrl+click", "Go to definition"), ("alt+left", "Go back"),
                          ("ctrl+shift+o", "Go to symbol in file"), ("alt+h", "Show hover docs"),
                          ("ctrl+shift+m", "Problems")]),
        ("View", [("ctrl+b", "Toggle sidebar"), ("ctrl+j", "Toggle terminal"), ("ctrl+l", "Moon AI chat"),
                  ("ctrl+0 / ctrl+e", "Focus explorer"), ("ctrl+1", "Focus editor"), ("F11", "Zen mode")]),
        ("Run", [("F5", "Run active file"), ("ctrl+F5", "Run project")]),
    ]

    def __init__(self):
        super().__init__(classes="dialog-screen")

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog shortcuts"):
            yield Static("Keyboard Shortcuts", classes="dialog-title")
            for group, items in self.SHORTCUTS:
                yield Static(group, classes="shortcut-group")
                for keys, label in items:
                    yield Static(Text.assemble((f"{keys:<22}", "bold"), label))
            yield Static("Esc to close", classes="muted")
