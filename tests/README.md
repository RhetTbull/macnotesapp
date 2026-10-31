# Tests for macnotesapp

Tests are split into three tiers (see `conftest.py`):

| Directory | Talks to Notes.app | Enabled by | Notes |
|---|---|---|---|
| `unit/` | No | default | Uses fakes in `unit/fakes.py`. Runs in CI. |
| `integration/` | Yes | `--integration` | Automated. Only creates, changes, and deletes notes in temporary `macnotesapp-test-*` folders in the default account, which are deleted afterwards (their notes go to Recently Deleted). |
| `manual/` | Yes | `--manual` | Prompts for input, so run with `-s`. Changes notes you select and creates notes in the default folder. |

```bash
uv run pytest                          # unit tests
uv run pytest --integration            # unit and integration tests
uv run pytest --manual -s tests/manual # manual tests
```

The first run against Notes.app asks for permission to control Notes. Grant it to your terminal in System Settings > Privacy & Security > Automation.
