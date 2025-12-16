# Bear Map - GitHub Copilot Instructions

## Project Overview

Bear Map is a FastAPI-powered tool for visualizing and arranging the "Bear Planner" layout. The application serves a REST API plus a static HTML/JS client for interactive bear trap planning and castle management.

## Architecture

### Backend (Python/FastAPI)
- **Framework**: FastAPI with uvicorn server
- **Main entry point**: `main.py`
- **Server modules**: Located in `server/` directory
  - `sync.py`: WebSocket synchronization with soft-locking mechanism
  - `broadcast.py`: Server-sent events (SSE) for real-time updates
  - `update.py`: Update logic
- **Logic modules**: Business logic in `logic/` directory
- **Configuration**: Application state in `config.json`

### Frontend (Static HTML/JS)
- **Location**: `static/` directory
- **Main files**: 
  - `index.html`: Main UI
  - `app.js`: Application logic
  - `sync.js`: WebSocket client synchronization
  - `style.css`: Styling

### Real-time Synchronization
- **WebSocket**: `/ws` endpoint for real-time state sync with soft-locking (20s TTL)
- **SSE**: `/api/stream` endpoint for server-sent events
- **State management**: Last-write-wins strategy with timestamp-based conflict resolution

## Code Conventions

### Python Style
- Follow PEP 8 conventions
- Use type hints where appropriate (e.g., `set[WebSocket]`, `dict[str, dict]`)
- Maximum line length: 100 characters (enforced by flake8)
- Use black for code formatting
- Prefer descriptive variable names

### API Design
- RESTful endpoints under `/api/` prefix
- WebSocket endpoint at `/ws`
- Static files served from root

### State Management
- Configuration persisted to `config.json`
- Use helper functions: `load_config()` and `save_config()`
- Broadcast updates via `broadcast_config()` after state changes

## Development Setup

### Prerequisites
- Python 3.11
- Virtual environment (recommended)

### Installation
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running Locally
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Access
- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs (FastAPI auto-generated)

## Key Dependencies
- `fastapi~=0.124.2`: Web framework
- `uvicorn[standard]~=0.38.0`: ASGI server
- `pydantic~=2.12.5`: Data validation
- `websockets~=15.0.1`: WebSocket support
- `opencv-python`, `numpy`, `pytesseract`, `pillow`: Image processing for scraping

## Common Tasks

### Adding a New API Endpoint
1. Add route function in `main.py` or create a new router in `server/`
2. Use appropriate HTTP method decorator (`@app.get`, `@app.post`, etc.)
3. Include type hints for request/response models
4. Return appropriate status codes

### Modifying Configuration Schema
1. Update `config.json` structure
2. Modify `load_config()` and `save_config()` if needed
3. Update frontend to handle new fields

### WebSocket Updates
1. Modify message handlers in `server/sync.py`
2. Ensure proper broadcasting to other clients
3. Handle soft-lock logic for concurrent edits

## Testing and Quality

### Code Quality Tools
- **Black**: Code formatting (run `black .`)
- **Flake8**: Linting (run `flake8 . --max-line-length=100`)
- **Requirements check**: Ensure `requirements.txt` matches installed packages

### CI/CD Pipeline
- GitHub Actions workflow: `.github/workflows/deploy.yml`
- Runs on push to `main` and pull requests
- Checks:
  - Dependencies up-to-date
  - Code formatting (black)
  - Linting (flake8)
  - TODO comments scan
- Auto-deploys to production server on main branch push

## Deployment

### Production Environment
- Server location: `/home/matthewpicone/bearMap`
- Virtual environment: `/home/matthewpicone/bearMap/venv`
- Systemd service: `bearmap.service`
- Deployment script: `scripts/update_and_restart.sh`

### Manual Deployment
```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart bearmap.service
```

### Webhook Integration
- GitHub webhook handler at `/webhook/github`
- Uses HMAC-SHA256 validation with `GITHUB_WEBHOOK_SECRET`
- Environment variables stored in `.env` (see `.env.example`)

## Security Considerations
- Validate all user inputs
- Use environment variables for secrets (never commit to repo)
- HMAC-SHA256 for webhook validation
- Soft-locking mechanism prevents concurrent edit conflicts

## File Structure
```
.
├── main.py                 # FastAPI application entry point
├── config.json             # Application state and configuration
├── requirements.txt        # Python dependencies
├── .github/
│   └── workflows/
│       └── deploy.yml      # CI/CD pipeline
├── server/                 # Backend modules
│   ├── sync.py            # WebSocket sync with soft-locking
│   ├── broadcast.py       # SSE broadcasting
│   └── update.py          # Update logic
├── static/                 # Frontend assets
│   ├── index.html         # Main UI
│   ├── app.js             # Application logic
│   ├── sync.js            # WebSocket client
│   └── style.css          # Styling
├── logic/                  # Business logic
├── scripts/                # Deployment scripts
└── templates/              # HTML templates (if any)
```

## Common Patterns

### Loading and Saving Configuration
```python
# Load config
config = load_config()

# Modify config
config["some_field"] = new_value

# Save config
save_config(config)

# Notify clients
await notify_config_updated()
```

### Broadcasting Updates
```python
# Notify all connected clients via SSE
await broadcast_config(config)

# Notify via WebSocket (in sync.py)
await broadcast({"type": "updates", "updates": accepted}, sender)
```

### Soft-Lock Pattern (WebSocket)
```python
# Acquire lock
soft_locks[obj_id] = {
    "owner": ws,
    "expires_at": now_ms() + LOCK_TTL_MS
}
await broadcast({"type": "busy", "id": obj_id}, ws)

# Release lock
if lock and lock["owner"] is ws:
    del soft_locks[obj_id]
    await broadcast_lock_release(obj_id)
```

## Notes
- The app uses a grid-based layout system for positioning castles and bear traps
- Player data can be exported via `/players.csv`
- Efficiency scoring is calculated based on configurable weights
- WebSocket connections auto-release locks on disconnect
