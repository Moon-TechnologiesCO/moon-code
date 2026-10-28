"""Code Runner: runs the active file or the whole project in the integrated terminal."""

from moon.core.languages import language_for, project_command, required_tool, run_command


def _run(api, command: str) -> None:
    missing = required_tool(command)
    if missing:
        api.notify(f"'{missing}' is not installed. Install it and try again.", "warning")
        return
    api.run_in_terminal(command)


def run_active(api) -> None:
    path = api.active_file()
    if path is None:
        run_project(api)
        return
    command = run_command(path)
    if command is None:
        api.notify(f"{language_for(path).name} files can't be run directly. Trying the project instead.")
        run_project(api)
        return
    api.save_active()
    _run(api, command)


def run_project(api) -> None:
    command = project_command(api.project_root)
    if command is None:
        api.notify("Couldn't detect how to run this project. Open a file and press F5.", "warning")
        return
    api.save_active()
    _run(api, command)


def activate(api) -> None:
    api.add_command("Run: Run Active File", "Save and run the active file (F5)", lambda: run_active(api))
    api.add_command("Run: Run Project", "Detect the project type and run it (ctrl+F5)", lambda: run_project(api))
