"""AI context manager - manages 64K context windows for all AI players."""
from loguru import logger
from typing import Dict
from ..models.ai import AIContext, AIMemory, SuspicionData, RoleClaim, InvestigationRecord
from ..models.game import GameState, ChatMessage, VoteRecord
from ..models.player import Player


class AIContextManager:
    """
    Manages context windows for all AI players.

    With 64K context, we keep COMPLETE game history for each AI.
    No summarization needed!
    """

    def __init__(self):
        self.contexts: Dict[int, AIContext] = {}

    def initialize_contexts(self, game_state: GameState) -> None:
        """
        Initialize AI contexts for all AI players at game start.

        Args:
            game_state: Game state with player assignments
        """
        logger.info("Initializing AI contexts...")

        for player in game_state.players:
            if not player.is_human:
                context = AIContext(
                    player_id=player.player_id,
                    role=player.role.name,
                    faction=player.faction.value,
                    night_number=game_state.night_number,
                    day_number=game_state.day_number,
                    memory=AIMemory(),
                    objectives=self._get_role_objectives(player),
                )

                # Add faction knowledge (Mafia knows other Mafia)
                if player.faction.value == "Mafia":
                    context.faction_member_ids = [
                        p.player_id for p in game_state.players
                        if p.faction.value == "Mafia" and p.player_id != player.player_id
                    ]

                self.contexts[player.player_id] = context
                logger.debug(f"Initialized context for Player {player.player_id} ({player.role.name})")

        logger.success(f"Initialized {len(self.contexts)} AI contexts")

    def update_all_contexts(self, game_state: GameState) -> None:
        """
        Update all AI contexts with latest game state.

        With 64K context, we simply append new data - no pruning!

        Args:
            game_state: Current game state
        """
        for player_id, context in self.contexts.items():
            self._update_context(context, game_state, player_id)

    def _update_context(
        self,
        context: AIContext,
        game_state: GameState,
        player_id: int
    ) -> None:
        """
        Update a single AI's context with complete game history.

        Args:
            context: AI context to update
            game_state: Current game state
            player_id: Player ID
        """
        # Update phase numbers
        context.night_number = game_state.night_number
        context.day_number = game_state.day_number

        # COMPLETE chat history (no pruning with 64K context!)
        context.complete_chat_history = game_state.all_chat_messages.copy()

        # COMPLETE vote history
        context.complete_vote_history = game_state.all_votes.copy()

        # ALL deaths
        context.all_deaths = game_state.all_deaths.copy()

        # Player's own investigations (if investigative role)
        # This would be populated by the night action system
        # For now, it's maintained separately

    def update_suspicion(
        self,
        player_id: int,
        target_id: int,
        delta: float,
        reason: str
    ) -> None:
        """
        Update AI's suspicion level for a target.

        Args:
            player_id: AI player ID
            target_id: Target player ID
            delta: Change in suspicion (-1.0 to +1.0)
            reason: Reason for suspicion change
        """
        if player_id not in self.contexts:
            return

        context = self.contexts[player_id]
        memory = context.memory

        if target_id not in memory.suspicions:
            memory.suspicions[target_id] = SuspicionData(
                player_id=target_id,
                level=0.5,  # Neutral starting point
                last_updated_night=context.night_number
            )

        sus = memory.suspicions[target_id]
        sus.level = max(0.0, min(1.0, sus.level + delta))
        sus.reasons.append(reason)
        sus.last_updated_night = context.night_number

        logger.debug(
            f"Player {player_id}: Updated suspicion of Player {target_id} "
            f"to {sus.level:.2f} ({reason})"
        )

    def record_role_claim(
        self,
        observer_id: int,
        claimer_id: int,
        claimed_role: str,
        day: int
    ) -> None:
        """
        Record when a player claims a role.

        Args:
            observer_id: AI observing the claim
            claimer_id: Player making the claim
            claimed_role: Role being claimed
            day: Day number
        """
        if observer_id not in self.contexts:
            return

        context = self.contexts[observer_id]
        memory = context.memory

        # Check for contradictions
        contradictions = []
        if claimer_id in memory.role_claims:
            old_claim = memory.role_claims[claimer_id]
            if old_claim.claimed_role != claimed_role:
                contradictions.append(
                    f"Changed from {old_claim.claimed_role} to {claimed_role}"
                )

        memory.role_claims[claimer_id] = RoleClaim(
            player_id=claimer_id,
            claimed_role=claimed_role,
            day_claimed=day,
            contradictions=contradictions
        )

        logger.debug(
            f"Player {observer_id}: Recorded claim from Player {claimer_id} "
            f"({claimed_role})"
        )

    def add_investigation_result(
        self,
        investigator_id: int,
        target_id: int,
        result: str,
        night: int
    ) -> None:
        """
        Add investigation result to AI's context.

        Args:
            investigator_id: Investigator player ID
            target_id: Target player ID
            result: Investigation result text
            night: Night number
        """
        if investigator_id not in self.contexts:
            return

        context = self.contexts[investigator_id]
        player = self._get_player_role(investigator_id)

        context.all_investigations.append(
            InvestigationRecord(
                target_id=target_id,
                result=result,
                night=night,
                investigator_role=player
            )
        )

        # Update suspicion based on result
        if "suspicious" in result.lower():
            self.update_suspicion(
                investigator_id,
                target_id,
                delta=0.5,
                reason=f"Investigation result: {result}"
            )
        elif "not suspicious" in result.lower():
            self.update_suspicion(
                investigator_id,
                target_id,
                delta=-0.3,
                reason=f"Investigation result: {result}"
            )

    def get_context(self, player_id: int) -> AIContext:
        """
        Get AI context for a player.

        Args:
            player_id: Player ID

        Returns:
            AI context

        Raises:
            KeyError: If player_id not found
        """
        if player_id not in self.contexts:
            raise KeyError(f"No context found for player {player_id}")

        return self.contexts[player_id]

    def get_context_stats(self, player_id: int) -> dict:
        """
        Get statistics about an AI's context usage.

        Args:
            player_id: Player ID

        Returns:
            Dictionary with context statistics
        """
        if player_id not in self.contexts:
            return {}

        context = self.contexts[player_id]

        return {
            "player_id": player_id,
            "role": context.role,
            "chat_messages": len(context.complete_chat_history),
            "votes": len(context.complete_vote_history),
            "deaths": len(context.all_deaths),
            "investigations": len(context.all_investigations),
            "suspicions_tracked": len(context.memory.suspicions),
            "claims_recorded": len(context.memory.role_claims),
        }

    def _get_role_objectives(self, player: Player) -> list[str]:
        """Get objectives for a role."""
        if player.faction.value == "Town":
            return [
                "Eliminate all Mafia and Neutral Killing roles",
                f"Use your {player.role.name} ability effectively",
                "Coordinate with other Town members"
            ]
        elif player.faction.value == "Mafia":
            return [
                "Achieve majority over Town",
                "Eliminate Neutral Killing roles",
                "Coordinate kills with Mafia members",
                "Avoid detection"
            ]
        else:  # Neutral
            if player.role.name == "Serial Killer":
                return ["Be the last player alive", "Kill everyone"]
            elif player.role.name == "Jester":
                return ["Get yourself lynched by the Town"]
            elif player.role.name == "Survivor":
                return ["Survive to see any faction win"]
            else:
                return [player.role.goal]

    def _get_player_role(self, player_id: int) -> str:
        """Get player's role name."""
        context = self.contexts.get(player_id)
        return context.role if context else "Unknown"
