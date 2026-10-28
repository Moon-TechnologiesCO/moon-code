"""The Moon Code application: owns settings, themes and which screen is showing."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from textual import work
from textual.app import App, SystemCommand
from textual.binding import Binding
from textual.screen import Screen

from moon import __version__
from moon.core import clipboard, updater
from moon.core.config import Settings, settings_path
from moon.core.projects import TEMPLATES_BY_ID
from moon.core.themes import PALETTES, app_theme, palette
from moon.extensions import builtin_extensions, user_extensions
from moon.ui.dialogs import ConfirmDialog
from moon.ui.screens.welcome import WelcomeScreen
from moon.ui.screens.workspace import WorkspaceScreen


class MoonCode(App):
    TITLE = "Moon Code"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+q", "request_quit", "Quit", priority=True),
        Binding("f1,ctrl+shift+p", "command_palette", "Commands", show=False, priority=True),
    ]

    def __init__(self, target: Path | None = None, settings: Settings | None = None):
        super().__init__()
        self.settings = settings or Settings.load()
        self.target = target
        self.update_tag: str | None = None
        for moon_palette in PALETTES:
            self.register_theme(app_theme(moon_palette))
        self.theme = palette(self.settings.theme).name

    def on_mount(self) -> None:
        if self.target is None:
            self.push_screen(WelcomeScreen(self.settings))
        elif self.target.is_file():
            self.open_workspace(self.target.parent, self.target)
        else:
            self.open_workspace(self.target)
        if self.settings.check_updates:
            self._check_updates(quiet=True)

    def copy_to_clipboard(self, text: str) -> None:
        super().copy_to_clipboard(text)  # OSC 52, for terminals that support it
        clipboard.copy(text)  # GNOME Terminal and others need the desktop clipboard tools

    # --- Screens ------------------------------------------------------------

    def _extensions(self):
        user, errors = user_extensions()
        for error in errors:
            self.notify(f"Extension error: {error}", severity="error")
        return builtin_extensions() + user

    def open_workspace(self, folder: Path, file: Path | None = None) -> None:
        workspace = WorkspaceScreen(folder.resolve(), self.settings, self._extensions())
        if isinstance(self.screen, (WelcomeScreen, WorkspaceScreen)):
            self.switch_screen(workspace)
        else:
            self.push_screen(workspace)
        if file is None:
            file = self._main_file(folder)
        if file is not None:
            self.call_after_refresh(workspace.open_file, file)

    def _main_file(self, folder: Path) -> Path | None:
        """For a freshly created project, the file to show first: its code, else its README."""
        if len(list(folder.iterdir())) > 6:
            return None
        mains = [t.main for t in TEMPLATES_BY_ID.values() if t.main and t.main != "README.md"] + ["README.md"]
        return next((folder / main for main in mains if (folder / main).is_file()), None)

    def close_workspace(self) -> None:
        self.switch_screen(WelcomeScreen(self.settings, self.update_tag))

    def open_settings(self) -> None:
        path = settings_path()
        if not path.exists():
            self.settings.save(path)
        self.open_workspace(path.parent, path)

    # --- Commands -----------------------------------------------------------

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        if isinstance(screen, WorkspaceScreen):
            for title, help_text, callback in screen.commands():
                yield SystemCommand(title, help_text, callback)
        else:
            yield SystemCommand("File: Open Folder", "Open a folder", lambda: screen.run_action("open_folder"))
            yield SystemCommand("File: New Project", "Create a project", lambda: screen.run_action("new_project"))
            yield SystemCommand("Preferences: Open Settings (JSON)", "Edit settings.json", self.open_settings)
            yield SystemCommand("Help: Check for Updates", "Look for a newer Moon Code", self.action_check_updates)
        if self.update_tag:
            yield SystemCommand(f"Help: Update to {self.update_tag}", "Install the new version and restart", self.action_install_update)
        yield SystemCommand("Quit", "Close Moon Code (ctrl+q)", self.action_request_quit)

    # --- Themes & settings ----------------------------------------------------

    def set_moon_theme(self, name: str) -> None:
        self.theme = name
        self.settings.theme = name
        self.settings.save()
        if isinstance(self.screen, WorkspaceScreen):
            self.screen.apply_theme(name)

    def reload_settings(self) -> None:
        self.settings = Settings.load()
        self.theme = palette(self.settings.theme).name
        if isinstance(self.screen, WorkspaceScreen):
            self.screen.apply_theme(self.theme)
            self.screen.apply_settings(self.settings)
        self.notify("Settings applied.")

    # --- Updates ------------------------------------------------------------

    def action_check_updates(self) -> None:
        self._check_updates(quiet=False)

    @work(thread=True, exclusive=True, group="updates")
    def _check_updates(self, quiet: bool) -> None:
        release = updater.newer_release()
        self.call_from_thread(self._update_checked, release.tag if release else None, quiet)

    def _update_checked(self, tag: str | None, quiet: bool) -> None:
        self.update_tag = tag
        if tag is None:
            if not quiet:
                self.notify("You're on the latest version.")
            return
        for screen in self.screen_stack:
            if hasattr(screen, "show_update"):
                screen.show_update(tag)
        # Ask once per version on startup; asking from the palette always shows the dialog.
        if quiet and tag == self.settings.skipped_update:
            return

        def answered(update: bool | None) -> None:
            if update:
                self.action_install_update()
            elif update is False:
                self.settings.skipped_update = tag
                self.settings.save()

        self.push_screen(ConfirmDialog(
            "Update available",
            f"Moon Code {tag} is ready to install (you have {__version__}).\n"
            "Moon Code will close, update and open again right where you are.",
            "Update now", "Later",
        ), answered)

    def action_install_update(self) -> None:
        """Close the app; the command line installs the update and starts Moon Code again."""
        if self.update_tag is None:
            self.action_check_updates()
            return
        screen = self.screen
        reopen = str(screen.root) if isinstance(screen, WorkspaceScreen) else None
        self._close_saving(lambda: self.exit(UpdateRequest(reopen)), "Save changes before updating?")

    # --- Quit ---------------------------------------------------------------

    def action_request_quit(self) -> None:
        self._close_saving(self.exit, "Save changes before quitting?")

    def _close_saving(self, close, question: str) -> None:
        """Run `close` once unsaved files are saved or discarded (asks first if there are any)."""
        screen = self.screen
        dirty = screen.dirty_editors() if isinstance(screen, WorkspaceScreen) else []
        if not dirty:
            close()
            return

        def answered(save: bool | None) -> None:
            if save is None:
                return
            if save:
                for editor in dirty:
                    editor.save()
            close()

        names = ", ".join(editor.path.name for editor in dirty[:3]) + ("…" if len(dirty) > 3 else "")
        self.push_screen(ConfirmDialog("Unsaved changes", f"{question}\n{names}", "Save All", "Don't Save"), answered)


@dataclass(frozen=True)
class UpdateRequest:
    """Returned by the app when the user chose "Update now"; `reopen` is the folder to open after."""

    reopen: str | None
