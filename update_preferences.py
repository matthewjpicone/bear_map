"""
Script to update bear preferences in config.json.

Rules:
- "Bear 1" -> "BT1"
- "Bear 2" -> "BT2"
- "Both" -> "BT1/2" if x < grid_size/2, else "BT2/1"
"""

import json

def update_preferences():
    """Update bear preferences based on rules."""
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    grid_size = config.get("grid_size", 28)
    midpoint = grid_size / 2  # 14 for grid_size=28

    castles = config.get("castles", [])
    updated_count = 0

    for castle in castles:
        old_pref = castle.get("preference", "")
        new_pref = old_pref
        x = castle.get("x")

        if old_pref == "Bear 1":
            new_pref = "BT1"
        elif old_pref == "Bear 2":
            new_pref = "BT2"
        elif old_pref == "Both" or old_pref.lower() == "both":
            # Use x position to determine BT1/2 or BT2/1
            if x is not None:
                if x < midpoint:
                    new_pref = "BT1/2"
                else:
                    new_pref = "BT2/1"
            else:
                # No x position, default to BT1/2
                new_pref = "BT1/2"

        if old_pref != new_pref:
            print(f"{castle.get('player', castle.get('id'))}: '{old_pref}' -> '{new_pref}' (x={x})")
            castle["preference"] = new_pref
            updated_count += 1

    # Save updated config
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"\nUpdated {updated_count} castle preferences.")

if __name__ == "__main__":
    update_preferences()

