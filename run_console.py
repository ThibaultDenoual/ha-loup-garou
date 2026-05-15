#!/usr/bin/env python3
"""
Console runner for Loup Garou (Werewolf) game.
Run with: python run_console.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "custom_components"))

from custom_components.loup_garou.core_game.engine import GameEngine
from custom_components.loup_garou.core_game.roles import PRESETS


def main():
    print("🐺 Loup Garou - Console Mode 🐺\n")

    while True:
        try:
            n = int(input("Number of players (4-18): ").strip())
            if 4 <= n <= 18:
                break
            print("Please enter a number between 4 and 18.")
        except ValueError:
            print("Please enter a valid number.")

    preset = None
    if 4 <= n <= 6:
        preset = "small"
    elif 7 <= n <= 9:
        preset = "medium"
    elif 10 <= n <= 13:
        preset = "large"
    else:
        preset = "chaos"

    print(f"\nUsing preset: {preset}")
    print(f"Roles: {PRESETS[preset]}\n")

    names = []
    for i in range(n):
        name = input(f"Player {i+1} name: ").strip()
        if name:
            names.append(name)

    if len(names) < 4:
        print("Need at least 4 players!")
        sys.exit(1)

    engine = GameEngine(player_names=names, preset=preset)
    engine.run()


if __name__ == "__main__":
    main()