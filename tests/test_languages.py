from pathlib import Path

from moon.core.languages import language_for, project_command, required_tool, run_command


def test_language_for_common_extensions():
    assert language_for(Path("app.py")).name == "Python"
    assert language_for(Path("main.rs")).syntax == "rust"
    assert language_for(Path("Makefile")).name == "Makefile"
    assert language_for(Path("notes.unknown")).name == "Plain Text"


def test_run_command_quotes_paths_with_spaces():
    command = run_command(Path("/tmp/my project/hello.py"))
    assert command == "python3 '/tmp/my project/hello.py'"


def test_run_command_none_for_data_files():
    assert run_command(Path("data.json")) is None


def test_compiled_language_builds_then_runs():
    command = run_command(Path("/src/main.c"))
    assert command.startswith("gcc /src/main.c -o ") and "&&" in command


def test_project_command_detects_markers(tmp_path):
    assert project_command(tmp_path) is None
    (tmp_path / "Cargo.toml").write_text("")
    assert project_command(tmp_path) == "cargo run"
    (tmp_path / "package.json").write_text("{}")
    assert project_command(tmp_path) == "npm start"


def test_project_command_dotnet(tmp_path):
    (tmp_path / "app.csproj").write_text("")
    assert project_command(tmp_path) == "dotnet run"


def test_required_tool_reports_missing_program():
    assert required_tool("definitely-not-a-real-tool-xyz file") == "definitely-not-a-real-tool-xyz"
    assert required_tool("cd /tmp && sh -c true") is None
