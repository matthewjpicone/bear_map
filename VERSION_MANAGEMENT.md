# Version Management System

## Overview

The Bear Map project uses an automated versioning system that keeps `version.json`, `package.json`, and git tags in sync.

## Components

### 1. **Semantic Release** (Primary)
- Runs in GitHub Actions CI/CD pipeline
- Analyzes commit messages (conventional commits) to determine version bump
- Automatically tags releases on git
- Updates CHANGELOG.md
- Pushes changes back to repo

### 2. **Version Update Script** (Fallback & Server-Side)
- Location: `scripts/update_version.py`
- Python script that ensures version consistency
- Runs on both CI/CD pipeline and server deployment
- Priority order:
  1. Latest git tag (from semantic-release)
  2. Version from package.json
  3. Default fallback to "1.0.0"

### 3. **Deployment Script** (Server-Side)
- Location: `scripts/update_and_restart.sh`
- Runs when server receives deployment
- Calls `update_version.py` after pulling latest code
- Ensures version.json is always synced

## Workflow

### On Push to Main:

1. **GitHub Actions triggers** (`deploy.yml`)
   - ✅ Runs tests and linting
   - ✅ Runs semantic-release (analyzes conventional commits)
   - ✅ Runs Python version update script as fallback
   - ✅ Commits version file updates back to repo
   - ✅ Deploys to server

2. **Server Receives Deployment**
   - ✅ Runs update_and_restart.sh
   - ✅ Pulls latest code from main
   - ✅ Calls update_version.py (ensures version is current)
   - ✅ Updates dependencies
   - ✅ Restarts the service

3. **API Serves Current Version**
   - ✅ GET `/api/version` returns version.json content
   - ✅ Server always has up-to-date version info

## Version Update Triggers

### Automatic Updates Happen When:
- ✅ Code is pushed to main branch
- ✅ Server receives deployment webhook
- ✅ CI/CD pipeline runs

### Manual Update (if needed):
```bash
python3 scripts/update_version.py
```

## Files Involved

- `version.json` - Main version file served by API
- `package.json` - NPM package version (kept in sync)
- `.releaserc.json` - Semantic release configuration
- `scripts/update_version.py` - Version sync script
- `scripts/update_and_restart.sh` - Deployment script
- `.github/workflows/deploy.yml` - CI/CD pipeline

## Troubleshooting

### Version not updating?

1. **Check git tags:**
   ```bash
   git tag -l
   git describe --tags --abbrev=0
   ```

2. **Check package.json version:**
   ```bash
   cat package.json | grep version
   ```

3. **Manual sync:**
   ```bash
   python3 scripts/update_version.py
   ```

4. **Check API:**
   ```bash
   curl http://localhost:8000/api/version
   ```

### Semantic Release not working?

- Ensure commits follow [Conventional Commits](https://www.conventionalcommits.org/) format
- Examples:
  - `feat: add new feature` → minor version bump
  - `fix: fix bug` → patch version bump
  - `feat!: breaking change` → major version bump

## How to Use Conventional Commits

Use one of these prefixes for your commit messages:

- `feat:` - New feature (minor bump)
- `fix:` - Bug fix (patch bump)
- `docs:` - Documentation changes
- `chore:` - Maintenance/build tasks
- `refactor:` - Code refactoring
- `test:` - Test changes
- `perf:` - Performance improvements

Example:
```bash
git commit -m "feat: add Discord webhook integration"
git commit -m "fix: resolve castle placement collision bug"
git commit -m "chore: update dependencies"
```

## Version History

- **2.0.1** - Current (synced across all files)
- **2.0.0** - Previous stable release
- **1.0.4** - Initial release

---

**Last Updated:** 2025-12-18  
**Author:** Matthew Picone

