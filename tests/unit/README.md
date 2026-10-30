# Unit tests

These tests do not use Notes.app and are safe to run at any time:

```bash
uv run pytest tests/unit
```

ScriptingBridge objects are replaced by fakes defined in `fakes.py`; predicates are evaluated against `NSArray`s of dictionaries.
