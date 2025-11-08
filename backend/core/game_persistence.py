"""Game state persistence for saving and loading games."""
import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
from loguru import logger
from pydantic import BaseModel

from ..models.game import GameState


class GameSaveMetadata(BaseModel):
    """Metadata about a saved game."""
    game_id: str
    save_time: datetime
    current_day: int
    current_phase: str
    alive_players: int
    total_players: int


class GamePersistence:
    """
    Handles saving and loading game states to/from disk.

    Saves are stored as JSON files in the saves directory.
    """

    def __init__(self, saves_dir: str = "saves"):
        """
        Initialize game persistence.

        Args:
            saves_dir: Directory to store save files
        """
        self.saves_dir = Path(saves_dir)
        self.saves_dir.mkdir(exist_ok=True)
        logger.info(f"Game persistence initialized: {self.saves_dir.absolute()}")

    def save_game(self, game_state: GameState, save_name: Optional[str] = None) -> str:
        """
        Save game state to disk.

        Args:
            game_state: Current game state to save
            save_name: Optional name for the save (defaults to timestamp)

        Returns:
            Path to saved file
        """
        if save_name is None:
            save_name = f"save_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Ensure safe filename
        safe_name = "".join(c for c in save_name if c.isalnum() or c in "._- ")
        save_path = self.saves_dir / f"{safe_name}.json"

        try:
            # Convert game state to JSON
            game_data = game_state.model_dump(mode='json')

            # Add metadata
            save_data = {
                "metadata": {
                    "game_id": game_state.game_id,
                    "save_time": datetime.now().isoformat(),
                    "current_day": game_state.current_day,
                    "current_phase": game_state.current_phase.phase_type.value,
                    "alive_players": len([p for p in game_state.players if p.is_alive]),
                    "total_players": len(game_state.players)
                },
                "game_state": game_data
            }

            # Write to file
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, default=str)

            logger.success(f"Game saved to: {save_path}")
            return str(save_path)

        except Exception as e:
            logger.error(f"Error saving game: {e}")
            raise

    def load_game(self, save_name: str) -> GameState:
        """
        Load game state from disk.

        Args:
            save_name: Name of save file (with or without .json extension)

        Returns:
            Loaded game state
        """
        # Handle both with and without .json extension
        if not save_name.endswith('.json'):
            save_name += '.json'

        save_path = self.saves_dir / save_name

        if not save_path.exists():
            raise FileNotFoundError(f"Save file not found: {save_path}")

        try:
            # Read from file
            with open(save_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)

            # Extract game state
            game_data = save_data.get("game_state")
            if not game_data:
                raise ValueError("Invalid save file: missing game_state")

            # Reconstruct game state
            game_state = GameState(**game_data)

            metadata = save_data.get("metadata", {})
            logger.success(
                f"Game loaded from: {save_path} "
                f"(Day {metadata.get('current_day')}, {metadata.get('current_phase')})"
            )

            return game_state

        except Exception as e:
            logger.error(f"Error loading game: {e}")
            raise

    def list_saves(self) -> list[GameSaveMetadata]:
        """
        List all available save files.

        Returns:
            List of save metadata
        """
        saves = []

        for save_file in self.saves_dir.glob("*.json"):
            try:
                with open(save_file, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)

                metadata = save_data.get("metadata", {})
                saves.append(GameSaveMetadata(
                    game_id=metadata.get("game_id", "unknown"),
                    save_time=datetime.fromisoformat(metadata.get("save_time", datetime.now().isoformat())),
                    current_day=metadata.get("current_day", 0),
                    current_phase=metadata.get("current_phase", "unknown"),
                    alive_players=metadata.get("alive_players", 0),
                    total_players=metadata.get("total_players", 0)
                ))

            except Exception as e:
                logger.warning(f"Error reading save file {save_file}: {e}")
                continue

        # Sort by save time (newest first)
        saves.sort(key=lambda s: s.save_time, reverse=True)

        return saves

    def delete_save(self, save_name: str) -> bool:
        """
        Delete a save file.

        Args:
            save_name: Name of save file to delete

        Returns:
            True if deleted successfully
        """
        if not save_name.endswith('.json'):
            save_name += '.json'

        save_path = self.saves_dir / save_name

        if not save_path.exists():
            logger.warning(f"Save file not found: {save_path}")
            return False

        try:
            save_path.unlink()
            logger.info(f"Deleted save file: {save_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting save file: {e}")
            return False

    def autosave(self, game_state: GameState) -> str:
        """
        Create an autosave.

        Args:
            game_state: Current game state

        Returns:
            Path to autosave file
        """
        return self.save_game(game_state, save_name="autosave")
