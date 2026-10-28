from moon import cli


def test_update_reports_up_to_date(monkeypatch, capsys):
    monkeypatch.setattr(cli.updater, "newer_release", lambda: None)
    assert cli.main(["update"]) == 0
    assert "al día" in capsys.readouterr().out


def test_update_installs_newer_release(monkeypatch):
    installed = []
    monkeypatch.setattr(cli.updater, "newer_release", lambda: "v9.0.0")
    monkeypatch.setattr(cli.updater, "install", lambda tag: installed.append(tag) or 0)
    assert cli.main(["update"]) == 0
    assert installed == ["v9.0.0"]
