#!/bin/bash

# Script to update the Bear Map application and restart the service
# This script is called by the GitHub webhook handler

set -e  # Exit on error

# Configuration
REPO_DIR="/home/matthewpicone/bearMap"
VENV_PIP="/home/matthewpicone/bearMap/venv/bin/pip"
SERVICE_NAME="bearmap.service"
LOG_FILE="/home/matthewpicone/bearMap/update.log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_message "========== Update Process Started =========="

# Navigate to repository directory
if [ ! -d "$REPO_DIR" ]; then
    log_message "ERROR: Repository directory not found: $REPO_DIR"
    exit 1
fi

cd "$REPO_DIR" || exit 1
log_message "Changed to directory: $REPO_DIR"

# Pull latest changes from main branch
log_message "Pulling latest changes from main branch..."
if git pull origin main; then
    log_message "Successfully pulled latest changes"
else
    log_message "ERROR: Failed to pull changes from repository"
    exit 1
fi

# Update Python dependencies
if [ ! -f "$VENV_PIP" ]; then
    log_message "ERROR: Virtual environment pip not found: $VENV_PIP"
    exit 1
fi

log_message "Updating Python dependencies..."
if "$VENV_PIP" install -r requirements.txt; then
    log_message "Successfully updated dependencies"
else
    log_message "ERROR: Failed to update dependencies"
    exit 1
fi

# Restart systemd service
# Note: This requires sudo access. Configure sudoers to allow the service user
# to run 'systemctl restart bearmap.service' without a password prompt.
# Example sudoers entry:
#   matthewpicone ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bearmap.service
log_message "Restarting $SERVICE_NAME..."
if sudo systemctl restart "$SERVICE_NAME"; then
    log_message "Successfully restarted $SERVICE_NAME"
else
    log_message "ERROR: Failed to restart $SERVICE_NAME"
    exit 1
fi

# Check service status
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    log_message "Service $SERVICE_NAME is running"
    log_message "========== Update Process Completed Successfully =========="
else
    log_message "WARNING: Service $SERVICE_NAME may not be running correctly"
    log_message "========== Update Process Completed with Warnings =========="
    exit 1
fi
