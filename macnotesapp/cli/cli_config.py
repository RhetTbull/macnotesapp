"""Simple config loader/writer for macnotesapp CLI"""

import os
import pathlib
from typing import Dict

import toml

from macnotesapp import NotesApp

CONFIG_DIR = pathlib.Path("~/.config/macnotesapp").expanduser()
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

    def read(self) -> Dict:
        """Read data from config file"""
        data = toml.load(self.config_file)
        return data.get("defaults", dict())

    def write(self, settings: Dict):
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
