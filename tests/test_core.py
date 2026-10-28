from moon.core.icons import icon_for, language_for
from moon.core.updater import parse_version
from pathlib import Path


def test_parse_version_handles_v_prefix_and_suffix():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("0.10.0-beta") == (0, 10, 0)


def test_versions_compare_numerically():
    assert parse_version("v0.10.0") > parse_version("0.9.9")


def test_language_for_known_extension():
    assert language_for(Path("app.py")) == "python"
    assert language_for(Path("notes.xyz")) is None


def test_icon_falls_back_to_default():
    assert icon_for(Path("archivo.desconocido")) == "📄"
