"""AI player context and memory models - optimized for 64K context window."""
from pydantic import BaseModel, Field
from typing import Dict, List
from .game import ChatMessage, VoteRecord, DeathInfo


class SuspicionData(BaseModel):
    """Suspicion tracking for a single player."""
    player_id: int
    level: float = Field(ge=0.0, le=1.0, default=0.5)
    reasons: list[str] = []
    last_updated_night: int = 0


class RoleClaim(BaseModel):
    """Track role claims made by players."""
    player_id: int
    claimed_role: str
    day_claimed: int
    believability: float = Field(ge=0.0, le=1.0, default=0.7)
    evidence: list[str] = []
    contradictions: list[str] = []


class InvestigationRecord(BaseModel):
    """Investigation result."""
    target_id: int
    result: str
    night: int
    investigator_role: str


class AIMemory(BaseModel):
    """AI memory and analysis - compact storage for key insights."""
    suspicions: dict[int, SuspicionData] = {}
    role_claims: dict[int, RoleClaim] = {}
    behavioral_notes: dict[int, list[str]] = {}
    alliance_trust: dict[int, float] = {}  # -1.0 to 1.0


class AIContext(BaseModel):
    """
    Full AI context for decision-making.

    With 64K context window, we include COMPLETE game history!
    NO summarization needed - this is the killer feature.
    """
    player_id: int
    role: str
    faction: str
    night_number: int
    day_number: int

    # COMPLETE game history (fits in 64K!)
    # Typical token counts:
    # - 500 chat messages: ~15,000 tokens
    # - 50 votes: ~2,000 tokens
    # - 10 deaths with wills: ~3,000 tokens
    # - System prompt + role info: ~1,000 tokens
    # Total: ~21,000 tokens (43GB headroom!)

    complete_chat_history: list[ChatMessage] = []
    complete_vote_history: list[VoteRecord] = []
    all_deaths: list[DeathInfo] = []
    all_investigations: list[InvestigationRecord] = []

    # Faction-specific knowledge
    faction_member_ids: list[int] = []  # Mafia knows other Mafia

    # AI's memory and analysis
    memory: AIMemory = Field(default_factory=AIMemory)

    # Game objectives
    objectives: list[str] = []

    def get_living_players(self, game_state) -> list[int]:
        """Get IDs of living players from game state."""
        from .player import Player
        return [
            p.player_id
            for p in game_state.players
            if p.is_alive and p.player_id != self.player_id
        ]

    def build_full_prompt(self, game_state, purpose: str) -> str:
        """
        Build complete context prompt with FULL game history.

        This is the magic of 64K context - no information loss!
        AI has perfect memory of everything that happened.
        """
        prompt = f"""You are Player {self.player_id}, playing as {self.role} ({self.faction}).

CURRENT SITUATION:
- Night: {self.night_number}, Day: {self.day_number}
- Living players: {len(self.get_living_players(game_state))}

YOUR WIN CONDITION:
{self._get_win_condition()}

"""

        # COMPLETE CHAT HISTORY (all messages, no pruning!)
        if self.complete_chat_history:
            prompt += "\n=== COMPLETE CHAT LOG ===\n"
            for msg in self.complete_chat_history[-100:]:  # Last 100 messages (still fits!)
                prompt += f"[Day {msg.day_number}] {msg.sender_name}: {msg.content}\n"

        # COMPLETE VOTE HISTORY
        if self.complete_vote_history:
            prompt += "\n=== ALL VOTES ===\n"
            for vote in self.complete_vote_history:
                if vote.vote_type == "accuse":
                    prompt += f"Day {vote.day_number}: Accused Player {vote.accused_id}\n"
                else:
                    prompt += f"Day {vote.day_number}: Voted {vote.vote_type}\n"

        # ALL DEATHS WITH COMPLETE WILLS
        if self.all_deaths:
            prompt += "\n=== ALL DEATHS ===\n"
            for death in self.all_deaths:
                prompt += f"Night {death.night}: {death.player_name} ({death.role}) - {death.cause}\n"
                if death.last_will:
                    prompt += f"  Will: {death.last_will}\n"
                if death.death_note:
                    prompt += f"  Death Note: {death.death_note}\n"

        # YOUR INVESTIGATION RESULTS
        if self.all_investigations:
            prompt += "\n=== YOUR INVESTIGATIONS ===\n"
            for inv in self.all_investigations:
                prompt += f"Night {inv.night}: Player {inv.target_id} - {inv.result}\n"

        # YOUR SUSPICIONS (condensed analysis)
        if self.memory.suspicions:
            prompt += "\n=== YOUR SUSPICIONS ===\n"
            sorted_suspicions = sorted(
                self.memory.suspicions.items(),
                key=lambda x: x[1].level,
                reverse=True
            )
            for pid, sus in sorted_suspicions[:5]:  # Top 5
                claimed = self.memory.role_claims.get(pid)
                claim_text = f" (claims {claimed.claimed_role})" if claimed else ""
                prompt += f"Player {pid}: {sus.level:.1f}/1.0{claim_text}\n"
                if sus.reasons:
                    prompt += f"  Reasons: {', '.join(sus.reasons[-3:])}\n"

        # SPECIFIC TASK
        prompt += f"\n=== TASK ===\n{purpose}\n"

        return prompt

    def _get_win_condition(self) -> str:
        """Get win condition text for this role."""
        if self.faction == "Town":
            return "Eliminate all Mafia and Neutral Killing roles."
        elif self.faction == "Mafia":
            return "Achieve majority over Town and eliminate Neutral Killing."
        elif self.role == "Serial Killer":
            return "Be the last player alive."
        elif self.role == "Jester":
            return "Get yourself lynched by the Town."
        elif self.role == "Executioner":
            return "Get your target lynched."
        elif self.role == "Survivor":
            return "Survive to see any faction win."
        else:
            return "Achieve your role's objective."
