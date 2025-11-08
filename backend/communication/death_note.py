"""Death note system for killers to leave messages on victims."""
from loguru import logger
from ..models.game import GameState
from ..models.player import Player, DeathInfo


class DeathNoteManager:
    """
    Manages death notes for killing roles.

    Certain roles (Serial Killer, Mafia, etc.) can leave death notes
    on their victims.
    """

    def __init__(self):
        # Map of player_id -> current death note text
        self.active_death_notes: dict[int, str] = {}

    def update_death_note(
        self,
        game_state: GameState,
        player_id: int,
        note_text: str
    ) -> tuple[bool, str]:
        """
        Update a player's death note.

        Args:
            game_state: Current game state
            player_id: Player updating their death note
            note_text: New death note content

        Returns:
            (success, error_message)
        """
        player = self._get_player(game_state, player_id)
        if not player:
            return False, "Player not found"

        if not player.is_alive:
            return False, "Dead players cannot set death notes"

        # Check if player can use death notes
        if not self.can_use_death_note(player):
            return False, "Your role cannot use death notes"

        # Truncate to 200 characters
        if len(note_text) > 200:
            note_text = note_text[:200]

        # Store death note
        self.active_death_notes[player_id] = note_text

        logger.info(f"Player {player_id} ({player.name}) updated their death note")

        return True, "Death note updated"

    def can_use_death_note(self, player: Player) -> bool:
        """
        Check if a player's role can use death notes.

        Args:
            player: Player to check

        Returns:
            True if player can use death notes
        """
        # Roles that can use death notes
        death_note_roles = [
            'serial_killer',
            'arsonist',
            'werewolf',
            'godfather',
            'mafioso',
        ]

        return player.role.id in death_note_roles

    def apply_death_note(
        self,
        killer_id: int,
        death_info: DeathInfo
    ) -> DeathInfo:
        """
        Apply the killer's death note to a death.

        Args:
            killer_id: Player who caused the death
            death_info: Death information to update

        Returns:
            Updated death info with death note
        """
        if killer_id in self.active_death_notes:
            note = self.active_death_notes[killer_id]
            death_info.death_note = note
            logger.info(f"Applied death note from player {killer_id}")

        return death_info

    def get_death_note(self, player_id: int) -> str:
        """
        Get a player's current death note.

        Args:
            player_id: Player ID

        Returns:
            Death note text (empty string if no note)
        """
        return self.active_death_notes.get(player_id, "")

    def clear_death_note(self, player_id: int):
        """
        Clear a player's death note.

        Args:
            player_id: Player ID
        """
        if player_id in self.active_death_notes:
            del self.active_death_notes[player_id]
            logger.debug(f"Cleared death note for player {player_id}")

    def reveal_death_note(self, death_info: DeathInfo) -> str | None:
        """
        Get the death note to display with a death.

        Args:
            death_info: Death information

        Returns:
            Death note to display, or None if no note
        """
        # Check if body was cleaned
        if death_info.cleaned:
            return None

        # Return death note if present
        if death_info.death_note and death_info.death_note.strip():
            return death_info.death_note

        return None

    def _get_player(self, game_state: GameState, player_id: int) -> Player | None:
        """Get player by ID."""
        return next(
            (p for p in game_state.players if p.player_id == player_id),
            None
        )
