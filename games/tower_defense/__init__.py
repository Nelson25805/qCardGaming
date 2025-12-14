"""
Tower defense game package entry.
Expose Game so the launcher can import it as a module and find the class.
"""

from .game import TowerDefenseGame as Game

__all__ = ["Game"]
