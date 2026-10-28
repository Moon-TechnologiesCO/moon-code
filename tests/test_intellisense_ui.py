"""IntelliSense inside the real editor (Python, served by Jedi)."""

import asyncio

import pytest

from moon.core.config import Settings
from moon.ui.app import MoonCode

CODE = '''def fibonacci(count: int) -> list[int]:
    """Return the first count Fibonacci numbers."""
    numbers = [0, 1]
    return numbers


'''


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("MOON_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SHELL", "/bin/sh")
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "app.py").write_text(CODE)
    return folder


async def open_app(pilot, project):
    workspace = pilot.app.screen
    workspace.open_file(project / "app.py")
    await pilot.pause()
    editor = workspace.active_editor
    editor.focus()
    editor.move_cursor((5, 0))
    await pilot.pause()
    return workspace, editor


async def wait_until(pilot, condition, seconds=25.0):
    for _ in range(int(seconds / 0.1)):
        await pilot.pause()
        if condition():
            return True
        await asyncio.sleep(0.1)
    return False


async def test_member_suggestions_after_dot(project):
    async with MoonCode(project, Settings(check_updates=False)).run_test(size=(120, 40)) as pilot:
        workspace, editor = await open_app(pilot, project)
        await pilot.press("x", "space", "equals_sign", "space", "left_square_bracket", "1", "right_square_bracket", "enter")
        await pilot.press("x", "full_stop", "a", "p")
        menu = workspace.query_one("#completion")
        assert await wait_until(pilot, lambda: menu.display and any(i.label == "append" for i in editor._shown))
        await pilot.press("tab")
        assert editor.document.get_line(6) == "x.append"


async def test_signature_help_while_calling(project):
    async with MoonCode(project, Settings(check_updates=False)).run_test(size=(120, 40)) as pilot:
        workspace, editor = await open_app(pilot, project)
        await pilot.press(*"fibonacci", "left_parenthesis")
        hint = workspace.query_one("#signature")
        assert await wait_until(pilot, lambda: hint.display)
        assert "count: int" in str(hint.render())


async def test_syntax_errors_show_in_problems(project):
    async with MoonCode(project, Settings(check_updates=False)).run_test(size=(120, 40)) as pilot:
        workspace, editor = await open_app(pilot, project)
        editor.insert("def broken(:\n")
        assert await wait_until(pilot, lambda: bool(workspace.problems))
        assert "1" in str(workspace.query_one("#status-problems").render())
        assert any(name.startswith("moon.") for line in editor._highlights.values() for *_, name in line)


async def test_f12_goes_to_definition_and_alt_left_returns(project):
    async with MoonCode(project, Settings(check_updates=False)).run_test(size=(120, 40)) as pilot:
        workspace, editor = await open_app(pilot, project)
        editor.insert("fibonacci(3)")
        editor.move_cursor((5, 2))
        await pilot.press("f12")
        assert await wait_until(pilot, lambda: editor.cursor_location[0] == 0)
        await pilot.press("alt+left")
        assert await wait_until(pilot, lambda: editor.cursor_location[0] == 5)


async def test_go_to_symbol_lists_functions(project):
    from moon.ui.dialogs import PickDialog

    async with MoonCode(project, Settings(check_updates=False)).run_test(size=(120, 40)) as pilot:
        workspace, editor = await open_app(pilot, project)
        workspace.action_go_to_symbol()
        assert await wait_until(pilot, lambda: isinstance(pilot.app.screen, PickDialog))
        assert any("fibonacci" in label for label, _ in pilot.app.screen.items)
