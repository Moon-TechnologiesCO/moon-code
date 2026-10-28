from moon.core.config import Settings


def test_settings_roundtrip_and_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(theme="moon-light", tab_size=2)
    settings.save(path)
    path.write_text(path.read_text().replace('"tab_size": 2', '"tab_size": 2, "future_option": true'))
    loaded = Settings.load(path)
    assert loaded.theme == "moon-light" and loaded.tab_size == 2


def test_broken_settings_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    assert Settings.load(path) == Settings()


def test_recent_projects_are_unique_and_newest_first(tmp_path):
    settings = Settings()
    for name in ["a", "b", "a"]:
        settings.add_recent(tmp_path / name)
    assert [p.rsplit("/", 1)[-1] for p in settings.recent_projects] == ["a", "b"]
