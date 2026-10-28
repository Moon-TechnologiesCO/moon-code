from moon.core.files import fuzzy_filter, fuzzy_score, search, walk_files


def test_walk_skips_dependency_folders(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x")
    assert [str(p) for p in walk_files(tmp_path)] == ["src/app.py"]


def test_fuzzy_prefers_file_name_matches():
    files = ["docs/readme.md", "src/moon/app.py", "src/application.py"]
    assert fuzzy_filter("app", files)[0] in ("src/moon/app.py", "src/application.py")
    assert fuzzy_score("xyz", "src/app.py") is None


def test_search_finds_lines(tmp_path):
    (tmp_path / "a.py").write_text("one\nTODO: fix\nthree\n")
    matches = search(tmp_path, "todo")
    assert [(m.path.name, m.line) for m in matches] == [("a.py", 2)]
