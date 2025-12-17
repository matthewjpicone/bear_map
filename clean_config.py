#!/usr/bin/env python3
"""
Clean up old priority and efficiency fields from config.json
"""

import json
import os

def clean_config():
    config_path = 'config.json'
    if not os.path.exists(config_path):
        print("config.json not found")
        return

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Clean castles
    if 'castles' in config:
        for castle in config['castles']:
            # Remove old fields
            castle.pop('priority', None)
            castle.pop('efficiency', None)

    # Save back
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print("Cleaned config.json")

if __name__ == '__main__':
    clean_config()
