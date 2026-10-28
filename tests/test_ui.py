"""End-to-end checks that drive the real app with Textual's pilot."""

import pytest
from textual.command import CommandPalette

from moon.core.config import Settings
from moon.ui.app import MoonCode
from moon.ui.screens.welcome import WelcomeScreen
from moon.ui.screens.workspace import WorkspaceScreen


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("MOON_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SHELL", "/bin/sh")
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "main.py").write_text("def greet(name):\n    return name\n")
    return folder


def make_app(target=None):
    return MoonCode(target, Settings(check_updates=False))


async def open_main(pilot, project):
    workspace = pilot.app.screen
    workspace.open_file(project / "main.py")
    await pilot.pause()
    editor = workspace.active_editor
    editor.focus()
    editor.move_cursor(editor.document.end)
    await pilot.pause()
    return workspace, editor


async def test_starts_on_welcome_screen(project):
    async with make_app().run_test() as pilot:
        assert isinstance(pilot.app.screen, WelcomeScreen)


async def test_f1_opens_command_palette(project):
    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("f1")
        await pilot.pause()
        assert isinstance(pilot.app.screen, CommandPalette)


async def test_enter_keeps_indentation_and_indents_after_colon(project):
    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        _, editor = await open_main(pilot, project)
        await pilot.press("i", "f", "space", "x", "colon", "enter", "y")
        assert editor.document.get_line(editor.cursor_location[0]) == "    y"


async def test_brackets_are_paired_and_typed_over(project):
    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        _, editor = await open_main(pilot, project)
        await pilot.press("f", "left_parenthesis", "1", "right_parenthesis")
        assert editor.document.get_line(editor.cursor_location[0]) == "f(1)"


async def test_autocomplete_inserts_suggestion_with_tab(project):
    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        workspace, editor = await open_main(pilot, project)
        await pilot.press("g", "r", "e")
        await pilot.pause()
        assert workspace.query_one("#completion").display
        await pilot.press("tab")
        assert editor.document.get_line(editor.cursor_location[0]) == "greet"


async def test_save_writes_file_and_clears_dirty_marker(project):
    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        workspace, editor = await open_main(pilot, project)
        await pilot.press("x")
        assert editor.dirty
        await pilot.press("ctrl+s")
        assert not editor.dirty
        assert (project / "main.py").read_text().endswith("x")


async def test_new_project_from_welcome_opens_workspace(project, tmp_path):
    settings = Settings(check_updates=False, projects_dir=str(tmp_path / "Projects"))
    async with MoonCode(None, settings).run_test(size=(120, 40)) as pilot:
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("d", "e", "m", "o", "enter")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(pilot.app.screen, WorkspaceScreen)
        assert (tmp_path / "Projects" / "demo" / "main.py").exists()


async def wait_for_dialog(pilot):
    for _ in range(50):
        await pilot.pause(0.05)
        if type(pilot.app.screen).__name__ == "ConfirmDialog":
            return
    raise AssertionError("update dialog never appeared")


async def _app_with_update(project, monkeypatch):
    from moon.core import updater
    from moon.core.updater import Release

    monkeypatch.setattr(updater, "newer_release", lambda: Release("v9.9.9", None))
    return MoonCode(project, Settings(check_updates=True))


async def test_update_dialog_later_remembers_the_version(project, monkeypatch):
    app = await _app_with_update(project, monkeypatch)
    async with app.run_test(size=(120, 40)) as pilot:
        await wait_for_dialog(pilot)
        await pilot.click("#no")
        await pilot.pause()
        assert app.settings.skipped_update == "v9.9.9"
        assert "v9.9.9" in str(app.screen.query_one("#status-update").render())


async def test_update_now_exits_with_update_request(project, monkeypatch):
    from moon.ui.app import UpdateRequest

    app = await _app_with_update(project, monkeypatch)
    async with app.run_test(size=(120, 40)) as pilot:
        await wait_for_dialog(pilot)
        await pilot.click("#yes")
        await pilot.pause()
    assert app.return_value == UpdateRequest(str(project.resolve()))


async def test_welcome_screen_offers_the_update(project, monkeypatch):
    from moon.core import updater
    from moon.core.updater import Release

    monkeypatch.setattr(updater, "newer_release", lambda: Release("v9.9.9", None))
    app = MoonCode(None, Settings(check_updates=True))
    async with app.run_test(size=(120, 40)) as pilot:
        await wait_for_dialog(pilot)
        await pilot.click("#no")
        await pilot.pause()
        assert app.screen.query_one("#welcome-update").display
        assert "v9.9.9" in str(app.screen.query_one("#welcome-update-label").render())


async def test_explorer_rename_and_delete_to_trash(project, tmp_path, monkeypatch):
    from moon.core import trash
    from moon.ui.dialogs import ConfirmDialog, PromptDialog

    monkeypatch.setattr(trash, "trash_dir", lambda: tmp_path / "Trash")
    (project / "oops.txt").write_text("by mistake")
    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        workspace = pilot.app.screen
        workspace.open_file(project / "oops.txt")
        await pilot.pause()

        workspace.rename_path(project / "oops.txt")
        await pilot.pause()
        assert isinstance(pilot.app.screen, PromptDialog)
        prompt = pilot.app.screen.query_one("Input")
        prompt.value = "notes.txt"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert (project / "notes.txt").read_text() == "by mistake"
        assert not (project / "oops.txt").exists()
        assert workspace.active_editor.path.name == "notes.txt"

        workspace.delete_path(project / "notes.txt")
        await pilot.pause()
        assert isinstance(pilot.app.screen, ConfirmDialog)
        await pilot.click("#yes")
        await pilot.pause()
        assert not (project / "notes.txt").exists()
        assert (tmp_path / "Trash" / "files" / "notes.txt").exists()
        assert all(e.path.name != "notes.txt" for e in workspace.editors.values())


async def test_explorer_keeps_focus_on_first_open(project):
    (project / "other.py").write_text("x = 1\n")
    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        workspace = pilot.app.screen
        from moon.ui.widgets.views import OpenFile
        workspace.tree.focus()
        workspace.post_message(OpenFile(project / "other.py", focus=False))
        await pilot.pause()
        assert workspace.active_editor.path.name == "other.py"
        assert not workspace.active_editor.has_focus
        workspace.post_message(OpenFile(project / "other.py", focus=False))
        await pilot.pause()
        assert workspace.active_editor.has_focus


async def test_right_click_opens_context_menu(project):
    from moon.ui.dialogs import ContextMenu

    async with make_app(project).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        tree = pilot.app.screen.query_one("#project-tree")
        await pilot.click(tree, offset=(6, 1), button=3)
        await pilot.pause()
        assert isinstance(pilot.app.screen, ContextMenu)
