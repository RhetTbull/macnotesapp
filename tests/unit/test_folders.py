"""Test finding folders by path with FolderTree, without Notes.app"""

import pytest

import macnotesapp.notesapp as notesapp
from macnotesapp.errors import FolderNotFoundError, MacNotesAppError
from macnotesapp.notesapp import FolderTree

FOLDERS = [
    # id, name, parent id
    ("notes", "Notes", None),
    ("work", "Work", None),
    ("projects", "Projects", "work"),
    ("2026", "2026", "projects"),
    ("archive", "Archive", None),
    ("slash", "a/b", None),
    ("top-projects", "Projects", None),
    ("dup1", "Dup", None),
    ("dup2", "Dup", None),
    ("dupchild", "Child", "dup2"),
    ("nested-x1", "X", "work"),
    ("nested-x2", "X", "archive"),
]


@pytest.fixture
def tree() -> FolderTree:
    ids, names, parents = zip(*FOLDERS, strict=True)
    return FolderTree(list(ids), list(names), list(parents))


@pytest.mark.parametrize(
    "path, folder_id",
    [
        ("Notes", "notes"),
        ("Work/Projects/2026", "2026"),
        ("work/projects", "projects"),
        # a folder whose name contains "/"
        ("a/b", "slash"),
        # top-level folders come first
        ("Projects", "top-projects"),
        # a subfolder with a unique name can be found by its name, as before #4
        ("2026", "2026"),
        # only one of the folders named Dup has a Child
        ("Dup/Child", "dupchild"),
    ],
)
def test_resolve(tree, path, folder_id):
    assert tree.resolve(path) == folder_id


@pytest.mark.parametrize("path", ["Missing", "Work/Missing", "Projects/2026", ""])
def test_resolve_not_found(tree, path):
    with pytest.raises(FolderNotFoundError):
        tree.resolve(path)


@pytest.mark.parametrize("path", ["Dup", "X"])
def test_resolve_ambiguous(tree, path):
    with pytest.raises(MacNotesAppError, match="2 folders match"):
        tree.resolve(path)


def test_folder_not_found_is_value_error():
    """missing folders raised ValueError before FolderNotFoundError existed"""
    assert issubclass(FolderNotFoundError, ValueError)


def test_paths(tree):
    assert tree.path("2026") == "Work/Projects/2026"
    assert tree.paths() == [
        "a/b",
        "Archive",
        "Archive/X",
        "Dup",
        "Dup",
        "Dup/Child",
        "Notes",
        "Projects",
        "Work",
        "Work/Projects",
        "Work/Projects/2026",
        "Work/X",
    ]


def test_descendants_deepest_first(tree):
    assert tree.descendants("work") == ["2026", "projects", "nested-x1"]
    assert tree.descendants("notes") == []


def test_for_account(monkeypatch):
    calls = []

    def run_script(*args):
        calls.append(args)
        return [["f1", "f2"], ["Top", "Sub"], ["", "f1"]]

    monkeypatch.setattr(notesapp, "run_script", run_script)
    tree = FolderTree.for_account("iCloud")
    assert calls == [("accountGetFolderTree", "iCloud")]
    assert tree.children(None) == ["f1"]
    assert tree.resolve("Top/Sub") == "f2"


def test_resolve_subfolder_of_name_with_slash():
    """a folder inside a top-level folder whose name contains "/" """
    tree = FolderTree(["s", "c"], ["a/b", "c"], [None, "s"])
    assert tree.paths() == ["a/b", "a/b/c"]
    assert tree.resolve("a/b/c") == "c"
    assert tree.find("A/B/C") == ["c"]


def test_orphaned_subfolder_is_top_level():
    """Deleting a folder with AppleScript leaves its subfolders, which keep the
    deleted folder's ID as their parent"""
    tree = FolderTree(["c"], ["Child"], ["deleted"])
    assert tree.paths() == ["Child"]
    assert tree.children(None) == ["c"]
    assert tree.resolve("Child") == "c"


def test_find_only_full_paths(tree):
    """find() doesn't fall back to subfolders by name, unlike resolve()"""
    assert tree.find("2026") == []
    assert tree.find("work/projects") == ["projects"]
    assert sorted(tree.find("Dup")) == ["dup1", "dup2"]
