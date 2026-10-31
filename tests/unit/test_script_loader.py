"""Test loading and compiling the AppleScript handlers (does not run them)"""

import re

from macnotesapp.script_loader import get_script, load_script_source


def test_script_source_is_utf8():
    source = load_script_source()
    assert "«class seld»" in source
    assert "�" not in source


def test_script_compiles():
    """Compiling needs Notes.app's scripting dictionary but does not launch Notes"""
    assert get_script() is get_script()


def test_called_handlers_exist():
    """Every handler called from Python must be defined in the script"""
    import pathlib

    import macnotesapp

    source = load_script_source()
    defined = set(re.findall(r"^on (\w+)\(", source, flags=re.M))
    package = pathlib.Path(macnotesapp.__file__).parent
    called = set()
    for path in package.rglob("*.py"):
        for line in path.read_text().splitlines():
            if not line.strip().startswith("#"):
                called.update(re.findall(r'run_script\(\s*"(\w+)"', line))
    assert called
    assert called <= defined, called - defined
