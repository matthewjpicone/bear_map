#!/usr/bin/env python3
"""
AI-Powered Version Bumper Script

Analyzes commit history since the last version update and uses AI to classify
commit impacts, then determines the appropriate semantic version bump and updates
version files and CHANGELOG.md accordingly.

Usage:
    python version_ai_bumper.py [--dry-run] [--api-key KEY] [--model MODEL]

Environment Variables:
    OPENAI_API_KEY: OpenAI API key for commit classification

Author: Matthew Picone
Date: 2025-12-18
"""

import os
import sys
import json
import re
import argparse
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from enum import Enum

try:
    import openai
except ImportError:
    print("Error: openai package not installed. Install with: pip install openai")
    sys.exit(1)


class ChangeType(Enum):
    """Types of changes that can be classified from commits."""

    BREAKING = "breaking"
    FEATURE = "feature"
    FIX = "fix"
    CHORE = "chore"
    DOCS = "docs"
    REFACTOR = "refactor"
    TEST = "test"
    PERF = "perf"


class VersionBumper:
    """Handles AI-powered version bumping based on commit analysis."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize the version bumper.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            model: OpenAI model to use for classification.

        Raises:
            ValueError: If API key is not provided or found in environment.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment "
                "variable or pass --api-key argument."
            )

        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)

    def get_last_version(self) -> str:
        """Get the last version from version.json.

        Returns:
            Version string (e.g., "1.0.4").

        Raises:
            FileNotFoundError: If version.json doesn't exist.
            json.JSONDecodeError: If version.json is invalid.
        """
        try:
            with open("version.json", "r") as f:
                data = json.load(f)
                return data["version"]
        except FileNotFoundError:
            print("Warning: version.json not found. Trying CHANGELOG.md...")
            return self._get_version_from_changelog()

    def _get_version_from_changelog(self) -> str:
        """Extract last version from CHANGELOG.md as fallback.

        Returns:
            Version string or "0.0.0" if not found.
        """
        try:
            with open("CHANGELOG.md", "r") as f:
                content = f.read()
                # Look for version pattern like [1.0.4]
                match = re.search(r"\[(\d+\.\d+\.\d+)\]", content)
                if match:
                    return match.group(1)
        except FileNotFoundError:
            pass
        return "0.0.0"

    def get_commits_since_version(self, version: str) -> List[Dict[str, str]]:
        """Get all commits since the last version tag or update.

        Args:
            version: Version to get commits since.

        Returns:
            List of commit dictionaries with keys: hash, message, diff.
        """
        commits = []

        # Try to find version tag
        tag = f"v{version}"
        try:
            # Check if tag exists
            subprocess.run(
                ["git", "rev-parse", tag],
                check=True,
                capture_output=True,
                text=True,
            )
            # Get commits since tag
            result = subprocess.run(
                ["git", "log", f"{tag}..HEAD", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            # Tag doesn't exist, search for version.json or CHANGELOG.md changes
            print(f"Tag {tag} not found, searching for version update commits...")
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--all",
                    "--oneline",
                    "--",
                    "version.json",
                    "CHANGELOG.md",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Get the most recent version update commit
            lines = result.stdout.strip().split("\n")
            if lines and lines[0]:
                last_commit = lines[0].split()[0]
                # Get commits since that commit
                result = subprocess.run(
                    ["git", "log", f"{last_commit}..HEAD", "--oneline"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

        # Parse commit log
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue

            commit_hash = parts[0]
            commit_msg = parts[1]

            # Get diff for this commit
            diff_result = subprocess.run(
                ["git", "show", commit_hash, "--stat"],
                capture_output=True,
                text=True,
            )

            commits.append(
                {
                    "hash": commit_hash,
                    "message": commit_msg,
                    "diff": diff_result.stdout,
                }
            )

        return commits

    def classify_commit(self, commit: Dict[str, str]) -> ChangeType:
        """Use AI to classify a commit's impact.

        Args:
            commit: Dictionary with commit hash, message, and diff.

        Returns:
            ChangeType enum indicating the type of change.
        """
        # First, try conventional commit parsing
        conventional_type = self._parse_conventional_commit(commit["message"])
        if conventional_type:
            return conventional_type

        # Use AI for classification
        # Limit diff to first 1000 chars
        diff_summary = commit["diff"][:1000]
        prompt = f"""Analyze this git commit and classify its impact on semantic versioning.

Commit message: {commit['message']}

Diff summary:
{diff_summary}

Classify this commit as one of:
- BREAKING: Breaking changes that require a major version bump
- FEATURE: New features that require a minor version bump
- FIX: Bug fixes that require a patch version bump
- CHORE: Maintenance tasks (no version bump)
- DOCS: Documentation changes (no version bump)
- REFACTOR: Code refactoring (no version bump)
- TEST: Test changes (no version bump)
- PERF: Performance improvements (patch bump)

