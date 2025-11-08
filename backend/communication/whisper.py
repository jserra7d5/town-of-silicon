"""Whisper system for private communication between players."""
from loguru import logger
from ..models.game import GameState, ChatMessage, PhaseType
from ..models.player import Player


class WhisperManager:
    """
    Manages whisper (private message) system.

    Whispers are private messages between two players visible to both.
    """

    def __init__(self):
        self.whisper_history: list[ChatMessage] = []

    def send_whisper(
        self,
        game_state: GameState,
        from_player_id: int,
        to_player_id: int,
        message: str
    ) -> tuple[bool, str, ChatMessage | None]:
        """
        Send a whisper from one player to another.

        Args:
            game_state: Current game state
            from_player_id: Player sending whisper
            to_player_id: Player receiving whisper
            message: Whisper message content

        Returns:
            (success, error_message, whisper_message)
        """
        # Validate sender
        sender = self._get_player(game_state, from_player_id)
        if not sender:
            return False, "Sender not found", None

        if not sender.is_alive:
            return False, "Dead players cannot whisper", None

        if not sender.can_speak:
            return False, "You cannot speak", None

        if sender.is_blackmailed:
            return False, "You have been blackmailed!", None

        # Validate recipient
        recipient = self._get_player(game_state, to_player_id)
        if not recipient:
            return False, "Recipient not found", None

        if not recipient.is_alive:
            return False, "Cannot whisper to dead players", None

        # Validate phase (can only whisper during day)
        if game_state.current_phase.phase_type != PhaseType.DAY_DISCUSSION:
            return False, "Can only whisper during the day", None

        # Truncate message
        if len(message) > 200:
            message = message[:197] + "..."

        # Create whisper message
        whisper = ChatMessage(
            player_id=from_player_id,
            player_name=sender.name,
            message=message,
            phase=PhaseType.DAY_DISCUSSION.value,
            day_number=game_state.current_day,
            is_whisper=True,
            whisper_to=to_player_id
        )

        # Add to history
        self.whisper_history.append(whisper)
        game_state.all_chat_messages.append(whisper)

        logger.info(
            f"Whisper: {sender.name} -> {recipient.name}: {message[:50]}..."
        )

        return True, "OK", whisper

    def get_whispers_for_player(
        self,
        game_state: GameState,
        player_id: int
    ) -> list[ChatMessage]:
        """
        Get all whispers visible to a player.

        A player can see whispers they sent or received.

        Args:
            game_state: Current game state
            player_id: Player ID

        Returns:
            List of whisper messages
        """
        whispers = []

        for msg in game_state.all_chat_messages:
            if not msg.is_whisper:
                continue

            # Player can see whispers they sent or received
            if msg.player_id == player_id or msg.whisper_to == player_id:
                whispers.append(msg)

        return whispers

    def get_whispers_for_day(
        self,
        game_state: GameState,
        day_number: int
    ) -> list[ChatMessage]:
        """
        Get all whispers for a specific day.

        Args:
            game_state: Current game state
            day_number: Day number

        Returns:
            List of whisper messages
        """
        return [
            msg for msg in game_state.all_chat_messages
            if msg.is_whisper and msg.day_number == day_number
        ]

    def _get_player(self, game_state: GameState, player_id: int) -> Player | None:
        """Get player by ID."""
        return next(
            (p for p in game_state.players if p.player_id == player_id),
            None
        )
