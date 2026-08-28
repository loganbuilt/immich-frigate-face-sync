# Contributing

Keep the project small and appliance-like.

## Development

```bash
python3.13 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
mypy src
pytest
```

Changes that add runtime dependencies should justify why the dependency is needed. Do not add a
recognition model, embeddings store, queue service, telemetry, or a web UI.
