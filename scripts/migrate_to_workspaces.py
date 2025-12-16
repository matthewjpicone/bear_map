#!/usr/bin/env python3
"""Migration script to convert config.json to workspace-based structure.

This script transforms the existing config.json into a workspace-aware format
with support for per-workspace whitelists and entity ownership.
"""

import json
import os
import sys
from datetime import datetime


def migrate_config(config_path: str, backup: bool = True):
    """Migrate config.json to workspace-based structure.

    Args:
        config_path: Path to config.json.
        backup: Whether to create a backup before migration.
    """
    print(f"Starting migration of {config_path}...")

    # Load existing config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {e}")
        sys.exit(1)

    # Check if already migrated
    if "workspaces" in config:
        print("Config already appears to be migrated (has 'workspaces' key)")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != "y":
            print("Migration cancelled")
            return

    # Create backup
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{config_path}.backup_{timestamp}"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"Backup created at {backup_path}")

    # Create default workspace from existing data
    default_workspace_id = "default"
    default_workspace = {
        "name": "Default Workspace",
        "description": "Default workspace (legacy data)",
        "whitelist": [],  # Empty = open to all (backward compatible)
        "created_at": datetime.now().isoformat(),
    }

    # Add workspace_id to all entities
    for entity_type in ["castles", "bear_traps", "banners"]:
        if entity_type in config:
            for entity in config[entity_type]:
                entity["workspace_id"] = default_workspace_id

    # Create workspaces structure
    config["workspaces"] = {default_workspace_id: default_workspace}

    # Add global settings if not present
    if "global_settings" not in config:
        config["global_settings"] = {
            "auth_enabled": False,  # Start disabled for backward compatibility
            "allow_anonymous": True,  # Allow unauthenticated access initially
        }

    # Save migrated config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("Migration completed successfully!")
    print(f"  - Created default workspace: '{default_workspace_id}'")
    print(f"  - Added workspace_id to all entities")
    print(
        f"  - Set auth_enabled=False for backward compatibility"
    )
    print("\nTo enable authentication:")
    print("  1. Set auth_enabled=true in global_settings")
    print("  2. Configure Discord OAuth (DISCORD_CLIENT_ID, etc.)")
    print("  3. Add Discord user IDs to workspace whitelists")


def main():
    """Main entry point for migration script."""
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # Default to config.json in parent directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(
            os.path.dirname(script_dir), "config.json"
        )

    migrate_config(config_path)


if __name__ == "__main__":
    main()