Respond with ONLY the classification word (e.g., "BREAKING", "FEATURE", etc.)
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a semantic versioning expert analyzing git commits.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=50,
            )

            classification = response.choices[0].message.content.strip().upper()

            # Map to ChangeType
            type_map = {
                "BREAKING": ChangeType.BREAKING,
                "FEATURE": ChangeType.FEATURE,
                "FIX": ChangeType.FIX,
                "CHORE": ChangeType.CHORE,
                "DOCS": ChangeType.DOCS,
                "REFACTOR": ChangeType.REFACTOR,
                "TEST": ChangeType.TEST,
                "PERF": ChangeType.PERF,
            }

            return type_map.get(classification, ChangeType.CHORE)

        except Exception as e:
            print(f"Warning: AI classification failed for commit {commit['hash']}: {e}")
            print("Falling back to CHORE classification")
            return ChangeType.CHORE

    def _parse_conventional_commit(self, message: str) -> Optional[ChangeType]:
        """Parse conventional commit format to determine type.

        Args:
            message: Commit message to parse.

        Returns:
            ChangeType if conventional format detected, None otherwise.
        """
        # Check for BREAKING CHANGE in message
        if "BREAKING CHANGE" in message or "!" in message.split(":")[0]:
            return ChangeType.BREAKING

        # Parse conventional commit prefix
        match = re.match(r"^(\w+)(\(.+\))?!?:", message)
        if match:
            commit_type = match.group(1).lower()
            type_map = {
                "feat": ChangeType.FEATURE,
                "feature": ChangeType.FEATURE,
                "fix": ChangeType.FIX,
                "docs": ChangeType.DOCS,
                "chore": ChangeType.CHORE,
                "refactor": ChangeType.REFACTOR,
                "test": ChangeType.TEST,
                "perf": ChangeType.PERF,
            }
            return type_map.get(commit_type)

        return None

    def determine_version_bump(
        self, classifications: List[Tuple[Dict[str, str], ChangeType]]
    ) -> str:
        """Determine semantic version bump type from commit classifications.

        Args:
            classifications: List of (commit, ChangeType) tuples.

        Returns:
            Bump type: "major", "minor", or "patch".
        """
        has_breaking = any(ct == ChangeType.BREAKING for _, ct in classifications)
        has_feature = any(ct == ChangeType.FEATURE for _, ct in classifications)
        has_fix = any(
            ct in [ChangeType.FIX, ChangeType.PERF] for _, ct in classifications
        )

        if has_breaking:
            return "major"
        elif has_feature:
            return "minor"
        elif has_fix:
            return "patch"
        else:
            # Only chores, docs, refactors, tests - no version bump needed
            return "none"

    def bump_version(self, current: str, bump_type: str) -> str:
        """Calculate new version based on bump type.

        Args:
            current: Current version string (e.g., "1.0.4").
            bump_type: Type of bump ("major", "minor", "patch", or "none").

        Returns:
            New version string.
        """
        if bump_type == "none":
            return current

        parts = current.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "patch":
            patch += 1

        return f"{major}.{minor}.{patch}"

    def update_version_json(self, new_version: str) -> None:
        """Update version.json with new version.

        Args:
            new_version: New version string.
        """
        with open("version.json", "r") as f:
            data = json.load(f)

        data["version"] = new_version

        with open("version.json", "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")  # Add trailing newline

    def update_package_json(self, new_version: str) -> None:
        """Update package.json with new version.

        Args:
            new_version: New version string.
        """
        try:
            with open("package.json", "r") as f:
                data = json.load(f)

            data["version"] = new_version

            with open("package.json", "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")  # Add trailing newline
        except FileNotFoundError:
            print("Warning: package.json not found, skipping update")

    def update_changelog(
        self,
        new_version: str,
        classifications: List[Tuple[Dict[str, str], ChangeType]],
    ) -> None:
        """Update CHANGELOG.md with new version and changes.

        Args:
            new_version: New version string.
            classifications: List of (commit, ChangeType) tuples.
        """
        try:
            with open("CHANGELOG.md", "r") as f:
                content = f.read()
        except FileNotFoundError:
            content = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

