# Contributing to Bear Map

Thank you for your interest in contributing to Bear Map! This document provides guidelines for contributing to the project.

## Code of Conduct

Please be respectful and constructive in all interactions with other contributors.

## How to Contribute

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Make your changes following the code conventions
4. Write or update tests as needed
5. Commit your changes using conventional commits (see below)
6. Push your branch and open a pull request

## Conventional Commits

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic versioning and changelog generation. All commit messages must follow this format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Commit Types

- **feat**: A new feature (triggers MINOR version bump)
  - Example: `feat: add bulk castle operations`
  - Example: `feat(ui): add dark mode toggle`

- **fix**: A bug fix (triggers PATCH version bump)
  - Example: `fix: correct castle overlap detection`
  - Example: `fix(api): handle null values in castle data`

- **docs**: Documentation only changes (no version bump)
  - Example: `docs: update API endpoint documentation`
  - Example: `docs(readme): add installation instructions`

- **style**: Changes that don't affect code meaning (formatting, whitespace, etc.) (no version bump)
  - Example: `style: format code with black`
  - Example: `style(css): improve button spacing`

- **refactor**: Code changes that neither fix a bug nor add a feature (no version bump)
  - Example: `refactor: simplify castle positioning logic`
  - Example: `refactor(sync): extract WebSocket handler`

- **perf**: Performance improvements (triggers PATCH version bump)
  - Example: `perf: optimize map rendering`
  - Example: `perf(database): add index to castle queries`

- **test**: Adding or updating tests (no version bump)
  - Example: `test: add castle overlap test cases`
  - Example: `test(api): add endpoint integration tests`

- **chore**: Maintenance tasks, dependency updates (no version bump)
  - Example: `chore: update dependencies`
  - Example: `chore(ci): update GitHub Actions workflow`

- **ci**: Changes to CI/CD configuration (no version bump)
  - Example: `ci: add semantic-release to workflow`
  - Example: `ci(deploy): update deployment script`

- **build**: Changes affecting the build system or dependencies (no version bump)
  - Example: `build: update requirements.txt`
  - Example: `build(npm): update package.json`

### Breaking Changes

Breaking changes trigger a MAJOR version bump. To indicate a breaking change, add `BREAKING CHANGE:` in the commit footer or add `!` after the type:

```
feat!: redesign API response format

BREAKING CHANGE: All API endpoints now return data in a new format.
The old format is no longer supported.
```

Or:

```
feat(api)!: change castle endpoint structure
```

### Commit Message Examples

#### Good Examples ✅

```
feat: add auto-placement algorithm for castles
```

```
fix: prevent castle overlap at grid boundaries
```

```
docs: add contributing guidelines
```

```
feat(websocket): implement real-time sync for multiple clients

This adds WebSocket support for real-time updates across
all connected clients with soft-locking mechanism.
```

```
fix(api): handle missing player data gracefully

Fixes #123
```

#### Bad Examples ❌

```
Added new feature  (missing type prefix)
```

```
FIX: bug in castle code  (uppercase type)
```

```
fix castle  (too vague, needs better description)
```

```
feat(): add new button  (empty scope not allowed)
```

## Code Style

### Python

- Follow PEP 8 conventions
- Use Google-style docstrings
- Use type hints where appropriate
- Maximum line length: 100 characters
- Format code with `black`
- Lint with `flake8`

### JavaScript

- Use modern ES6+ syntax
- Use meaningful variable names
- Add comments for complex logic
- Follow existing code structure

## Development Workflow

### Setting Up

```bash
# Clone the repository
git clone https://github.com/matthewjpicone/bear_map.git
cd bear_map

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Node.js dependencies (for semantic-release)
npm install
```

### Running Locally

```bash
# Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access the application at http://localhost:8000

### Running Tests

```bash
# Format code
black .

# Lint code
flake8 . --max-line-length=100
```

### Making a Pull Request

1. Ensure all tests pass
2. Update documentation if needed
3. Use conventional commit messages
4. Reference any related issues in the PR description
5. Wait for CI/CD checks to pass
6. Request review from maintainers

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes (e.g., 1.0.0 → 2.0.0)
- **MINOR**: New features, backwards compatible (e.g., 1.0.0 → 1.1.0)
- **PATCH**: Bug fixes, backwards compatible (e.g., 1.0.0 → 1.0.1)

Versions are automatically determined based on commit messages using semantic-release.

## Questions?

If you have questions about contributing, please open an issue or contact the maintainers.

Thank you for contributing to Bear Map! 🐻
