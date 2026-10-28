"""Git: the workspace shows the branch and a Source Control view when this is enabled."""


def activate(api) -> None:
    api.add_command("Git: Open Lazygit", "Open lazygit in the terminal if it's installed", lambda: api.run_in_terminal("lazygit"))
    api.add_command("Git: Status", "Run git status in the terminal", lambda: api.run_in_terminal("git status"))
