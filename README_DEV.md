# Developer Notes for MacNotesApp

These notes are to remind me of things I need to do to maintain this project. They may be useful for anyone who wants to contribute to MacNotesApp.

## Development Environment

MacNotesApp uses [uv](https://docs.astral.sh/uv/) for dependency management and virtual environments. To set up a development environment, run the following commands:

```bash
uv sync
```

This will create a virtual environment in `.venv/` and install all dependencies including dev dependencies.

To run commands within the virtual environment, use `uv run`:

```bash
uv run notes --help
uv run pytest -v -s tests/
```

Or activate the virtual environment manually:

```bash
source .venv/bin/activate
```

## Version Management

Versioning is handled with [bump2version](https://github.com/c4urself/bump2version). To bump the version, run the following command:

```bash
uv run bump2version <major|minor|patch> --verbose
```

## Building

The `build.sh` script will build the project and package it for distribution. To build the project, run the following command:

```bash
./build.sh
```

## Publishing

To publish to PyPI:

```bash
uv build
uv publish
```

## Testing

The tests are run with [pytest](https://docs.pytest.org/en/stable/). The test suite is interactive and will operate on your actual Notes.app data. Because the tests require user input, they must be run with `pytest -s`. To run the tests, run the following command:

```bash
uv run pytest -v -s tests/
```

## Documentation

The documentation is maintained in the `docs/` directory. The documentation is built with [mkdocs](https://www.mkdocs.org/). To build the documentation, run the following command:

```bash
uv run mkdocs build
```

To deploy the documentation to GitHub Pages, run the following command:

```bash
uv run mkdocs gh-deploy
```

The docs will be built (but not deployed) when you run the `./build.sh` script.
