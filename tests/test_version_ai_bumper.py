"""
Tests for version_ai_bumper module.

Run with: python -m pytest tests/test_version_ai_bumper.py
"""

import json
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch
import pytest

# Import after adding parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from version_ai_bumper import VersionBumper, ChangeType  # noqa: E402


@pytest.fixture
def temp_repo():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    os.chdir(temp_dir)

    # Create test files
    with open("version.json", "w") as f:
        json.dump({"version": "1.0.0"}, f)

    with open("package.json", "w") as f:
        json.dump({"name": "test", "version": "1.0.0"}, f)

    with open("CHANGELOG.md", "w") as f:
        f.write(
            """# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-01-01

### Added
- Initial release
"""
        )

    yield temp_dir

    # Cleanup
    os.chdir(original_dir)
    shutil.rmtree(temp_dir)


def test_version_bumper_init_with_api_key():
    """Test VersionBumper initialization with API key."""
    bumper = VersionBumper(api_key="test-key")
    assert bumper.api_key == "test-key"
    assert bumper.model == "gpt-4o-mini"


def test_version_bumper_init_without_api_key():
    """Test VersionBumper initialization without API key raises error."""
    # Clear env var if it exists
    original_key = os.environ.get("OPENAI_API_KEY")
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

    with pytest.raises(ValueError, match="OpenAI API key not found"):
        VersionBumper()

    # Restore env var
    if original_key:
        os.environ["OPENAI_API_KEY"] = original_key


def test_version_bumper_init_from_env():
    """Test VersionBumper reads API key from environment."""
    os.environ["OPENAI_API_KEY"] = "env-test-key"
    bumper = VersionBumper()
    assert bumper.api_key == "env-test-key"
    del os.environ["OPENAI_API_KEY"]


def test_get_last_version(temp_repo):
    """Test reading version from version.json."""
    bumper = VersionBumper(api_key="test-key")
    version = bumper.get_last_version()
    assert version == "1.0.0"


def test_get_last_version_fallback_to_changelog(temp_repo):
    """Test fallback to CHANGELOG.md when version.json doesn't exist."""
    os.remove("version.json")
    bumper = VersionBumper(api_key="test-key")
    version = bumper.get_last_version()
    assert version == "1.0.0"


def test_get_last_version_default(temp_repo):
    """Test default version when no files exist."""
    os.remove("version.json")
    os.remove("CHANGELOG.md")
    bumper = VersionBumper(api_key="test-key")
    version = bumper.get_last_version()
    assert version == "0.0.0"


def test_parse_conventional_commit_feature():
    """Test parsing conventional commit for feature."""
    bumper = VersionBumper(api_key="test-key")

    assert (
        bumper._parse_conventional_commit("feat: add new feature") == ChangeType.FEATURE
    )
    assert (
        bumper._parse_conventional_commit("feature: add new feature")
        == ChangeType.FEATURE
    )
    assert (
        bumper._parse_conventional_commit("feat(scope): add new feature")
        == ChangeType.FEATURE
    )


def test_parse_conventional_commit_fix():
    """Test parsing conventional commit for fix."""
    bumper = VersionBumper(api_key="test-key")

    assert bumper._parse_conventional_commit("fix: bug fix") == ChangeType.FIX
    assert bumper._parse_conventional_commit("fix(scope): bug fix") == ChangeType.FIX


def test_parse_conventional_commit_breaking():
    """Test parsing conventional commit for breaking change."""
    bumper = VersionBumper(api_key="test-key")

    assert (
        bumper._parse_conventional_commit("feat!: breaking change")
        == ChangeType.BREAKING
    )
    assert (
        bumper._parse_conventional_commit("fix!: breaking fix") == ChangeType.BREAKING
    )
    assert (
        bumper._parse_conventional_commit("feat: something\n\nBREAKING CHANGE: details")
        == ChangeType.BREAKING
    )


def test_parse_conventional_commit_other_types():
    """Test parsing conventional commit for other types."""
    bumper = VersionBumper(api_key="test-key")

    assert bumper._parse_conventional_commit("docs: update readme") == ChangeType.DOCS
    assert bumper._parse_conventional_commit("chore: update deps") == ChangeType.CHORE
    assert (
        bumper._parse_conventional_commit("refactor: clean code") == ChangeType.REFACTOR
    )
    assert bumper._parse_conventional_commit("test: add tests") == ChangeType.TEST
    assert bumper._parse_conventional_commit("perf: optimize") == ChangeType.PERF


def test_parse_conventional_commit_non_conventional():
    """Test parsing non-conventional commit returns None."""
    bumper = VersionBumper(api_key="test-key")

    assert bumper._parse_conventional_commit("some random commit") is None
    assert bumper._parse_conventional_commit("Update README") is None


def test_determine_version_bump_major():
    """Test determining major version bump."""
    bumper = VersionBumper(api_key="test-key")

    classifications = [
        ({"hash": "abc", "message": "feat: new"}, ChangeType.FEATURE),
        ({"hash": "def", "message": "fix: bug"}, ChangeType.FIX),
        ({"hash": "ghi", "message": "feat!: breaking"}, ChangeType.BREAKING),
    ]

    assert bumper.determine_version_bump(classifications) == "major"


