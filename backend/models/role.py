"""Role definitions and data models."""
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class FactionType(str, Enum):
    """Player factions."""
    TOWN = "Town"
    MAFIA = "Mafia"
    NEUTRAL = "Neutral"


class AttackValue(int, Enum):
    """Attack power levels."""
    NONE = 0
    BASIC = 1
    POWERFUL = 2
    UNSTOPPABLE = 3


class DefenseValue(int, Enum):
    """Defense power levels."""
    NONE = 0
    BASIC = 1
    POWERFUL = 2
    INVINCIBLE = 3


class RoleAbility(BaseModel):
    """Individual role ability."""
    name: str
    description: str
    action_type: str
    priority: int = Field(ge=0, le=10)
    max_uses: int | None = None  # None = unlimited
    cooldown_nights: int = 0
    targets_required: int = 1


class Role(BaseModel):
    """Complete role definition."""
    id: str
    name: str
    faction: FactionType
    category: str  # e.g., "Town Investigative"
    alignment: str  # e.g., "Town Investigative"

    # Combat stats
    attack: AttackValue = AttackValue.NONE
    defense: DefenseValue = DefenseValue.NONE

    # Properties
    unique: bool = False  # Only one per game
    abilities: list[RoleAbility] = []
    immunities: list[str] = []  # e.g., ["roleblock", "detection"]

    # Description
    summary: str
    goal: str


class RoleConstraint(BaseModel):
    """Constraint for role list slot."""
    type: Literal["specific", "category", "faction", "any"]
    value: str  # Role name, category name, or "any"


class RoleSlot(BaseModel):
    """Single slot in role list."""
    position: int = Field(ge=1, le=15)
    constraint: RoleConstraint


class RoleList(BaseModel):
    """Complete role list template."""
    name: str
    description: str
    slots: list[RoleSlot] = Field(min_length=15, max_length=15)

    def validate_slot_count(self) -> bool:
        """Ensure exactly 15 slots."""
        return len(self.slots) == 15
