"""Voting system for accusations and judgments.

Handles two types of votes:
1. Accusation votes - Who to put on trial
2. Judgment votes - Guilty or Innocent
"""
from typing import Optional
from loguru import logger
from pydantic import BaseModel

from ..models.game import GameState
from ..models.player import Player


# ============================================================================
# Vote Models
# ============================================================================

class Vote(BaseModel):
    """A single vote cast by a player."""
    voter_id: int
    target_id: Optional[int] = None  # None = abstain
    vote_type: str  # "accusation" or "judgment"
    guilty: Optional[bool] = None  # For judgment votes


class VoteCount(BaseModel):
    """Vote count for a single candidate."""
    target_id: int
    votes: int
    voters: list[int] = []  # Player IDs who voted for this target


class VotingResult(BaseModel):
    """Result of a voting round."""
    vote_type: str
    votes_cast: list[Vote]
    vote_counts: dict[int, VoteCount] = {}  # target_id -> count
    winner_id: Optional[int] = None
    tied: bool = False
    votes_required: int = 0


class JudgmentResult(BaseModel):
    """Result of a judgment vote."""
    accused_id: int
    guilty_votes: int
    innocent_votes: int
    abstain_votes: int
    verdict: str  # "guilty", "innocent", or "tied"
    voters: dict[int, str] = {}  # player_id -> "guilty"/"innocent"/"abstain"


# ============================================================================
# Voting Manager
# ============================================================================

