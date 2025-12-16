# Bear Map

FastAPI-powered tool for visualizing and arranging the "Bear Planner" layout. The app serves a small API plus a static HTML/JS client from `static/`.

## Quick start

1. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the API and static site:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Open the UI at <http://localhost:8000>.

## Configuration

The app loads its state from `config.json` at startup and persists changes via `POST /api/save`. Player data is exposed for download via `/players.csv`.

## Development notes

- Static assets live in `static/`.
- The FastAPI application is defined in `main.py`.
- `requirements.txt` pins the versions needed for local development and GitHub Codespaces installs.
