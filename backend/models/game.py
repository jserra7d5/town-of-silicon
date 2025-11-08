"""Game state models."""
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
from enum import Enum
from .player import Player, DeathInfo


class PhaseType(str, Enum):
    """Game phase types."""
    PREGAME = "pregame"
    NIGHT = "night"
    DAY_DISCUSSION = "day_discussion"
    DEFENSE = "defense"
    JUDGMENT = "judgment"
    JUDGMENT_RESULTS = "judgment_results"
    LAST_WORDS = "last_words"
    POSTGAME = "postgame"


class GamePhase(BaseModel):
    """Current phase information."""
    phase_type: PhaseType
    phase_number: int
    start_time: datetime = Field(default_factory=datetime.now)
    duration: float  # seconds
    remaining_time: float
    extensions_used: int = 0
    max_extensions: int = 6


class ChatMessage(BaseModel):
    """A single chat message."""
    player_id: int
    player_name: str
    message: str = Field(max_length=200)
    phase: str
    day_number: int
    timestamp: datetime = Field(default_factory=datetime.now)
    is_whisper: bool = False
    whisper_to: int | None = None
    visible_to_dead: bool = False


class VoteRecord(BaseModel):
    """Vote during trial."""
    voter_id: int
    accused_id: int | None = None  # For accusation votes
    vote_type: Literal["accuse", "guilty", "innocent", "abstain"] | None = None
    day_number: int
    timestamp: datetime = Field(default_factory=datetime.now)


class NightActionRecord(BaseModel):
    """Record of a night action."""
    actor_id: int
    action_type: str
    target_id: int | None = None
    secondary_target_id: int | None = None
    night_number: int
    priority: int
    result: str | None = None
    was_successful: bool = False


class GameState(BaseModel):
    """Complete game state - with 64K context, we keep EVERYTHING!"""
    game_id: str = "main"  # Default game ID
    created_at: datetime = Field(default_factory=datetime.now)

    # Players
    players: list[Player] = []  # Will be populated during game creation

    # Phase tracking
    current_phase: GamePhase
    day_number: int = 0
    night_number: int = 0

    # Complete history (NO SUMMARIZATION with 64K context!)
    all_chat_messages: list[ChatMessage] = []
    all_votes: list[VoteRecord] = []
    all_night_actions: list[NightActionRecord] = []
    all_deaths: list[DeathInfo] = []

    # Current trial state
    accused_player_id: int | None = None
    votes_to_accuse: dict[int, list[int]] = {}  # accused_id: [voter_ids]
    last_judgment_result: dict | None = None  # Store as dict to avoid circular import

    # Game status
    is_game_over: bool = False
    winners: list[int] = []  # Player IDs who won
    victory_type: str | None = None

    def get_player(self, player_id: int) -> Player | None:
        """Get player by ID."""
        return next((p for p in self.players if p.player_id == player_id), None)

    def get_living_players(self) -> list[Player]:
        """Get all living players."""
        return [p for p in self.players if p.is_alive]

    def get_human_player(self) -> Player | None:
        """Get the human player."""
        return next((p for p in self.players if p.is_human), None)

    def get_chat_for_day(self, day: int) -> list[ChatMessage]:
        """Get all chat messages for a specific day."""
        return [msg for msg in self.all_chat_messages if msg.day_number == day]

    def get_deaths_for_night(self, night: int) -> list[DeathInfo]:
        """Get all deaths for a specific night."""
        return [d for d in self.all_deaths if d.night == night]