"""

        # Group commits by type
        grouped = {
            "Breaking Changes": [],
            "Added": [],
            "Fixed": [],
            "Changed": [],
            "Performance": [],
        }

        for commit, change_type in classifications:
            msg = commit["message"]
            if change_type == ChangeType.BREAKING:
                grouped["Breaking Changes"].append(msg)
            elif change_type == ChangeType.FEATURE:
                grouped["Added"].append(msg)
            elif change_type == ChangeType.FIX:
                grouped["Fixed"].append(msg)
            elif change_type == ChangeType.PERF:
                grouped["Performance"].append(msg)
            elif change_type in [ChangeType.REFACTOR, ChangeType.CHORE]:
                grouped["Changed"].append(msg)

        # Build new entry
        today = datetime.now().strftime("%Y-%m-%d")
        new_entry = f"\n## [{new_version}] - {today}\n\n"

        for section, commits in grouped.items():
            if commits:
                new_entry += f"### {section}\n\n"
                for commit in commits:
                    new_entry += f"- {commit}\n"
                new_entry += "\n"

        # Insert after header (find first ## or insert after intro)
        lines = content.split("\n")
        insert_index = 0

        for i, line in enumerate(lines):
            if line.startswith("## ["):
                insert_index = i
                break
            elif i > 0 and line.strip() == "" and i < len(lines) - 1:
                # Found blank line after header, insert here
                insert_index = i + 1

        if insert_index > 0:
            lines.insert(insert_index, new_entry.rstrip())
            content = "\n".join(lines)
        else:
            content += new_entry

        with open("CHANGELOG.md", "w") as f:
            f.write(content)

    def run(self, dry_run: bool = False) -> None:
        """Run the version bumping process.

        Args:
            dry_run: If True, only print what would be done without making changes.
        """
        print("🔍 AI-Powered Version Bumper")
        print("=" * 50)

        # Get current version
        current_version = self.get_last_version()
        print(f"Current version: {current_version}")

        # Get commits since last version
        print("\n📝 Analyzing commits...")
        commits = self.get_commits_since_version(current_version)

        if not commits:
            print("No commits found since last version. Nothing to bump!")
            return

        print(f"Found {len(commits)} commits to analyze")

        # Classify commits
        print("\n🤖 Classifying commits with AI...")
        classifications = []
        for i, commit in enumerate(commits, 1):
            print(
                f"  [{i}/{len(commits)}] {commit['hash'][:7]}: {commit['message'][:60]}..."
            )
            change_type = self.classify_commit(commit)
            classifications.append((commit, change_type))
            print(f"    → {change_type.value}")

        # Determine version bump
        bump_type = self.determine_version_bump(classifications)
        print(f"\n📊 Version bump type: {bump_type.upper()}")

        if bump_type == "none":
            print("No version bump needed (only non-versioned changes)")
            return

        new_version = self.bump_version(current_version, bump_type)
        print(f"New version: {current_version} → {new_version}")

        if dry_run:
            print("\n🔍 DRY RUN - No files will be modified")
            print("\nWould update:")
            print("  - version.json")
            print("  - package.json")
            print("  - CHANGELOG.md")
            print("\nChangelog entry preview:")
            print("-" * 50)
            # Create a temporary changelog to show preview
            temp_classifications = classifications
            grouped = {
                "Breaking Changes": [],
                "Added": [],
                "Fixed": [],
                "Changed": [],
                "Performance": [],
            }
            for commit, change_type in temp_classifications:
                msg = commit["message"]
                if change_type == ChangeType.BREAKING:
                    grouped["Breaking Changes"].append(msg)
                elif change_type == ChangeType.FEATURE:
                    grouped["Added"].append(msg)
                elif change_type == ChangeType.FIX:
                    grouped["Fixed"].append(msg)
                elif change_type == ChangeType.PERF:
                    grouped["Performance"].append(msg)
                elif change_type in [ChangeType.REFACTOR, ChangeType.CHORE]:
                    grouped["Changed"].append(msg)

            today = datetime.now().strftime("%Y-%m-%d")
            print(f"\n## [{new_version}] - {today}\n")
            for section, commits_list in grouped.items():
                if commits_list:
                    print(f"### {section}\n")
                    for commit in commits_list:
                        print(f"- {commit}")
                    print()
            print("-" * 50)
            return

        # Update files
        print("\n✍️  Updating files...")
        self.update_version_json(new_version)
        print("  ✓ Updated version.json")

        self.update_package_json(new_version)
        print("  ✓ Updated package.json")

        self.update_changelog(new_version, classifications)
        print("  ✓ Updated CHANGELOG.md")

        print(f"\n✅ Version bumped successfully: {current_version} → {new_version}")
        print("\nNext steps:")
        print("  1. Review the changes: git diff")
        print(
            f"  2. Commit the changes: git add -A && git commit -m 'chore(release): {new_version}'"
        )
        print(
            f"  3. Create a tag: git tag -a v{new_version} -m 'Release v{new_version}'"
        )
        print("  4. Push changes: git push && git push --tags")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="AI-powered version bumper for semantic versioning"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--api-key",
        help="OpenAI API key (can also use OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)",
    )

    args = parser.parse_args()

    try:
        bumper = VersionBumper(api_key=args.api_key, model=args.model)
        bumper.run(dry_run=args.dry_run)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
