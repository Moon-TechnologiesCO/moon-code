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
