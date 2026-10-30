"""Test CLI config file handling"""

from macnotesapp.cli.cli_config import DEFAULT_FORMAT, ConfigSettings


def test_missing_config_file(tmp_path, monkeypatch):
    """Reading settings doesn't create the config file or touch Notes.app"""
    config = ConfigSettings()
    config.config_file = tmp_path / "macnotesapp" / "macnotesapp.toml"
    assert config.read() == {}
    assert config.format == DEFAULT_FORMAT
    assert not config.config_file.parent.exists()


def test_round_trip(tmp_path, monkeypatch):
    config = ConfigSettings()
    config.config_file = tmp_path / "macnotesapp" / "macnotesapp.toml"
    settings = {
        "account": "iCloud",
        "folder": "Notes",
        "format": "Markdown",
        "editor": "$MY_EDITOR",
    }
    config.write(settings)
    assert config.read() == settings
    assert config.account == "iCloud"
    assert config.folder == "Notes"
    monkeypatch.setenv("MY_EDITOR", "/usr/bin/vi")
    assert config.editor == "/usr/bin/vi"
    monkeypatch.delenv("MY_EDITOR")
    assert config.editor is None