def test_determine_version_bump_minor():
    """Test determining minor version bump."""
    bumper = VersionBumper(api_key="test-key")

    classifications = [
        ({"hash": "abc", "message": "feat: new"}, ChangeType.FEATURE),
        ({"hash": "def", "message": "fix: bug"}, ChangeType.FIX),
    ]

    assert bumper.determine_version_bump(classifications) == "minor"


def test_determine_version_bump_patch():
    """Test determining patch version bump."""
    bumper = VersionBumper(api_key="test-key")

    classifications = [
        ({"hash": "abc", "message": "fix: bug"}, ChangeType.FIX),
        ({"hash": "def", "message": "perf: optimize"}, ChangeType.PERF),
    ]

    assert bumper.determine_version_bump(classifications) == "patch"


def test_determine_version_bump_none():
    """Test determining no version bump needed."""
    bumper = VersionBumper(api_key="test-key")

    classifications = [
        ({"hash": "abc", "message": "docs: update"}, ChangeType.DOCS),
        ({"hash": "def", "message": "chore: cleanup"}, ChangeType.CHORE),
    ]

    assert bumper.determine_version_bump(classifications) == "none"


def test_bump_version_major():
    """Test bumping major version."""
    bumper = VersionBumper(api_key="test-key")

    assert bumper.bump_version("1.2.3", "major") == "2.0.0"
    assert bumper.bump_version("0.1.5", "major") == "1.0.0"


def test_bump_version_minor():
    """Test bumping minor version."""
    bumper = VersionBumper(api_key="test-key")

    assert bumper.bump_version("1.2.3", "minor") == "1.3.0"
    assert bumper.bump_version("0.1.5", "minor") == "0.2.0"


def test_bump_version_patch():
    """Test bumping patch version."""
    bumper = VersionBumper(api_key="test-key")

    assert bumper.bump_version("1.2.3", "patch") == "1.2.4"
    assert bumper.bump_version("0.1.5", "patch") == "0.1.6"


def test_bump_version_none():
    """Test no version bump."""
    bumper = VersionBumper(api_key="test-key")

    assert bumper.bump_version("1.2.3", "none") == "1.2.3"


def test_update_version_json(temp_repo):
    """Test updating version.json file."""
    bumper = VersionBumper(api_key="test-key")
    bumper.update_version_json("2.0.0")

    with open("version.json", "r") as f:
        data = json.load(f)

    assert data["version"] == "2.0.0"


def test_update_package_json(temp_repo):
    """Test updating package.json file."""
    bumper = VersionBumper(api_key="test-key")
    bumper.update_package_json("2.0.0")

    with open("package.json", "r") as f:
        data = json.load(f)

    assert data["version"] == "2.0.0"


def test_update_package_json_not_found(temp_repo):
    """Test updating package.json when file doesn't exist."""
    os.remove("package.json")
    bumper = VersionBumper(api_key="test-key")

    # Should not raise error
    bumper.update_package_json("2.0.0")


def test_update_changelog(temp_repo):
    """Test updating CHANGELOG.md."""
    bumper = VersionBumper(api_key="test-key")

    classifications = [
        ({"hash": "abc", "message": "feat: new feature"}, ChangeType.FEATURE),
        ({"hash": "def", "message": "fix: bug fix"}, ChangeType.FIX),
        ({"hash": "ghi", "message": "docs: update docs"}, ChangeType.DOCS),
    ]

    bumper.update_changelog("1.1.0", classifications)

    with open("CHANGELOG.md", "r") as f:
        content = f.read()

    assert "## [1.1.0]" in content
    assert "feat: new feature" in content
    assert "fix: bug fix" in content
    # docs should not appear in changelog (non-versioned change)


def test_classify_commit_conventional(temp_repo):
    """Test classifying a conventional commit without AI."""
    bumper = VersionBumper(api_key="test-key")

    commit = {
        "hash": "abc123",
        "message": "feat: add new feature",
        "diff": "some diff",
    }

    change_type = bumper.classify_commit(commit)
    assert change_type == ChangeType.FEATURE


@patch("version_ai_bumper.openai.OpenAI")
def test_classify_commit_with_ai(mock_openai, temp_repo):
    """Test classifying a commit using AI."""
    # Mock OpenAI response
    mock_client = Mock()
    mock_openai.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "FEATURE"
    mock_client.chat.completions.create.return_value = mock_response

    bumper = VersionBumper(api_key="test-key")
    bumper.client = mock_client

    commit = {
        "hash": "abc123",
        "message": "Add new dashboard component",
        "diff": "+++ dashboard.js\n@@ +10 lines",
    }

    change_type = bumper.classify_commit(commit)
    assert change_type == ChangeType.FEATURE
    assert mock_client.chat.completions.create.called


@patch("version_ai_bumper.openai.OpenAI")
def test_classify_commit_ai_fallback(mock_openai, temp_repo):
    """Test AI classification fallback to CHORE on error."""
    mock_client = Mock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API Error")

    bumper = VersionBumper(api_key="test-key")
    bumper.client = mock_client

    commit = {
        "hash": "abc123",
        "message": "Random commit message",
        "diff": "some diff",
    }

    change_type = bumper.classify_commit(commit)
    assert change_type == ChangeType.CHORE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
