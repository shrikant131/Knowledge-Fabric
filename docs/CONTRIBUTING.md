# Contributing

## Development loop

```bash
python -m venv .venv
pip install -r requirements.txt
pytest -q
```

Before opening a change:

1. add or update tests;
2. run the full test suite;
3. run the golden evaluation when retrieval/generation changes;
4. update relevant documentation;
5. keep secrets out of source control.

## Definition of done

A feature is complete when implementation, tests, configuration, documentation and failure behavior are updated together.
