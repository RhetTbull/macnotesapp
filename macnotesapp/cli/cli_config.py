"""Simple config loader/writer for macnotesapp CLI"""

from __future__ import annotations

import os
import pathlib

import toml
from xdg import xdg_config_home

from macnotesapp import NotesApp


def get_config_dir() -> pathlib.Path:
    """Get the directory where config files are stored; create it if necessary."""
    config_dir = xdg_config_home() / "macnotesapp"
    if not config_dir.is_dir():
        config_dir.mkdir(parents=True)
    return config_dir

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
    config_file = CONFIG_FILE

    def __init__(self):
        if not self.config_file.is_file():
            self._create_config_file()

    def read(self) -> dict[str, str]:
        """Read data from config file"""
        data = toml.load(self.config_file)
        return data.get("defaults", {})

    def write(self, settings: dict[str, str]):
        """Write settings dict to config file"""
        data = {"defaults": settings}
        if not self.config_file.is_file():
            self._create_config_file()
        with open(self.config_file, "w") as fp:
            toml.dump(data, fp)

    @property
    def account(self):
        """Return default account"""
        data = self.read()
        return data.get("account", NotesApp().default_account)

    @property
    def folder(self):
        """Return default folder"""
        data = self.read()
        if folder := data.get("folder"):
            return folder
        notes = NotesApp()
        return notes.account(notes.default_account).default_folder

    @property
    def format(self):
        """Return default note format"""
        data = self.read()
        return data.get("format", DEFAULT_FORMAT)

    @property
    def editor(self):
        """Return default editor"""
        data = self.read()
        editor = data.get("editor", DEFAULT_EDITOR)
        if editor.startswith("$"):
            # environment variable
            return os.environ.get(editor[1:], DEFAULT_EDITOR)
        return editor

    def _create_config_file(self):
        config_dir = self.config_file.parent
        config_dir.mkdir(exist_ok=True)
        notes = NotesApp()
        account = notes.default_account
        folder = notes.account(account).default_folder
        config_defaults = {
            "defaults": {
                "editor": DEFAULT_EDITOR,
                "format": DEFAULT_FORMAT,
                "account": account,
                "folder": folder,
            },
        }
        with open(self.config_file, "w") as fp:
            toml.dump(config_defaults, fp)
