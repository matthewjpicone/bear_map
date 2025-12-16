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

## Discord Integration

Bear Map now supports linking to Discord channels or threads to display alliance/map-related messages directly in the app.

### Setup

1. **Create a Discord Bot:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Navigate to the "Bot" section and create a bot
   - Enable "MESSAGE CONTENT INTENT" under Privileged Gateway Intents
   - Copy the bot token

2. **Configure the Bot Token:**
   - Copy `.env.example` to `.env`
   - Add your bot token: `DISCORD_BOT_TOKEN=your_token_here`

3. **Invite the Bot to Your Server:**
   - In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
   - Select scopes: `bot`
   - Select permissions: `Read Messages/View Channels`, `Read Message History`
   - Use the generated URL to invite the bot to your server

4. **Link a Channel:**
   - In Bear Map, navigate to the Discord Integration section
   - Enable Developer Mode in Discord (Settings > Advanced > Developer Mode)
   - Right-click on a channel or thread and select "Copy ID"
   - Paste the channel ID in Bear Map and click "Link Channel"

### Features

- **Read-only message viewing:** View recent messages from your linked Discord channel
- **Channel/Thread support:** Works with both regular channels and threads
- **Configurable message limit:** Choose how many messages to display (10-100)
- **Auto-refresh:** Messages automatically refresh every 30 seconds
- **Attachment support:** See file attachments from Discord messages

### API Endpoints

- `GET /api/discord/status` - Check Discord connection status
- `POST /api/discord/link` - Link a Discord channel (requires `channel_id`)
- `POST /api/discord/unlink` - Unlink the current channel
- `GET /api/discord/messages` - Fetch messages from linked channel (optional `limit` param)

## Development notes

- Static assets live in `static/`.
- The FastAPI application is defined in `main.py`.
- `requirements.txt` pins the versions needed for local development and GitHub Codespaces installs.
- Discord integration is implemented in `server/discord_integration.py`.
