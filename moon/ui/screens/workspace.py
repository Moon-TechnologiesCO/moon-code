"""The main editor window: sidebar, editor tabs, terminal panel and status bar."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import ContentSwitcher, Input, Static, TabbedContent, TabPane, TextArea

from moon import __version__
from moon.core import files, git
from moon.core.config import Settings, extensions_dir, settings_path
from moon.core.icons import icon_for
from moon.core.languages import language_for
from moon.core.themes import PALETTES, palette
from moon.extensions import Extension, code_runner, create_user_extension
from moon.ui.dialogs import (ConfirmDialog, NewProjectDialog, OpenFolderDialog, PickDialog, PromptDialog,
                             ShortcutsDialog)
from moon.ui.widgets.chrome import ActivityBar, StatusBar, TitleBar
from moon.ui.widgets.common import Clickable
from moon.ui.widgets.editor import CodeEditor, CompletionMenu, FindBar
from moon.ui.widgets.terminal import TerminalView
from moon.ui.widgets.views import (AIChatView, ExplorerView, ExtensionsView, ExtensionToggled, OpenFile,
                                   ScmView, SearchView)

Command = tuple[str, str, Callable[[], Any]]

# Actions whose keys also mean something in a shell; they go to the shell when the terminal has focus.
SHELL_KEYS = {"close_editor", "find", "replace", "go_to_line", "focus_explorer", "quick_open", "new_file",
              "open_folder", "toggle_comment", "save", "toggle_ai"}


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text)


class WorkspaceAPI:
    """What extensions get to call. Keeps extensions away from the screen's internals."""

    def __init__(self, workspace: "WorkspaceScreen"):
        self._workspace = workspace

    @property
    def project_root(self) -> Path:
        return self._workspace.root

    def add_command(self, title: str, help: str, callback: Callable[[], Any]) -> None:
        self._workspace.extension_commands.append((title, help, callback))

    def notify(self, message: str, severity: str = "information") -> None:
        self._workspace.app.notify(message, severity=severity)

    def run_in_terminal(self, command: str) -> None:
        self._workspace.run_in_terminal(command)

    def open_file(self, path: Path, line: int | None = None) -> None:
        self._workspace.open_file(Path(path), line)

    def active_file(self) -> Path | None:
        editor = self._workspace.active_editor
        return editor.path if editor else None

    def save_active(self) -> None:
        self._workspace.action_save()

    def reload_file(self, path: Path) -> None:
        self._workspace.reload_file(Path(path))

    def open_ai_chat(self) -> None:
        self._workspace.action_toggle_ai(force=True)

    def explain_active_file(self) -> None:
        self._workspace.explain_active_file()


