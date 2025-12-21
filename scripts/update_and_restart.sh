#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$HOME/bear_map"
BRANCH="main"
REMOTE="origin"
SERVICE_NAME="bearmap"

cd "$REPO_DIR"

git config --global --add safe.directory "$REPO_DIR" >/dev/null 2>&1 || true

git fetch --prune "$REMOTE"
git reset --hard "$REMOTE/$BRANCH"
git clean -fd

if [[ ! -x "./venv/bin/python" ]]; then
  python3 -m venv venv
fi

./venv/bin/python -m pip install --upgrade pip setuptools wheel
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python -m pip check

sudo systemctl restart "$SERVICE_NAME"
sudo systemctl is-active --quiet "$SERVICE_NAME"