class VotingManager:
    """
    Manages accusation and judgment voting.

    Handles vote counting, majority calculation, and special role abilities.
    """

    def __init__(self):
        self.current_votes: list[Vote] = []

    def process_accusation_votes(
        self,
        game_state: GameState,
        votes: list[Vote]
    ) -> VotingResult:
        """
        Process accusation votes to determine who goes on trial.

        Args:
            game_state: Current game state
            votes: All votes cast

        Returns:
            VotingResult with winner (if any)
        """
        self.current_votes = votes

        # Count votes
        vote_counts: dict[int, VoteCount] = {}

        for vote in votes:
            if vote.target_id is None:
                continue  # Abstain

            if vote.target_id not in vote_counts:
                vote_counts[vote.target_id] = VoteCount(
                    target_id=vote.target_id,
                    votes=0,
                    voters=[]
                )

            # Apply vote weight (Mayor has 3 votes)
            vote_weight = self._get_vote_weight(game_state, vote.voter_id)
            vote_counts[vote.target_id].votes += vote_weight
            vote_counts[vote.target_id].voters.append(vote.voter_id)

        # Determine votes required (majority of living players)
        alive_count = sum(1 for p in game_state.players if p.is_alive)
        votes_required = (alive_count // 2) + 1

        logger.info(
            f"Accusation votes: {len(vote_counts)} candidates, "
            f"{votes_required} votes required for trial"
        )

        # Find winner
        winner_id = None
        max_votes = 0
        tied = False

        for target_id, count in vote_counts.items():
            if count.votes > max_votes:
                max_votes = count.votes
                winner_id = target_id
                tied = False
            elif count.votes == max_votes and max_votes >= votes_required:
                tied = True

        # Only succeed if majority reached and no tie
        if max_votes < votes_required or tied:
            winner_id = None

        if winner_id:
            winner = self._get_player(game_state, winner_id)
            logger.info(
                f"Player {winner_id} ({winner.name}) put on trial with {max_votes} votes"
            )
        else:
            logger.info(f"No one put on trial (max votes: {max_votes}, tied: {tied})")

        return VotingResult(
            vote_type="accusation",
            votes_cast=votes,
            vote_counts=vote_counts,
            winner_id=winner_id,
            tied=tied,
            votes_required=votes_required
        )

    def process_judgment_votes(
        self,
        game_state: GameState,
        accused_id: int,
        votes: list[Vote]
    ) -> JudgmentResult:
        """
        Process judgment votes to determine verdict.

        Args:
            game_state: Current game state
            accused_id: Player on trial
            votes: All votes cast

        Returns:
            JudgmentResult with verdict
        """
        self.current_votes = votes

        guilty_votes = 0
        innocent_votes = 0
        abstain_votes = 0
        voters: dict[int, str] = {}

        for vote in votes:
            # Apply vote weight
            vote_weight = self._get_vote_weight(game_state, vote.voter_id)

            if vote.guilty is True:
                guilty_votes += vote_weight
                voters[vote.voter_id] = "guilty"
            elif vote.guilty is False:
                innocent_votes += vote_weight
                voters[vote.voter_id] = "innocent"
            else:
                abstain_votes += vote_weight
                voters[vote.voter_id] = "abstain"

        # Determine verdict (need majority for guilty)
        if guilty_votes > innocent_votes:
            verdict = "guilty"
        elif innocent_votes > guilty_votes:
            verdict = "innocent"
        else:
            verdict = "tied"  # Ties favor innocent

        accused = self._get_player(game_state, accused_id)

        logger.info(
            f"Judgment for {accused.name}: "
            f"{guilty_votes} guilty, {innocent_votes} innocent, {abstain_votes} abstain "
            f"→ {verdict}"
        )

        return JudgmentResult(
            accused_id=accused_id,
            guilty_votes=guilty_votes,
            innocent_votes=innocent_votes,
            abstain_votes=abstain_votes,
            verdict=verdict,
            voters=voters
        )

    def can_vote(self, game_state: GameState, player_id: int) -> tuple[bool, str]:
        """
        Check if a player can vote.

        Args:
            game_state: Current game state
            player_id: Player attempting to vote

        Returns:
            (can_vote, reason)
        """
        player = self._get_player(game_state, player_id)

        # Must be alive
        if not player.is_alive:
            return False, "You are dead"

        # Check if blackmailed
        if self._is_blackmailed(game_state, player_id):
            return False, "You have been blackmailed!"

        return True, "OK"

    def reveal_mayor(self, game_state: GameState, player_id: int) -> bool:
        """
        Reveal a player as Mayor (gives 3 vote power).

        Args:
            game_state: Current game state
            player_id: Player revealing as Mayor

        Returns:
            True if reveal successful
        """
        player = self._get_player(game_state, player_id)

        if player.role.id != "mayor":
            logger.warning(f"Player {player_id} tried to reveal as Mayor but isn't Mayor")
            return False

        # Check if Mayor has already revealed (max 1 use)
        if "reveal" in player.ability_uses_remaining:
            if player.ability_uses_remaining["reveal"] <= 0:
                logger.warning(f"Mayor {player_id} has already revealed")
                return False

        # Mark mayor as revealed
        player.revealed = True

        # Decrement reveal uses
        if "reveal" in player.ability_uses_remaining:
            player.ability_uses_remaining["reveal"] -= 1

        logger.info(f"Player {player_id} ({player.name}) revealed as Mayor! They now have 3 votes.")

        return True

    def get_vote_summary(self, game_state: GameState) -> dict[int, list[int]]:
        """
        Get current vote summary.

        Returns:
            Dict mapping target_id to list of voter_ids
        """
        summary: dict[int, list[int]] = {}

        for vote in self.current_votes:
            if vote.target_id is None:
                continue

            if vote.target_id not in summary:
                summary[vote.target_id] = []

            summary[vote.target_id].append(vote.voter_id)

        return summary

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _get_player(self, game_state: GameState, player_id: int) -> Player:
        """Get player by ID."""
        return next(p for p in game_state.players if p.player_id == player_id)

    def _get_vote_weight(self, game_state: GameState, voter_id: int) -> int:
        """Get vote weight for a player (Mayor has 3 votes)."""
        player = self._get_player(game_state, voter_id)

        # Mayor has 3 votes if revealed
        if player.role.id == "mayor" and player.revealed:
            return 3

        return 1

    def _is_blackmailed(self, game_state: GameState, player_id: int) -> bool:
        """Check if player is blackmailed."""
        player = self._get_player(game_state, player_id)
        return player.is_blackmailed

def clear_day_states(game_state: GameState) -> None:
    """Clear temporary day-specific states on all players."""
    for player in game_state.players:
        # Clear blackmail at start of day
        player.is_blackmailed = False
        player.can_speak = True
        player.voted_today = False