class WorkspaceScreen(Screen):
    BINDINGS = [
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+w", "close_editor", "Close", priority=True),
        Binding("ctrl+n", "new_file", "New File", priority=True),
        Binding("ctrl+o", "open_folder", "Open Folder", priority=True),
        Binding("ctrl+p", "quick_open", "Quick Open", priority=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", priority=True),
        Binding("ctrl+j", "toggle_terminal", "Terminal", priority=True),
        Binding("ctrl+l", "toggle_ai", "Moon AI", priority=True),
        Binding("ctrl+e", "focus_explorer", "Explorer", priority=True),
        Binding("ctrl+shift+f", "show_view('search')", "Search", priority=True),
        Binding("ctrl+f", "find", "Find", priority=True),
        Binding("ctrl+h", "replace", "Replace", priority=True),
        Binding("ctrl+g", "go_to_line", "Go to Line", priority=True),
        Binding("ctrl+slash,ctrl+underscore", "toggle_comment", "Comment", priority=True),
        Binding("ctrl+pageup", "previous_editor", "Previous", priority=True),
        Binding("ctrl+pagedown", "next_editor", "Next", priority=True),
        Binding("f5", "run_active", "Run", priority=True),
        Binding("ctrl+f5", "run_project", "Run Project", priority=True),
        Binding("f11", "toggle_zen", "Zen", priority=True),
        Binding("escape", "escape", "Close", show=False),
    ]

    def __init__(self, root: Path, settings: Settings, extensions: list[Extension]):
        super().__init__()
        self.root = root
        self.settings = settings
        self.extensions = extensions
        self.editors: dict[str, CodeEditor] = {}  # pane id -> editor
        self.extension_commands: list[Command] = []
        self.api = WorkspaceAPI(self)

    # --- Layout -------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield TitleBar(self._window_title())
        with Horizontal(id="body"):
            yield ActivityBar(id="activity-bar")
            with ContentSwitcher(initial="explorer", id="sidebar"):
                yield ExplorerView(self.root, self.settings.nerd_font, id="explorer")
                yield SearchView(self.root, id="search")
                yield ScmView(self.root, id="scm")
                yield ExtensionsView(self.extensions, self.settings.disabled_extensions, extensions_dir(), id="extensions")
            with Vertical(id="main"):
                yield FindBar(id="find-bar")
                with TabbedContent(id="editors"):
                    with TabPane("Welcome", id="welcome-pane"):
                        yield Static(self._watermark(), id="watermark")
                with Vertical(id="panel"):
                    with Horizontal(id="panel-header"):
                        yield Static("TERMINAL", classes="panel-tab active")
                        yield Static(classes="panel-spacer")
                        yield Clickable(" ⟳ ", "screen.restart_terminal", "New terminal", classes="panel-action")
                        yield Clickable(" ✕ ", "screen.toggle_terminal", "Hide panel (ctrl+j)", classes="panel-action")
                    yield TerminalView(self.root, palette(self.settings.theme), id="terminal")
            yield AIChatView(self.settings.ai_model, self.settings.ollama_url, id="ai")
        yield StatusBar(id="status-bar")
        yield CompletionMenu(id="completion")

    def _window_title(self, file: Path | None = None) -> str:
        name = self.root.name or str(self.root)
        return f"{file.name} — {name} — Moon Code" if file else f"{name} — Moon Code"

    def _watermark(self) -> str:
        rows = [("Command Palette", "F1"), ("Quick Open File", "ctrl+p"), ("New File", "ctrl+n"),
                ("Open Folder", "ctrl+o"), ("Toggle Terminal", "ctrl+j"), ("Run File", "F5"),
                ("Moon AI", "ctrl+l"), ("All Shortcuts", "F1 → Keyboard Shortcuts")]
        lines = "\n".join(f"[dim]{label:<22}[/dim][b]{keys}[/b]" for label, keys in rows)
        return f"\n\n[b]🌙  Moon Code[/b]  [dim]{__version__}[/dim]\n\n{lines}"

    def on_mount(self) -> None:
        self.query_one("#find-bar").display = False
        self.query_one("#completion").display = False
        self.query_one("#ai").display = False
        self.query_one(ActivityBar).set_active("explorer")
        self.settings.add_recent(self.root)
        self.settings.save()
        self._activate_extensions()
        self._apply_extension_features()
        self.status.show("theme", f"🌙 {palette(self.settings.theme).label}")
        self.status.show("indent", f"Spaces: {self.settings.tab_size}")
        self.status.show("update", f"⬆ Update to {self.app.update_tag}" if self.app.update_tag else "")
        self.query_one("#project-tree").focus()
        self._refresh_branch()

    @property
    def status(self) -> StatusBar:
        return self.query_one(StatusBar)

    @property
    def terminal(self) -> TerminalView:
        return self.query_one(TerminalView)

    @property
    def tabs(self) -> TabbedContent:
        return self.query_one("#editors", TabbedContent)

    @property
    def active_editor(self) -> CodeEditor | None:
        return self.editors.get(self.tabs.active)

    # --- Extensions ---------------------------------------------------------

    def extension_enabled(self, extension_id: str) -> bool:
        return extension_id not in self.settings.disabled_extensions

    def _activate_extensions(self) -> None:
        self.extension_commands.clear()
        for extension in self.extensions:
            if extension.activate and self.extension_enabled(extension.id):
                try:
                    extension.activate(self.api)
                except Exception as error:  # A broken extension must never stop the editor.
                    self.app.notify(f"{extension.name} failed to start: {error}", severity="error")

    def _apply_extension_features(self) -> None:
        self.query_one("#run-button").display = self.extension_enabled("code-runner")
        self.query_one("#activity-ai").display = self.extension_enabled("moon-ai")
        self.query_one("#activity-scm").display = self.extension_enabled("git")
        if not self.extension_enabled("moon-ai"):
            self.query_one("#ai").display = False
        for editor in self.editors.values():
            editor.autocomplete = self.extension_enabled("autocomplete")
        self._refresh_branch()

    @on(ExtensionToggled)
    def _extension_toggled(self, event: ExtensionToggled) -> None:
        disabled = set(self.settings.disabled_extensions)
        disabled.discard(event.extension_id) if event.enabled else disabled.add(event.extension_id)
        self.settings.disabled_extensions = sorted(disabled)
        self.settings.save()
        self._activate_extensions()
        self._apply_extension_features()
        self.app.notify(f"Extension {'enabled' if event.enabled else 'disabled'}.")

    def action_create_extension(self) -> None:
        def created(name: str | None) -> None:
            if not name:
                return
            try:
                path = create_user_extension(name)
            except (FileExistsError, OSError) as error:
                self.app.notify(str(error), severity="error")
                return
            self.open_file(path)
            self.app.notify("Extension created. Edit it, save, and reopen the folder to load it.")

        self.app.push_screen(PromptDialog("Create Extension", "My Extension", hint="A Python file with an activate(api) function."), created)

    # --- Commands (palette) -----------------------------------------------------

    def commands(self) -> list[Command]:
        builtin: list[Command] = [
            ("File: New File", "Create a file in this project (ctrl+n)", self.action_new_file),
            ("File: New Folder", "Create a folder in this project", self.action_new_folder),
            ("File: New Project", "Create a project from a template", self.action_new_project),
            ("File: Open Folder", "Open another folder (ctrl+o)", self.action_open_folder),
            ("File: Open Recent", "Open a recent project", self.action_open_recent),
            ("File: Quick Open", "Find a file by name (ctrl+p)", self.action_quick_open),
            ("File: Save", "Save the active file (ctrl+s)", self.action_save),
            ("File: Save All", "Save every open file", self.action_save_all),
            ("File: Close Editor", "Close the active tab (ctrl+w)", self.action_close_editor),
            ("File: Close Folder", "Back to the welcome screen", self.action_close_folder),
            ("Edit: Find", "Find in the active file (ctrl+f)", self.action_find),
            ("Edit: Replace", "Find and replace (ctrl+h)", self.action_replace),
            ("Edit: Go to Line", "Jump to a line number (ctrl+g)", self.action_go_to_line),
            ("Edit: Toggle Line Comment", "Comment or uncomment lines (ctrl+/)", self.action_toggle_comment),
            ("View: Toggle Sidebar", "Show or hide the sidebar (ctrl+b)", self.action_toggle_sidebar),
            ("View: Toggle Terminal", "Show or hide the terminal (ctrl+j)", self.action_toggle_terminal),
            ("View: Explorer", "Show the file explorer (ctrl+e)", lambda: self.action_show_view("explorer")),
            ("View: Search", "Search in all files", lambda: self.action_show_view("search")),
            ("View: Source Control", "Show changed files", lambda: self.action_show_view("scm")),
            ("View: Extensions", "Manage extensions", lambda: self.action_show_view("extensions")),
            ("View: Zen Mode", "Only the editor (F11)", self.action_toggle_zen),
            ("Terminal: New Terminal", "Restart the integrated terminal", self.action_restart_terminal),
            ("Preferences: Color Theme", "Choose a Moon theme", self.action_pick_theme),
            ("Preferences: Open Settings (JSON)", "Edit settings.json", self.action_open_settings),
            ("Preferences: Toggle Word Wrap", "Wrap long lines", self.action_toggle_word_wrap),
            ("Preferences: Toggle Nerd Font Icons", "Use Nerd Font glyphs instead of emoji", self.action_toggle_nerd),
            ("Help: Keyboard Shortcuts", "Every shortcut in one place", self.action_show_shortcuts),
            ("Help: Check for Updates", "Look for a newer Moon Code", self.app.action_check_updates),
            ("Help: About Moon Code", "Version and links", self.action_about),
        ]
        return builtin + self.extension_commands

    # --- Files & editors ----------------------------------------------------

    def _pane_id(self, path: Path) -> str:
        return "pane-" + _slug(str(path))

    def open_file(self, path: Path, line: int | None = None) -> None:
        path = path.resolve()
        pane_id = self._pane_id(path)
        if pane_id in self.editors:
            self.tabs.active = pane_id
            editor = self.editors[pane_id]
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                self.app.notify(f"{path.name} is a binary file and can't be edited.", severity="warning")
                return
            except OSError as error:
                self.app.notify(f"Couldn't open {path.name}: {error.strerror}", severity="error")
                return
            editor = CodeEditor(
                path, text, theme=self.settings.theme, tab_size=self.settings.tab_size,
                line_numbers=self.settings.show_line_numbers, word_wrap=self.settings.word_wrap,
                autocomplete=self.extension_enabled("autocomplete"), id=f"editor-{pane_id}",
            )
            self.editors[pane_id] = editor
            self.tabs.add_pane(TabPane(self._tab_label(editor), editor, id=pane_id))
            self.tabs.active = pane_id
        editor.focus()
        if line:
            self.call_after_refresh(editor.go_to_line, line)
        self._update_for_editor(editor)

    def _tab_label(self, editor: CodeEditor) -> str:
        return f"{icon_for(editor.path, self.settings.nerd_font)} {editor.path.name}{' ●' if editor.dirty else ''}"

    @on(CodeEditor.DirtyChanged)
    def _dirty_changed(self, event: CodeEditor.DirtyChanged) -> None:
        for pane_id, editor in self.editors.items():
            if editor is event.editor:
                self.tabs.get_tab(pane_id).label = self._tab_label(editor)

    @on(OpenFile)
    def _open_requested(self, event: OpenFile) -> None:
        self.open_file(event.path, event.line)

    @on(TabbedContent.TabActivated, "#editors")
    def _tab_activated(self) -> None:
        self._update_for_editor(self.active_editor)

    @on(TextArea.SelectionChanged)
    def _cursor_moved(self, event: TextArea.SelectionChanged) -> None:
        if isinstance(event.text_area, CodeEditor):
            row, column = event.selection.end
            self.status.show("cursor", f"Ln {row + 1}, Col {column + 1}")

    def _update_for_editor(self, editor: CodeEditor | None) -> None:
        if editor is None:
            self.query_one(TitleBar).set_title(self._window_title())
            self.status.show("cursor", "")
            self.status.show("language", "")
            return
        self.query_one(TitleBar).set_title(self._window_title(editor.path))
        row, column = editor.cursor_location
        self.status.show("cursor", f"Ln {row + 1}, Col {column + 1}")
        self.status.show("language", language_for(editor.path).name)

    def action_save(self) -> None:
        editor = self.active_editor
        if editor is None:
            return
        try:
            editor.save()
        except OSError as error:
            self.app.notify(f"Couldn't save {editor.path.name}: {error.strerror}", severity="error")
            return
        if editor.path == settings_path().resolve():
            self.app.reload_settings()

    def action_save_all(self) -> None:
        for editor in self.editors.values():
            if editor.dirty:
                editor.save()
        self.app.notify("All files saved.")

    def reload_file(self, path: Path) -> None:
        editor = self.editors.get(self._pane_id(path.resolve()))
        if editor is not None:
            editor.reload()

    def dirty_editors(self) -> list[CodeEditor]:
        return [editor for editor in self.editors.values() if editor.dirty]

    def action_close_editor(self) -> None:
        pane_id = self.tabs.active
        editor = self.editors.get(pane_id)
        if editor is None:
            return

        def answered(save: bool | None) -> None:
            if save is None:
                return
            if save:
                editor.save()
            self._remove_pane(pane_id)

        if editor.dirty:
            self.app.push_screen(ConfirmDialog("Unsaved changes", f"Save changes to {editor.path.name}?", "Save", "Don't Save"), answered)
        else:
            self._remove_pane(pane_id)

    def _remove_pane(self, pane_id: str) -> None:
        self.editors.pop(pane_id, None)
        self.tabs.remove_pane(pane_id)
        self.call_after_refresh(self._after_close)

    def _after_close(self) -> None:
        editor = self.active_editor
        self._update_for_editor(editor)
        if editor:
            editor.focus()

    def action_previous_editor(self) -> None:
        self._cycle_editor(-1)

    def action_next_editor(self) -> None:
        self._cycle_editor(1)

    def _cycle_editor(self, step: int) -> None:
        panes = [pane.id for pane in self.tabs.query(TabPane)]
        if len(panes) > 1 and self.tabs.active in panes:
            self.tabs.active = panes[(panes.index(self.tabs.active) + step) % len(panes)]
            if self.active_editor:
                self.active_editor.focus()

    def action_new_file(self) -> None:
        def create(name: str | None) -> None:
            if not name:
                return
            path = (self.root / name).resolve()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=True)
            except OSError as error:
                self.app.notify(f"Couldn't create {name}: {error.strerror}", severity="error")
                return
            self.query_one(ExplorerView).reload()
            self.open_file(path)

        self.app.push_screen(PromptDialog("New File", "src/main.py", hint=f"Relative to {self.root}"), create)

    def action_new_folder(self) -> None:
        def create(name: str | None) -> None:
            if name:
                (self.root / name).mkdir(parents=True, exist_ok=True)
                self.query_one(ExplorerView).reload()

        self.app.push_screen(PromptDialog("New Folder", "assets", hint=f"Relative to {self.root}"), create)

    def action_refresh_explorer(self) -> None:
        self.query_one(ExplorerView).reload()

    def action_quick_open(self) -> None:
        items = [(str(path), path) for path in files.walk_files(self.root)]

        def chosen(path: Path | None) -> None:
            if path is not None:
                self.open_file(self.root / path)

        self.app.push_screen(PickDialog("Quick Open", items, "Search files by name", nerd=self.settings.nerd_font, file_icons=True), chosen)

    def action_open_folder(self) -> None:
        self.app.push_screen(OpenFolderDialog(self.root.parent), self._open_folder_result)

    def _open_folder_result(self, folder: Path | None) -> None:
        if folder is not None:
            self.app.open_workspace(folder)

    def action_open_recent(self) -> None:
        items = [(p, Path(p)) for p in self.settings.recent_projects if Path(p).is_dir()]
        self.app.push_screen(PickDialog("Open Recent", items, "Recent folders"), self._open_folder_result)

    def action_new_project(self) -> None:
        def created(folder: Path | None) -> None:
            if folder is not None:
                self.app.open_workspace(folder)

        self.app.push_screen(NewProjectDialog(Path(self.settings.projects_dir)), created)

    def action_close_folder(self) -> None:
        self.app.close_workspace()

    def action_open_settings(self) -> None:
        path = settings_path()
        if not path.exists():
            self.settings.save(path)
        self.open_file(path)

    # --- Find / replace / go to line ------------------------------------------

    @property
    def find_bar(self) -> FindBar:
        return self.query_one(FindBar)

    def action_find(self) -> None:
        self._open_find(replace=False)

    def action_replace(self) -> None:
        self._open_find(replace=True)

    def _open_find(self, replace: bool) -> None:
        editor = self.active_editor
        if editor is None:
            return
        selected = editor.selected_text if "\n" not in editor.selected_text else ""
        self.find_bar.open(replace, selected)
        self.find_bar.show_count(editor.count_matches(self.find_bar.query_text))

    @on(Input.Changed, "#find-input")
    def _find_changed(self, event: Input.Changed) -> None:
        editor = self.active_editor
        if editor is not None:
            self.find_bar.show_count(editor.count_matches(event.value))

    @on(Input.Submitted, "#find-input")
    def _find_submitted(self) -> None:
        self.action_find_next()

    @on(Input.Submitted, "#replace-input")
    def _replace_submitted(self) -> None:
        self.action_replace_one()

    def action_find_next(self) -> None:
        if self.active_editor and not self.active_editor.find_next(self.find_bar.query_text):
            self.app.notify("No results.", severity="warning")

    def action_find_previous(self) -> None:
        if self.active_editor:
            self.active_editor.find_next(self.find_bar.query_text, backwards=True)

    def action_replace_one(self) -> None:
        editor = self.active_editor
        if editor:
            editor.replace_current(self.find_bar.query_text, self.find_bar.replacement)
            self.find_bar.show_count(editor.count_matches(self.find_bar.query_text))

    def action_replace_all(self) -> None:
        editor = self.active_editor
        if editor:
            count = editor.replace_all(self.find_bar.query_text, self.find_bar.replacement)
            self.find_bar.show_count(editor.count_matches(self.find_bar.query_text))
            self.app.notify(f"Replaced {count} occurrence{'s' if count != 1 else ''}.")

    def action_close_find(self) -> None:
        self.find_bar.display = False
        if self.active_editor:
            self.active_editor.focus()

    def action_escape(self) -> None:
        if self.find_bar.display:
            self.action_close_find()

    def action_go_to_line(self) -> None:
        editor = self.active_editor
        if editor is None:
            return

        def go(value: str | None) -> None:
            if value and value.isdigit():
                editor.go_to_line(int(value))
                editor.focus()

        self.app.push_screen(PromptDialog("Go to Line", f"1 – {editor.document.line_count}"), go)

    def action_toggle_comment(self) -> None:
        if self.active_editor:
            self.active_editor.toggle_comment()

    # --- Views --------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Let the shell have its ctrl keys (ctrl+w, ctrl+e, ctrl+l…) while the terminal is focused.
        if action in SHELL_KEYS and isinstance(self.focused, TerminalView):
            return False
        return True

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display
        self.query_one(ActivityBar).set_active(sidebar.current if sidebar.display else None)

    def action_show_view(self, view: str) -> None:
        sidebar = self.query_one("#sidebar", ContentSwitcher)
        if sidebar.display and sidebar.current == view:
            sidebar.display = False
            self.query_one(ActivityBar).set_active(None)
            return
        sidebar.display = True
        sidebar.current = view
        self.query_one(ActivityBar).set_active(view)
        if view == "search":
            self.query_one(SearchView).focus_input()
        elif view == "scm":
            self.query_one(ScmView).refresh_changes()
        elif view == "explorer":
            self.query_one("#project-tree").focus()

    def action_focus_explorer(self) -> None:
        sidebar = self.query_one("#sidebar", ContentSwitcher)
        if not (sidebar.display and sidebar.current == "explorer"):
            self.action_show_view("explorer")
        self.query_one("#project-tree").focus()

    def action_refresh_scm(self) -> None:
        self.query_one(ScmView).refresh_changes()

    def action_toggle_terminal(self) -> None:
        panel = self.query_one("#panel")
        panel.display = not panel.display
        if panel.display:
            self.terminal.focus()
        elif self.active_editor:
            self.active_editor.focus()

    def action_restart_terminal(self) -> None:
        self.query_one("#panel").display = True
        self.terminal.restart()
        self.terminal.focus()

    def run_in_terminal(self, command: str) -> None:
        self.query_one("#panel").display = True
        self.terminal.run(command)
        self.terminal.focus()

    def action_toggle_zen(self) -> None:
        self.toggle_class("zen")

    def action_toggle_ai(self, force: bool = False) -> None:
        if not self.extension_enabled("moon-ai"):
            self.app.notify("Enable the Moon AI extension first.", severity="warning")
            return
        ai = self.query_one(AIChatView)
        ai.display = True if force else not ai.display
        if ai.display:
            self.query_one("#ai-input", Input).focus()
        elif self.active_editor:
            self.active_editor.focus()

    def action_clear_ai(self) -> None:
        self.query_one(AIChatView).clear()

    @on(Input.Submitted, "#ai-input")
    def _ask_ai(self, event: Input.Submitted) -> None:
        question = event.value.strip()
        event.input.value = ""
        if not question:
            return
        ai = self.query_one(AIChatView)
        editor = self.active_editor
        context = None
        if ai.include_file and editor is not None:
            context = f"Active file `{editor.path.name}`:\n```\n{editor.text[:12000]}\n```"
        ai.ask(question, context)

    def explain_active_file(self) -> None:
        editor = self.active_editor
        if editor is None:
            self.app.notify("Open a file first.", severity="warning")
            return
        self.action_toggle_ai(force=True)
        self.query_one(AIChatView).ask(
            f"Explain what {editor.path.name} does, briefly.",
            f"```\n{editor.text[:12000]}\n```",
        )

    # --- Run ----------------------------------------------------------------

    def action_run_active(self) -> None:
        if not self.extension_enabled("code-runner"):
            self.app.notify("Enable the Code Runner extension to run files.", severity="warning")
            return
        code_runner.run_active(self.api)

    def action_run_project(self) -> None:
        if self.extension_enabled("code-runner"):
            code_runner.run_project(self.api)

    # --- Preferences ----------------------------------------------------------

    def action_pick_theme(self) -> None:
        items = [(p.label, p.name) for p in PALETTES]
        self.app.push_screen(PickDialog("Color Theme", items, "Select a theme", fuzzy=False), self._theme_chosen)

    def _theme_chosen(self, name: str | None) -> None:
        if name:
            self.app.set_moon_theme(name)

    def apply_theme(self, name: str) -> None:
        for editor in self.editors.values():
            editor.theme = name
        self.terminal.palette = palette(name)
        self.terminal.refresh()
        self.status.show("theme", f"🌙 {palette(name).label}")

    def apply_settings(self, settings: Settings) -> None:
        self.settings = settings
        for editor in self.editors.values():
            editor.indent_width = settings.tab_size
            editor.show_line_numbers = settings.show_line_numbers
            editor.soft_wrap = settings.word_wrap
        self.status.show("indent", f"Spaces: {settings.tab_size}")
        self._apply_extension_features()

    def action_toggle_word_wrap(self) -> None:
        self.settings.word_wrap = not self.settings.word_wrap
        self.settings.save()
        self.apply_settings(self.settings)

    def action_toggle_nerd(self) -> None:
        self.settings.nerd_font = not self.settings.nerd_font
        self.settings.save()
        self.app.notify("Icon style changed. Reopen the folder to refresh the explorer.")

    def action_show_shortcuts(self) -> None:
        self.app.push_screen(ShortcutsDialog())

    def action_about(self) -> None:
        self.app.notify(f"Moon Code {__version__} · Moon Technologies · MIT License", title="About")

    def show_update(self, tag: str) -> None:
        if self.is_mounted:  # on_mount picks up app.update_tag otherwise
            self.status.show("update", f"⬆ Update to {tag}")

    # --- Git ----------------------------------------------------------------

    @work(thread=True, exclusive=True, group="git")
    def _refresh_branch(self) -> None:
        name = git.branch(self.root) if self.extension_enabled("git") else None
        self.app.call_from_thread(self.status.show, "branch", f"⎇ {name}" if name else "")
