"""Simple config loader/writer for macnotesapp CLI"""

from __future__ import annotations

import os
import pathlib
import sys

import tomli_w
from xdg_base_dirs import xdg_config_home

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def get_config_dir() -> pathlib.Path:
    """Get the directory where config files are stored"""
    return xdg_config_home() / "macnotesapp"


CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "macnotesapp.toml"

# Default config options
FORMAT_PLAINTEXT = "plaintext"
FORMAT_HTML = "HTML"
FORMAT_MARKDOWN = "Markdown"
FORMAT_OPTIONS = [FORMAT_PLAINTEXT, FORMAT_HTML, FORMAT_MARKDOWN]
DEFAULT_FORMAT = FORMAT_PLAINTEXT
DEFAULT_EDITOR = "$EDITOR"


class ConfigSettings:
    """Settings for the CLI stored in CONFIG_FILE.

    Reading settings never creates the config file; it is written by `notes config`.
    Defaults for account and folder are looked up from Notes.app only when needed.
    """

    config_file = CONFIG_FILE

    def read(self) -> dict[str, str]:
        """Read data from config file; returns empty dict if file doesn't exist"""
        if not self.config_file.is_file():
            return {}
        with open(self.config_file, "rb") as fp:
            data = tomllib.load(fp)
        return data.get("defaults", {})

    def write(self, settings: dict[str, str]):
        """Write settings dict to config file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "wb") as fp:
            tomli_w.dump({"defaults": settings}, fp)

    @property
    def account(self) -> str:
        """Return default account"""
        if account := self.read().get("account"):
            return account
        from macnotesapp import NotesApp

        return NotesApp().default_account

    @property
    def folder(self) -> str:
        """Return default folder"""
        if folder := self.read().get("folder"):
            return folder
        from macnotesapp import NotesApp

        notes = NotesApp()
        return notes.account(self.account).default_folder

    @property
    def format(self) -> str:
        """Return default note format"""
        return self.read().get("format", DEFAULT_FORMAT)

    @property
    def editor(self) -> str | None:
        """Return default editor or None if not set (click.edit() will then choose one)"""
        editor = self.read().get("editor", DEFAULT_EDITOR)
        if editor.startswith("$"):
            # environment variable
            return os.environ.get(editor[1:])
        return editor
