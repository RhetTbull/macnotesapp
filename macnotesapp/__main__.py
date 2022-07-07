"""Entry point for macnotesapp CLI"""

import sys

import click

import macnotesapp
from macnotesapp import __version__
import pathlib
import tempfile
import os.path
import time

# unique sentinel for indicating whether a file was passed to --file
# if no file passed, reads from stdin
# if your file is named this, you're out of luck
with tempfile.TemporaryDirectory() as tmp:
    FILE_FLAG = os.path.join(tmp, f"____MACNOTESAPP____{time.time()}____")


@click.command(name="add")
@click.option("--name", "-n", type=str)
@click.option("--body", type=str, required=False)
@click.option("--file", required=False, is_flag=False, flag_value=FILE_FLAG)
def add_note(name, body, file):
    """Add new note named NAME with body BODY"""
    print(f"{name=}, {body=}, {file=}")
    if body and file:
        print("Can't provide both file and body", file=sys.stderr)
        raise click.Abort()
    if file == FILE_FLAG:
        # --file passed as flag with no parameter
        body = sys.stdin.read()
    elif file:
        # a filename passed
        fp = pathlib.Path(file)
        if not fp.is_file():
            print(f"--file must be a valid file path: '{file}'", file=sys.stderr)
            raise click.Abort()
        body = fp.read_text()
    if not name:
        name, body = body.split("\n", 1)
    print(f"{name=}, {body=}, {file=}")


# Click CLI object & context settings
class CLI_Obj:
    def __init__(self, debug=False, group=None):
        self.debug = debug
        self.group = group


CTX_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CTX_SETTINGS)
@click.option(
    "--debug",
    required=False,
    is_flag=True,
    help="Enable debug output",
    hidden=True,
)
@click.version_option(__version__, "--version", "-v")
@click.pass_context
def cli_main(ctx, debug):
    """notes: work with Apple Notes on the command line"""
    ctx.obj = CLI_Obj(group=cli_main)


cli_main.add_command(add_note)

if __name__ == "__main__":
    cli_main()
