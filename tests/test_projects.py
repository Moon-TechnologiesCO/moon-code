import pytest

from moon.core.projects import create_project, slugify


def test_python_template_creates_runnable_main(tmp_path):
    folder = create_project(tmp_path, "Hello Moon", "python", git_init=False)
    assert (folder / "main.py").read_text().count("Hello from Hello Moon!") == 1


def test_csharp_template_names_project_file(tmp_path):
    folder = create_project(tmp_path, "My App", "csharp", git_init=False)
    assert (folder / "my-app.csproj").exists()


def test_rejects_existing_folder_and_bad_names(tmp_path):
    create_project(tmp_path, "demo", "empty", git_init=False)
    with pytest.raises(FileExistsError):
        create_project(tmp_path, "demo", "empty", git_init=False)
    with pytest.raises(ValueError):
        create_project(tmp_path, "../escape", "empty", git_init=False)


def test_slugify():
    assert slugify("My Cool App!") == "my-cool-app"
