"""Player data models."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from .role import Role, FactionType


class Player(BaseModel):
    """Individual player in the game."""
    player_id: int = Field(ge=1, le=15)
    name: str
    role: Role
    faction: FactionType
    is_human: bool = False
    is_alive: bool = True
    revealed: bool = False  # Mayor reveal, etc.

    # Communication
    last_will: str = Field(default="", max_length=200)
    is_blackmailed: bool = False
    can_speak: bool = True

    # State
    in_jail: bool = False
    on_trial: bool = False
    voted_today: bool = False

    # Role-specific states
    is_doused: bool = False  # Arsonist target
    is_vested: bool = False  # Survivor vest active
    is_alerted: bool = False  # Veteran alert active
    jailed_by: Optional[int] = None  # Player ID of Jailor (if jailed)

    # Death info (legacy fields for compatibility)
    death_night: int = 0
    death_day: int = 0
    death_cause: str | None = None
    death_info: Optional["DeathInfo"] = None  # Full death information

    # Ability tracking
    ability_uses_remaining: dict[str, int] = {}
    last_action_night: int = 0

    # Investigation results (for AI memory)
    investigation_results: list["InvestigationResult"] = []


class InvestigationResult(BaseModel):
    """Result of investigating a player."""
    night: int
    target_id: int
    target_name: str
    investigation_type: str  # "sheriff", "investigator", "lookout", "spy"
    result: str  # The actual result message


class PlayerRoleAssignment(BaseModel):
    """Role assignment for game initialization."""
    player_id: int
    role: Role
    faction: FactionType
    is_human: bool


class DeathInfo(BaseModel):
    """Information about a player's death."""
    player_id: int
    player_name: str = ""
    role: str = ""
    faction: str = ""
    night: int = 0
    day: int = 0
    day_number: int = 0  # Alias for day
    phase: str = "Unknown"
    cause: str
    killed_by: int | None = None
    killer_id: int | None = None  # Alias for killed_by
    last_will: str = ""
    death_note: str | None = None
    cleaned: bool = False  # Janitor
    role_revealed: str | None = None  # For display purposes
    timestamp: datetime = Field(default_factory=datetime.now)
