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
uv run pytest
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

The tests are run with [pytest](https://docs.pytest.org/en/stable/) and are split into three tiers:

```bash
# unit tests: no Notes.app access; run by default and in CI
uv run pytest

# also run integration tests against Notes.app; these only touch temporary
# macnotesapp-test-* folders in the default account, which are deleted afterwards
uv run pytest --integration

# manual tests: prompt for input and change notes you select; require -s
uv run pytest --manual -s tests/manual
```

Lint and format with [ruff](https://docs.astral.sh/ruff/):

```bash
uv run ruff check
uv run ruff format
```

CI runs ruff, `cog --check README.md`, the unit tests on Python 3.10–3.14, and a package and docs build.

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
