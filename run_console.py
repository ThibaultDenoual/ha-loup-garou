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


def suggest_preset(n: int) -> str:
    """Suggest a preset based on player count."""
    if n <= 6:
        return "small"
    if n <= 9:
        return "medium"
    if n <= 13:
        return "large"
    return "chaos"


def print_presets():
    """Print available presets."""
    print("\nAvailable presets:")
    for name, roles in PRESETS.items():
        print(f"  {name}: {len(roles)} roles - {roles}")


def get_role_names(n: int) -> list[str]:
    """Get role names from user (with preset suggestions)."""
    suggested = suggest_preset(n)
    print_presets()
    print(f"\nSuggested preset for {n} players: {suggested}")
    print(f"  → {PRESETS[suggested]}")

    while True:
        choice = input("\nUse preset or customize? (preset name/custom): ").strip().lower()
        if choice in PRESETS:
            role_names = PRESETS[choice][:]
            if len(role_names) != n:
                print(f"Warning: '{choice}' preset has {len(role_names)} roles but you have {n} players.")
                if input("Adjust to match player count? (y/n): ").strip().lower() != 'y':
                    continue
                role_names = _adjust_roles(role_names, n)
            break
        elif choice == "custom":
            role_names = _get_custom_roles(n)
            break
        else:
            print(f"Invalid choice. Enter a preset name or 'custom'.")

    print(f"\nFinal roles: {role_names}")
    return role_names


def _adjust_roles(roles: list[str], target: int) -> list[str]:
    """Adjust role list to match target count by adding/removing Villagers."""
    while len(roles) < target:
        roles.append("Villager")
    while len(roles) > target:
        if "Villager" in roles:
            roles.remove("Villager")
        else:
            roles.pop()
    return roles


def _get_custom_roles(n: int) -> list[str]:
    """Get custom role configuration from user."""
    print("\nEnter roles (comma-separated) or press Enter for default villagers:")
    print(f"Available roles: Werewolf, Seer, Doctor, Hunter, Witch, Bodyguard, "
          "Cupid, Alpha Wolf, Minion, Serial Killer, Jester, Villager")

    while True:
        roles_input = input(f"Enter {n} roles (comma-separated): ").strip()
        if not roles_input:
            return ["Villager"] * n

        role_names = [r.strip() for r in roles_input.split(",")]

        if len(role_names) != n:
            print(f"Need exactly {n} roles, got {len(role_names)}. Try again.")
            continue

        invalid = [r for r in role_names if r not in PRESETS.get("chaos")]
        if invalid:
            print(f"Unknown roles: {invalid}. Try again.")
            continue

        return role_names


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

    role_names = get_role_names(n)

    print("\n" + "=" * 40)
    print("Player names:")
    names = []
    while len(names) < n:
        name = input(f"Player {len(names)+1} name: ").strip()
        if name:
            names.append(name)

    if len(names) < 4:
        print("Need at least 4 players!")
        sys.exit(1)

    engine = GameEngine(player_names=names, role_names=role_names)
    engine.run()


if __name__ == "__main__":
    main()