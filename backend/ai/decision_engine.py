"""AI Decision Engine using Pydantic AI for structured outputs.

With 64K context, AIs can make informed decisions based on complete game history.
"""
import asyncio
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .context_manager import AIContextManager
from .llm_client import LLMClient
from ..models.game import GameState
from ..models.player import Player
from ..models.role import RoleAbility
from ..config.settings import settings


# ============================================================================
# Decision Output Models
# ============================================================================

class TargetDecision(BaseModel):
    """Night action targeting decision."""
    target_player_id: Optional[int] = Field(
        None,
        description="ID of player to target (None = no action)"
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of decision (for AI memory)"
    )
    suspicion_level: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="How suspicious is the target (0=town, 1=evil)"
    )


class VoteDecision(BaseModel):
    """Voting decision (accusation or judgment)."""
    vote_for_player_id: Optional[int] = Field(
        None,
        description="ID of player to vote for (None = abstain)"
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of vote decision"
    )
    confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in this vote (0=unsure, 1=certain)"
    )
    guilty: Optional[bool] = Field(
        None,
        description="Guilty/Innocent for judgment votes"
    )


class ChatDecision(BaseModel):
    """Chat message decision."""
    should_speak: bool = Field(
        ...,
        description="Whether to send a message"
    )
    message: Optional[str] = Field(
        None,
        description="Message to send (if should_speak=True)"
    )
    message_type: str = Field(
        "normal",
        description="Type of message: normal, claim, accusation, defense"
    )
    targets_player_id: Optional[int] = Field(
        None,
        description="Player this message is about (for accusations/claims)"
    )


class ClaimDecision(BaseModel):
    """Role claim decision."""
    should_claim: bool = Field(
        ...,
        description="Whether to make a role claim"
    )
    claimed_role: Optional[str] = Field(
        None,
        description="Role to claim (can be fake!)"
    )
    reasoning: str = Field(
        ...,
        description="Why making this claim"
    )
    is_truthful: bool = Field(
        ...,
        description="Is this claim truthful?"
    )


class DefenseDecision(BaseModel):
    """Defense speech decision."""
    defense_speech: str = Field(
        ...,
        description="Defense speech to give (max 200 chars)"
    )
    claim_role: Optional[str] = Field(
        None,
        description="Role to claim during defense"
    )
    call_out_player_id: Optional[int] = Field(
        None,
        description="Player to accuse during defense"
    )


# ============================================================================
# AI Decision Engine
# ============================================================================

