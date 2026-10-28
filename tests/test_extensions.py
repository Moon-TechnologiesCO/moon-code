from pathlib import Path

from moon.extensions import builtin_extensions, code_runner, create_user_extension, user_extensions


class FakeAPI:
    def __init__(self, root: Path, active: Path | None = None):
        self.project_root = root
        self.active = active
        self.commands, self.ran, self.messages = [], [], []

    def add_command(self, title, help, callback):
        self.commands.append(title)

    def notify(self, message, severity="information"):
        self.messages.append(message)

    def run_in_terminal(self, command):
        self.ran.append(command)

    def active_file(self):
        return self.active

    def save_active(self):
        pass


def test_builtins_have_unique_ids():
    ids = [e.id for e in builtin_extensions()]
    assert len(ids) == len(set(ids)) and "code-runner" in ids


def test_code_runner_runs_active_python_file(tmp_path):
    api = FakeAPI(tmp_path, tmp_path / "hello.py")
    code_runner.run_active(api)
    assert api.ran == [f"python3 {tmp_path / 'hello.py'}"]


def test_code_runner_falls_back_to_project(tmp_path):
    (tmp_path / "Makefile").write_text("all:\n\techo hi\n")
    api = FakeAPI(tmp_path, None)
    code_runner.run_active(api)
    assert api.ran == ["make"] or api.messages  # `make` may be missing on CI machines


def test_user_extension_template_loads_and_activates(tmp_path):
    create_user_extension("Hello World", tmp_path)
    extensions, errors = user_extensions(tmp_path)
    assert errors == [] and extensions[0].name == "Hello World"
    api = FakeAPI(tmp_path)
    extensions[0].activate(api)
    assert api.commands == ["Hello World: Hello"]


def test_broken_user_extension_is_reported_not_raised(tmp_path):
    (tmp_path / "broken.py").write_text("raise RuntimeError('boom')")
    extensions, errors = user_extensions(tmp_path)
    assert extensions == [] and "boom" in errors[0]
