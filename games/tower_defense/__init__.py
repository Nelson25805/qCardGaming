# games/tower_defense/__init__.py
"""
Expose a Game class for discover_games().

Keep imports minimal here to avoid import-time errors.
"""
from .game import TowerDefenseGame

# The discoverer looks for attribute named "Game", or any class name ending with "Game".
# Expose a stable name 'Game' so main.py picks it up cleanly.
Game = TowerDefenseGame
