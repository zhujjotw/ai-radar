# AI Radar

AI Radar is a lightweight internal tool for tracking AI open-source projects, evaluating them as a team, and preserving trial outcomes as a small knowledge graph.

## MVP Scope

- Baseline project import
- GitHub project discovery
- Configurable filtering and lightweight scoring
- Project radar, trial tracking, and share archive
- One-hop project knowledge graph

## Development

```bash
uv sync
uv run streamlit run src/app.py
```

Initialize the local SQLite database:

```bash
uv run python scripts/init_db.py
```