class AIDecisionEngine:
    """
    Makes AI decisions using Pydantic AI with 64K context.

    This is where the magic happens - AIs make decisions based on
    COMPLETE game history, no information loss!
    """

    def __init__(
        self,
        llm_client: LLMClient,
        context_manager: AIContextManager
    ):
        self.llm_client = llm_client
        self.context_manager = context_manager

        # Initialize agents as None - will be created when LLM is loaded
        self.target_agent = None
        self.vote_agent = None
        self.chat_agent = None
        self.claim_agent = None
        self.defense_agent = None

        # Try to create agents if LLM is available
        if llm_client._loaded:
            try:
                self._create_agents()
            except Exception as e:
                logger.warning(f"Could not create Pydantic AI agents: {e}")
                logger.warning("AI decisions will use fallback logic")

    def _create_agents(self) -> None:
        """Create Pydantic AI agents for structured outputs."""
        # TODO: Update to new Pydantic AI API
        # The API has changed - result_type is no longer a parameter
        # Need to use the new response_model approach
        logger.warning("Pydantic AI agents not yet updated to new API")

        # For now, agents stay None and we use fallback logic
        # TODO: Implement proper Pydantic AI integration with new API
        return

    async def decide_night_target(
        self,
        game_state: GameState,
        player_id: int,
        ability: RoleAbility
    ) -> TargetDecision:
        """
        Decide who to target with a night action.

        Args:
            game_state: Current game state
            player_id: AI player making the decision
            ability: The ability being used

        Returns:
            TargetDecision with chosen target
        """
        # Get full context (with 64K window, this includes EVERYTHING!)
        context = self.context_manager.get_context(player_id)

        # Build prompt with complete game context
        prompt = context.build_full_prompt(
            game_state,
            purpose=f"night_target_{ability.name}"
        )

        # Add specific targeting instructions
        alive_players = [
            p for p in game_state.players
            if p.is_alive and p.player_id != player_id
        ]

        prompt += f"\n\nYou must use your {ability.name} ability."
        prompt += "\n\nAlive players you can target:"
        for p in alive_players:
            prompt += f"\n- Player {p.player_id}: {p.name}"

        prompt += "\n\nWho do you target? Consider your win condition and all information you've gathered."

        try:
            # Use Pydantic AI agent to get structured decision if available
            if self.target_agent is None:
                # Fallback: Use simple random targeting
                logger.debug(f"Player {player_id} using fallback targeting (no AI agent)")
                import random
                target_id = random.choice(alive_players).player_id if alive_players else None
                return TargetDecision(
                    target_player_id=target_id,
                    reasoning="Random target (AI agent not initialized)",
                    suspicion_level=0.5
                )

            logger.info(f"Player {player_id} deciding target for {ability.name}...")

            result = await self.target_agent.run(prompt)
            decision = result.data

            # Validate target is alive
            if decision.target_player_id is not None:
                target = next(
                    (p for p in alive_players if p.player_id == decision.target_player_id),
                    None
                )
                if not target:
                    logger.warning(
                        f"Player {player_id} chose invalid target {decision.target_player_id}, "
                        f"selecting random target"
                    )
                    # Fallback: random target
                    import random
                    decision.target_player_id = random.choice(alive_players).player_id if alive_players else None

            logger.info(
                f"Player {player_id} targets {decision.target_player_id}: {decision.reasoning}"
            )

            return decision

        except Exception as e:
            logger.error(f"Error in night target decision for player {player_id}: {e}")
            # Fallback: random target
            import random
            target_id = random.choice(alive_players).player_id if alive_players else None
            return TargetDecision(
                target_player_id=target_id,
                reasoning=f"Fallback decision due to error: {e}",
                suspicion_level=0.5
            )

    async def decide_vote(
        self,
        game_state: GameState,
        player_id: int,
        vote_type: str = "accusation"
    ) -> VoteDecision:
        """
        Decide who to vote for (accusation or judgment).

        Args:
            game_state: Current game state
            player_id: AI player making the decision
            vote_type: "accusation" or "judgment"

        Returns:
            VoteDecision with chosen target
        """
        context = self.context_manager.get_context(player_id)
        prompt = context.build_full_prompt(game_state, purpose=f"vote_{vote_type}")

        if vote_type == "accusation":
            alive_players = [
                p for p in game_state.players
                if p.is_alive and p.player_id != player_id
            ]
            prompt += "\n\nYou can vote to put someone on trial."
            prompt += "\n\nAlive players:"
            for p in alive_players:
                prompt += f"\n- Player {p.player_id}: {p.name}"
            prompt += "\n\nWho do you vote for? (You can abstain by choosing None)"

        else:  # judgment
            accused_id = game_state.accused_player_id
            accused = next(
                (p for p in game_state.players if p.player_id == accused_id),
                None
            )
            prompt += f"\n\nPlayer {accused_id} ({accused.name if accused else 'Unknown'}) is on trial."
            prompt += "\n\nDo you vote GUILTY or INNOCENT?"

        try:
            # Fallback if no AI agent
            if self.vote_agent is None:
                logger.debug(f"Player {player_id} using fallback voting (no AI agent)")
                # Simple fallback: abstain
                return VoteDecision(
                    vote_for_player_id=None,
                    reasoning="Abstain (AI agent not initialized)",
                    confidence=0.0
                )

            result = await self.vote_agent.run(prompt)
            decision = result.data

            logger.info(
                f"Player {player_id} votes for {decision.vote_for_player_id}: {decision.reasoning}"
            )

            return decision

        except Exception as e:
            logger.error(f"Error in vote decision for player {player_id}: {e}")
            # Fallback: abstain
            return VoteDecision(
                vote_for_player_id=None,
                reasoning=f"Fallback abstain due to error: {e}",
                confidence=0.0
            )

    async def decide_chat_message(
        self,
        game_state: GameState,
        player_id: int,
        context_hint: Optional[str] = None
    ) -> ChatDecision:
        """
        Decide whether to speak and what to say.

        Args:
            game_state: Current game state
            player_id: AI player making the decision
            context_hint: Optional hint about what to discuss

        Returns:
            ChatDecision with message
        """
        context = self.context_manager.get_context(player_id)
        prompt = context.build_full_prompt(game_state, purpose="chat")

        prompt += "\n\nShould you speak? If so, what should you say?"
        prompt += "\nKeep messages under 200 characters."
        prompt += "\nBe strategic - don't reveal too much information."

        if context_hint:
            prompt += f"\n\nContext: {context_hint}"

        try:
            # Fallback if no AI agent
            if self.chat_agent is None:
                logger.debug(f"Player {player_id} using fallback chat (no AI agent)")
                # Stay silent
                return ChatDecision(
                    should_speak=False,
                    message=None,
                    message_type="normal"
                )

            result = await self.chat_agent.run(prompt)
            decision = result.data

            if decision.should_speak and decision.message:
                # Truncate message if too long
                if len(decision.message) > 200:
                    decision.message = decision.message[:197] + "..."

                logger.info(f"Player {player_id} says: {decision.message}")

            return decision

        except Exception as e:
            logger.error(f"Error in chat decision for player {player_id}: {e}")
            # Fallback: stay silent
            return ChatDecision(
                should_speak=False,
                message=None,
                message_type="normal"
            )

    async def decide_defense(
        self,
        game_state: GameState,
        player_id: int
    ) -> DefenseDecision:
        """
        Decide defense speech when on trial.

        Args:
            game_state: Current game state
            player_id: AI player making the decision

        Returns:
            DefenseDecision with defense speech
        """
        context = self.context_manager.get_context(player_id)
        prompt = context.build_full_prompt(game_state, purpose="defense")

        prompt += "\n\nYou are on trial! Make your defense."
        prompt += "\nYou have 20 seconds to convince others you're innocent."
        prompt += "\nConsider claiming your role or accusing someone else."
        prompt += "\nKeep your defense under 200 characters."

        try:
            # Fallback if no AI agent
            if self.defense_agent is None:
                logger.debug(f"Player {player_id} using fallback defense (no AI agent)")
                return DefenseDecision(
                    defense_speech="I'm innocent! Don't vote me up!",
                    claim_role=None,
                    call_out_player_id=None
                )

            result = await self.defense_agent.run(prompt)
            decision = result.data

            # Truncate defense if too long
            if len(decision.defense_speech) > 200:
                decision.defense_speech = decision.defense_speech[:197] + "..."

            logger.info(f"Player {player_id} defends: {decision.defense_speech}")

            return decision

        except Exception as e:
            logger.error(f"Error in defense decision for player {player_id}: {e}")
            # Fallback: generic defense
            return DefenseDecision(
                defense_speech="I'm innocent! Don't vote me up!",
                claim_role=None,
                call_out_player_id=None
            )

    async def batch_decide_night_targets(
        self,
        game_state: GameState,
        decisions_needed: list[tuple[int, RoleAbility]]
    ) -> dict[int, TargetDecision]:
        """
        Process multiple night target decisions in parallel batches.

        Args:
            game_state: Current game state
            decisions_needed: List of (player_id, ability) tuples

        Returns:
            Dict mapping player_id to TargetDecision
        """
        results = {}

        # Process in batches to avoid overloading the LLM
        batch_size = settings.ai_batch_size

        for i in range(0, len(decisions_needed), batch_size):
            batch = decisions_needed[i:i + batch_size]

            logger.info(
                f"Processing night target batch {i//batch_size + 1} "
                f"({len(batch)} AIs)"
            )

            # Process batch in parallel
            tasks = [
                self.decide_night_target(game_state, player_id, ability)
                for player_id, ability in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Store results
            for (player_id, _), result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error for player {player_id}: {result}")
                    # Fallback decision
                    results[player_id] = TargetDecision(
                        target_player_id=None,
                        reasoning="Error in decision making",
                        suspicion_level=0.5
                    )
                else:
                    results[player_id] = result

        return results

    async def batch_decide_votes(
        self,
        game_state: GameState,
        player_ids: list[int],
        vote_type: str = "accusation"
    ) -> dict[int, VoteDecision]:
        """
        Process multiple vote decisions in parallel batches.

        Args:
            game_state: Current game state
            player_ids: List of player IDs making decisions
            vote_type: "accusation" or "judgment"

        Returns:
            Dict mapping player_id to VoteDecision
        """
        results = {}
        batch_size = settings.ai_batch_size

        for i in range(0, len(player_ids), batch_size):
            batch = player_ids[i:i + batch_size]

            logger.info(
                f"Processing {vote_type} vote batch {i//batch_size + 1} "
                f"({len(batch)} AIs)"
            )

            tasks = [
                self.decide_vote(game_state, player_id, vote_type)
                for player_id in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for player_id, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error for player {player_id}: {result}")
                    results[player_id] = VoteDecision(
                        vote_for_player_id=None,
                        reasoning="Error in decision making",
                        confidence=0.0
                    )
                else:
                    results[player_id] = result

        return results
