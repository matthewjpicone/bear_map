#!/usr/bin/env python3
"""
Version updater script for CI/CD pipeline.

This script ensures the version.json file is kept in sync with the latest
git tag or semantic version, and that it's accessible to the API.

Author: Matthew Picone
Date: 2025-12-18
"""

import json
import subprocess
import sys
from pathlib import Path


def get_git_tag():
    """Get the latest git tag as version.

    Returns:
        Version string from latest git tag, or None if no tags exist.
    """
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip().lstrip("v")
        return None
    except Exception as e:
        print(f"Error getting git tag: {e}", file=sys.stderr)
        return None


def get_package_json_version():
    """Get version from package.json.

    Returns:
        Version string from package.json, or None if not found.
    """
    try:
        package_path = Path(__file__).parent.parent / "package.json"
        with open(package_path, "r") as f:
            data = json.load(f)
        return data.get("version")
    except Exception as e:
        print(f"Error reading package.json: {e}", file=sys.stderr)
        return None


def update_version_json(version):
    """Update version.json with the given version.

    Args:
        version: Version string to write.
    """
    try:
        version_file = Path(__file__).parent.parent / "version.json"
        with open(version_file, "w") as f:
            json.dump({"version": version}, f, indent=2)
        print(f"✅ Updated version.json to {version}")
    except Exception as e:
        print(f"❌ Error updating version.json: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for version update script."""
    # Try git tag first (from semantic-release)
    version = get_git_tag()

    # Fall back to package.json
    if not version:
        version = get_package_json_version()

    # Default fallback
    if not version:
        version = "1.0.0"
        print(f"⚠️  No version found, using default: {version}")

    # Update version.json
    update_version_json(version)
    print(f"🚀 Version set to: {version}")


if __name__ == "__main__":
    main()

