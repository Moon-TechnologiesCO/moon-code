from moon import cli
from moon.core.updater import Release, parse_version


def test_parse_version():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("0.10.0-beta") > parse_version("0.9.9")


def test_update_reports_up_to_date(monkeypatch, capsys):
    monkeypatch.setattr(cli.updater, "newer_release", lambda: None)
    assert cli.main(["update"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_update_installs_newer_release(monkeypatch):
    installed = []
    monkeypatch.setattr(cli.updater, "newer_release", lambda: Release("v9.0.0", None))
    monkeypatch.setattr(cli.updater, "install", lambda release: installed.append(release.tag) or 0)
    assert cli.main(["update"]) == 0
    assert installed == ["v9.0.0"]


def test_new_creates_project_without_opening(tmp_path, capsys):
    assert cli.main(["new", "demo", "-t", "node", "-d", str(tmp_path), "--no-open"]) == 0
    assert (tmp_path / "demo" / "index.js").exists()


def test_update_from_app_relaunches_in_same_folder(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_update", lambda: 0)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/moon")
    monkeypatch.setattr(cli.os, "execv", lambda path, args: calls.append(args))
    cli._update_and_relaunch("/home/me/project")
    assert calls[0] == ["/usr/bin/moon", "/home/me/project"]  # a real execv never returns


def test_failed_update_does_not_relaunch(monkeypatch):
    monkeypatch.setattr(cli, "_update", lambda: 1)
    monkeypatch.setattr(cli.os, "execv", lambda *a: (_ for _ in ()).throw(AssertionError("relaunched")))
    assert cli._update_and_relaunch(None) == 1
