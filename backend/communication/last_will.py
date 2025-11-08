"""Last will system for players to leave messages after death."""
from loguru import logger
from ..models.game import GameState
from ..models.player import Player


class LastWillManager:
    """
    Manages last wills for players.

    Players can write and update their will during the game.
    Will is revealed when they die.
    """

    def update_will(
        self,
        game_state: GameState,
        player_id: int,
        will_text: str
    ) -> tuple[bool, str]:
        """
        Update a player's last will.

        Args:
            game_state: Current game state
            player_id: Player updating their will
            will_text: New will content

        Returns:
            (success, error_message)
        """
        player = self._get_player(game_state, player_id)
        if not player:
            return False, "Player not found"

        if not player.is_alive:
            return False, "Dead players cannot update their will"

        # Truncate to 200 characters
        if len(will_text) > 200:
            will_text = will_text[:200]

        # Update will
        player.last_will = will_text

        logger.info(f"Player {player_id} ({player.name}) updated their will")

        return True, "Will updated"

    def get_will(
        self,
        game_state: GameState,
        player_id: int
    ) -> str:
        """
        Get a player's last will.

        Args:
            game_state: Current game state
            player_id: Player ID

        Returns:
            Last will text (empty string if no will)
        """
        player = self._get_player(game_state, player_id)
        if not player:
            return ""

        return player.last_will

    def reveal_will(
        self,
        game_state: GameState,
        player_id: int
    ) -> str:
        """
        Reveal a dead player's will.

        This is called when a player dies to show their will to everyone.

        Args:
            game_state: Current game state
            player_id: Dead player's ID

        Returns:
            Will text to display
        """
        player = self._get_player(game_state, player_id)
        if not player:
            return "(No will found)"

        if player.is_alive:
            logger.warning(f"Attempted to reveal will of living player {player_id}")
            return "(Player is still alive)"

        # Check if body was cleaned by Janitor
        if player.death_info and player.death_info.cleaned:
            return "(Body was cleaned - will destroyed)"

        will = player.last_will
        if not will or will.strip() == "":
            return f"{player.name} did not leave a will."

        return f"{player.name}'s Last Will:\n{will}"

    def _get_player(self, game_state: GameState, player_id: int) -> Player | None:
        """Get player by ID."""
        return next(
            (p for p in game_state.players if p.player_id == player_id),
            None
        )
