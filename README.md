# Bear Map

FastAPI-powered tool for visualizing and arranging the "Bear Planner" layout. The app serves a small API plus a static
HTML/JS client from `static/`.

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

The app loads its state from `config.json` at startup and persists changes via `POST /api/save`. Player data is exposed
for download via `/players.csv`.

### Environment Variables

Create a `.env` file (see `.env.example`) with the following configuration:

- `GITHUB_WEBHOOK_SECRET`: Secret token for validating GitHub webhook payloads. Generate a secure random string and
  configure it in your GitHub repository webhook settings.

### GitHub Webhook for Automatic Updates

The application includes a webhook handler at `/webhook/github` that enables automatic deployments when code is pushed
to the main branch.

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

Logs are written to `/home/matthewpicone/bearMap/update.log` on the production server.

## Development notes

- Static assets live in `static/`.
- The FastAPI application is defined in `main.py`.
- `requirements.txt` pins the versions needed for local development and GitHub Codespaces installs.

## Automated Versioning and Releases

This project uses [Semantic Release](https://semantic-release.gitbook.io/) for automated versioning and changelog
generation.

### How It Works

1. **Commit Convention**: Follow [Conventional Commits](https://www.conventionalcommits.org/) format:
    - `feat:` - New features (triggers minor version bump)
    - `fix:` - Bug fixes (triggers patch version bump)
    - `BREAKING CHANGE:` - Breaking changes (triggers major version bump)
    - `chore:`, `docs:`, `style:`, etc. - No version bump

2. **Automatic Process**: When code is pushed to the `main` branch:
    - GitHub Actions runs the CI/CD pipeline
    - Semantic Release analyzes commit messages since the last release
    - If version-bumping commits are found:
        - Version is updated in `package.json` and `version.json`
        - `CHANGELOG.md` is updated with release notes
        - Changes are committed back to the repository
        - A GitHub release is created with release notes

3. **Configuration**:
    - `.releaserc.json` - Semantic Release configuration
    - `package.json` - NPM package metadata (required by Semantic Release)
    - `.github/workflows/deploy.yml` - CI/CD pipeline with versioning step

### Troubleshooting

If versioning fails:

- Ensure commits follow the Conventional Commits format
- Check that the workflow has `contents: write` permission
- Verify all required semantic-release plugins are installed
- Review the GitHub Actions logs for errors

## Priority and Efficiency Scoring

The application computes priority ranks and efficiency scores for castle placements to help optimize rally assignments.

### Priority Score (1-100 Rank)

Priority determines the order in which castles should be assigned to optimal positions. It's calculated from player
stats:

- **Power**: 50% weight (log-transformed to handle large ranges)
- **Player Level**: 20% weight
- **Command Centre Level**: 20% weight
- **Attendance**: 10% weight

Each metric is normalized using 5th-95th percentiles to reduce outlier impact. Missing attendance uses the median value.
Command centre level of 0 is treated as 0 priority contribution.

Castles are ranked 1-100 (1 being highest priority) based on descending priority score, with ties broken by power, then
player level, then ID.

### Efficiency Score (0-100, Lower is Better)

Efficiency measures how well the current placement matches an ideal allocation that minimizes travel time for
high-priority players.

#### Travel Time Calculation

Uses Chebyshev distance (max(dx, dy)) between castle center and bear center.

#### Ideal Allocation

- Processes castles in priority order (highest first)
- Assigns to best available tile based on preference:
    - "Bear 1": Closest to Bear 1
    - "Bear 2": Closest to Bear 2
    - "Both": Closest to either bear (min distance)
- Respects locked castle positions
- Excludes occupied tiles (banners, bear influence areas)

#### Actual vs Ideal

- Regret = max(0, actual_travel_time - ideal_travel_time)
- Tscale = 90th percentile of nonzero regrets
- Base component = clamp01(regret / Tscale)

#### Blocking Penalty

Within each preference group ("Bear 1", "Bear 2", "Both"):

- For each pair (higher priority i, lower priority j)
- If actual_travel_time(i) < actual_travel_time(j), i is "blocking" j
- Penalty = (travel_time(j) - travel_time(i)) * sigmoid(rank_diff)
- Where sigmoid(d) = 1 / (1 + exp(-(d-10)/5))
- Normalized by 90th percentile across all castles

#### Final Score

efficiency_score = round(100 * clamp01(0.75 * base + 0.25 * block_norm))

### UI Features

- Table columns for Priority Rank and Efficiency Score
- Sortable by both metrics
- Tooltip shows detailed breakdown on hover
- Scores update automatically when placements change
