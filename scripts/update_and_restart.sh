#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="/home/matthewpicone/bear_map"
VENV_DIR="$REPO_DIR/.venv"
PY="$VENV_DIR/bin/python"
LOG="$REPO_DIR/update.log"

exec >>"$LOG" 2>&1

echo "=============================="
echo "Update script triggered: $(date -Is)"
echo "Repo: $REPO_DIR"
echo "=============================="

cd "$REPO_DIR"

# Safety: ensure we're in a git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: $REPO_DIR is not a git repository"
  exit 1
fi

# Deploy EXACTLY origin/main
git fetch --prune origin
git checkout -f main
git reset --hard origin/main
git clean -fd

echo "Deployed commit: $(git rev-parse --short HEAD) - $(git log -1 --pretty=%s)"

# Choose an interpreter that exists
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.12)"
else
  PYTHON_BIN="$(command -v python3)"
fi

echo "Using interpreter: $PYTHON_BIN"

# Ensure venv exists AND the python inside it actually runs
# (handles broken symlinks / missing interpreter)
if [[ ! -e "$PY" ]] || [[ ! -x "$PY" ]] || ! "$PY" -V >/dev/null 2>&1; then
  echo "Creating venv at $VENV_DIR"
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "Venv python: $("$PY" -V 2>&1)"

# Upgrade pip tooling inside the venv
"$PY" -m pip install --upgrade pip wheel setuptools

# Install python deps
if [[ -f "$REPO_DIR/requirements.txt" ]]; then
  echo "Installing requirements.txt"
  "$PY" -m pip install -r "$REPO_DIR/requirements.txt"
else
  echo "WARNING: requirements.txt not found at $REPO_DIR/requirements.txt"
fi

# Optional frontend steps
if [[ -f "$REPO_DIR/package.json" ]] && command -v npm >/dev/null 2>&1; then
  echo "Running npm install/build (if applicable)"
  npm ci || npm install
  npm run build || true
fi

# Quick sanity check (non-fatal but useful)
"$PY" -m uvicorn --version || true

echo "Restarting bearmap.service"
sudo /bin/systemctl daemon-reload
sudo /bin/systemctl reset-failed bearmap.service
sudo /bin/systemctl restart bearmap.service

echo "Update complete: $(date -Is)"
echo "Wrote log: $LOG"