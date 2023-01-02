# Developer Notes for MacNotesApp

These notes are to remind me of things I need to do to maintain this project. They may be useful for anyone who wants to contribute to MacNotesApp.

## Development Environment

MacNotesApp uses poetry for dependency management and virtual environments. To set up a development environment, run the following commands:

```bash
poetry install
poetry shell
```

## Version Management

Versioning is handled with [bump2version](https://github.com/c4urself/bump2version). To bump the version, run the following command:

```bash
bump2version <major|minor|patch> --verbose
```

## Building

The `build.sh` script will build the project and package it for distribution. To build the project, run the following command:

```bash
./build.sh
```

## Testing

The tests are run with [pytest](https://docs.pytest.org/en/stable/). The test suite is interactive and will operate on your actual Notes.app data. Because the tests require user input, they must be run with `pytest -s`. To run the tests, run the following command:

```bash
pytest -v -s tests/
```

## Documentation

The documentation is maintained in the `docs/` directory. The documentation is built with [mkdocs](https://www.mkdocs.org/). To build the documentation, run the following command:

```bash
mkdocs build
```

To deploy the documentation to GitHub Pages, run the following command:

```bash
mkdocs gh-deploy
```

The docs will be built (but not deployed) when you run the `./build.sh` script.
