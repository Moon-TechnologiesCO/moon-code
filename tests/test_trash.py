from moon.core.trash import move_to_trash


def test_move_to_trash_keeps_restore_info(tmp_path):
    trash = tmp_path / "Trash"
    file = tmp_path / "a.txt"
    file.write_text("x")
    moved = move_to_trash(file, trash)
    assert not file.exists() and moved.read_text() == "x"
    info = (trash / "info" / "a.txt.trashinfo").read_text()
    assert f"Path={file}" in info


def test_same_name_twice_gets_a_new_name(tmp_path):
    trash = tmp_path / "Trash"
    for _ in range(2):
        (tmp_path / "a.txt").write_text("x")
        move_to_trash(tmp_path / "a.txt", trash)
    assert sorted(p.name for p in (trash / "files").iterdir()) == ["a 2.txt", "a.txt"]
