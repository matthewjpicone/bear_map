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
   uvicorn main:app --reload --host 0.0.0.0 --port 3000
   ```
4. Open the UI at <http://localhost:3000>.

## Configuration

The app loads its state from `config.json` at startup and persists changes via `POST /api/save`. Player data is exposed for download via `/players.csv`.

### Environment Variables

Create a `.env` file (see `.env.example`) with the following configuration:

- `GITHUB_WEBHOOK_SECRET`: Secret token for validating GitHub webhook payloads. Generate a secure random string and configure it in your GitHub repository webhook settings.

### GitHub Webhook for Automatic Updates

The application includes a webhook handler at `/webhook/github` that enables automatic deployments when code is pushed to the main branch.

**Setup:**

1. Configure the webhook secret in your `.env` file:
   ```bash
   GITHUB_WEBHOOK_SECRET=your_secure_random_string
   ```

2. In your GitHub repository settings, add a webhook:
   - **Payload URL**: `https://your-domain.com/webhook/github`
   - **Content type**: `application/json`
   - **Secret**: Same value as `GITHUB_WEBHOOK_SECRET`
   - **Events**: Select "Just the push event"

3. Configure sudo access for the service user to restart the systemd service without a password prompt:
   ```bash
   # Add to /etc/sudoers.d/bearmap
   matthewpicone ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bearmap.service
   ```

4. Install the systemd service:
   ```bash
   sudo cp scripts/bearmap.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable bearmap.service
   sudo systemctl start bearmap.service
   ```

When a push to the main branch is detected, the webhook handler will:
1. Validate the payload signature using HMAC-SHA256
2. Trigger the update script at `scripts/update_and_restart.sh`
3. Pull latest changes from the repository
4. Update Python dependencies
5. Restart the systemd service

Logs are written to `/home/matthewpicone/bear_map/update.log` on the production server.

## Development notes

- Static assets live in `static/`.
- The FastAPI application is defined in `main.py`.
- `requirements.txt` pins the versions needed for local development and GitHub Codespaces installs.
