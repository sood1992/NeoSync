#!/usr/bin/env python3
"""
Generate and export all 500 NeoSync license keys
"""

import random
import string


def generate_license_keys():
    """Generate the 500 valid license keys"""
    random.seed("NeoSync_NeoFox_2024_License_Keys")

    keys = []
    chars = string.ascii_uppercase + string.digits
    prefixes = ["NEOS", "NEOFOX", "TEAM"]

    for i in range(500):
        prefix = prefixes[i % 3]
        parts = [prefix]

        for _ in range(4):
            part = ''.join(random.choices(chars, k=4))
            parts.append(part)

        key = '-'.join(parts)
        keys.append(key)

    return keys


def main():
    keys = generate_license_keys()

    print("=" * 60)
    print("NeoSync License Keys")
    print("=" * 60)
    print()
    print(f"Total keys: {len(keys)}")
    print()
    print("NEOS-xxxx keys (Pro - 500 clips):", sum(1 for k in keys if k.startswith("NEOS-")))
    print("NEOFOX-xxxx keys (Team - 1000 clips):", sum(1 for k in keys if k.startswith("NEOFOX-")))
    print("TEAM-xxxx keys (Enterprise - unlimited):", sum(1 for k in keys if k.startswith("TEAM-")))
    print()
    print("=" * 60)
    print("All Keys:")
    print("=" * 60)
    print()

    for i, key in enumerate(keys, 1):
        print(f"{i:3d}. {key}")

    # Save to file
    with open("license_keys.txt", "w") as f:
        f.write("NeoSync License Keys\n")
        f.write("=" * 60 + "\n\n")
        for i, key in enumerate(keys, 1):
            f.write(f"{i:3d}. {key}\n")

    print()
    print(f"Keys saved to license_keys.txt")


if __name__ == "__main__":
    main()
