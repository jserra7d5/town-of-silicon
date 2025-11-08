"""Game Orchestrator - Main game controller.

Coordinates all game systems and runs the game loop.
"""
import asyncio
from typing import Optional
from loguru import logger

from ..models.game import GameState, GamePhase, PhaseType, ChatMessage
from ..models.player import Player, DeathInfo
from ..core.role_assignment import RoleAssignmentSystem, RoleRegistry
from ..core.phase_manager import PhaseManager, PhaseTransitionController
from ..ai.llm_client import LLMClient
from ..ai.context_manager import AIContextManager
from ..ai.decision_engine import AIDecisionEngine
from ..actions.night_actions import NightActionResolver, NightAction
from ..actions.voting import VotingManager, Vote
from ..api.websocket import WebSocketHandler, ConnectionManager
from ..config.settings import settings


# ============================================================================
# Game Orchestrator
# ============================================================================

class GameOrchestrator:
    """
    Main game controller that orchestrates all game systems.

    This is the heart of the game - coordinates phases, AI decisions,
    actions, and communicates with clients via WebSocket.
    """

    def __init__(self):
        # Core systems
        self.role_registry = RoleRegistry()
        self.role_assigner = RoleAssignmentSystem(self.role_registry)
        self.phase_manager = PhaseManager()
        self.phase_controller = PhaseTransitionController(self.phase_manager)

        # AI systems
        self.llm_client = LLMClient()
        self.context_manager = AIContextManager()
        self.decision_engine = AIDecisionEngine(self.llm_client, self.context_manager)

        # Action systems
        self.night_resolver = NightActionResolver()
        self.voting_manager = VotingManager()

        # Communication
        self.connection_manager = ConnectionManager()
        self.ws_handler = WebSocketHandler(self.connection_manager)

        # Game state
        self.game_state: Optional[GameState] = None
        self.running = False

        # Human player
        self.human_player_id: int = 0  # Will be set during game creation

    async def initialize(self):
        """Initialize all systems."""
        logger.info("Initializing game orchestrator...")

        # Try to load LLM model (optional - game can run in demo mode without it)
        try:
            await asyncio.to_thread(self.llm_client.load_model)
            logger.success("LLM model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load LLM model: {e}")
            logger.warning("Game will run in demo mode with random AI decisions")

        # Set up phase callbacks
        self.phase_manager.on_phase_start = self.on_phase_start
        self.phase_manager.on_phase_end = self.on_phase_end

        logger.success("Game orchestrator initialized")

    async def create_game(self, human_position: Optional[int] = None) -> GameState:
        """
        Create a new game.

        Args:
            human_position: Position for human player (0-14, None = random)

        Returns:
            Initial GameState
        """
        logger.info("Creating new game...")

        # Assign roles
        assignments = self.role_assigner.assign_roles(
            role_list_name="classic",
            human_position=human_position
        )

        # Create players
        players = []
        for i, assignment in enumerate(assignments):
            player = Player(
                player_id=i,
                name=assignment.player_name,
                role=assignment.role,
                is_human=(i == 0),  # First player is human
                is_alive=True
            )
            players.append(player)

        self.human_player_id = 0

        # Create initial game state
        self.game_state = GameState(
            players=players,
            current_phase=GamePhase(
                phase_type=PhaseType.PREGAME,
                phase_number=0,
                duration=3.0,
                remaining_time=3.0
            ),
            current_day=0
        )

        # Initialize AI contexts
        self.context_manager.initialize_contexts(self.game_state)

        # Set game state in WebSocket handler
        self.ws_handler.set_game_state(self.game_state)

        logger.info(f"Game created with {len(players)} players")

        # Log role distribution
        for player in players:
            player_type = "HUMAN" if player.is_human else "AI"
            logger.info(
                f"  Player {player.player_id} ({player.name}): "
                f"{player.role.name} [{player_type}]"
            )

        return self.game_state

    async def start_game(self):
        """Start the game loop."""
        if not self.game_state:
            raise RuntimeError("No game created - call create_game() first")

        logger.info("Starting game...")
        self.running = True

        # Start with pregame phase
        await self.run_pregame()

        # Main game loop
        while self.running:
            # Check win conditions
            winner = self.check_victory()
            if winner:
                await self.end_game(winner)
                break

            # Run current phase
            await self.run_current_phase()

            # Transition to next phase
            await self.transition_phase()

    async def run_pregame(self):
        """Run pregame phase (role reveal to each player)."""
        logger.info("Running pregame phase...")

        # Send role information to each player
        for player in self.game_state.players:
            if player.is_human:
                # Send role to human via WebSocket
                await self.connection_manager.send_to_player(
                    {
                        "type": "role_reveal",
                        "role": player.role.model_dump()
                    },
                    player.player_id
                )

        # Wait for pregame duration
        await asyncio.sleep(self.game_state.current_phase.duration)

    async def run_current_phase(self):
        """Run the current phase."""
        phase_type = self.game_state.current_phase.phase_type

        logger.info(f"Running {phase_type.value} phase...")

        if phase_type == PhaseType.NIGHT:
            await self.run_night_phase()

        elif phase_type == PhaseType.DAY_DISCUSSION:
            await self.run_day_discussion()

        elif phase_type == PhaseType.DEFENSE:
            await self.run_defense_phase()

        elif phase_type == PhaseType.JUDGMENT:
            await self.run_judgment_phase()

        elif phase_type == PhaseType.JUDGMENT_RESULTS:
            await self.run_judgment_results()

        elif phase_type == PhaseType.LAST_WORDS:
            await self.run_last_words()

    async def run_night_phase(self):
        """Run night phase - collect and resolve night actions."""
        logger.info("Night phase starting...")

        # Get all living players with night abilities
        actors = [
            p for p in self.game_state.players
            if p.is_alive and p.role.abilities
        ]

        ai_actors = [p for p in actors if not p.is_human]

        # Collect AI decisions in batches
        decisions_needed = [
            (p.player_id, p.role.abilities[0])  # First ability
            for p in ai_actors
        ]

        # Mark AIs as pending (for adaptive timing)
        for player_id, _ in decisions_needed:
            self.phase_manager.mark_ai_pending(player_id)

        # Get AI decisions in parallel batches
        ai_decisions = await self.decision_engine.batch_decide_night_targets(
            self.game_state,
            decisions_needed
        )

        # Mark AIs as done
        for player_id in ai_decisions.keys():
            self.phase_manager.mark_ai_done(player_id)

        # Convert decisions to actions
        actions = []
        for player_id, decision in ai_decisions.items():
            player = next(p for p in actors if p.player_id == player_id)
            ability = player.role.abilities[0]

            action = NightAction(
                player_id=player_id,
                ability=ability,
                target_id=decision.target_player_id,
                priority=ability.priority
            )
            actions.append(action)

        # Wait for human action if alive
        human = self.game_state.players[self.human_player_id]
        if human.is_alive and human.role.abilities:
            # Wait for human to submit action via WebSocket
            # For now, skip human action (would come from ws_handler.action_queue)
            pass

        # Run phase timer
        await self.phase_manager.run_phase_loop()

        # Resolve night actions
        logger.info(f"Resolving {len(actions)} night actions...")
        summary = self.night_resolver.resolve_night(self.game_state, actions)

        # Apply deaths
        for death in summary.deaths:
            player = next(
                p for p in self.game_state.players
                if p.player_id == death.player_id
            )
            player.is_alive = False
            player.death_info = death
            self.game_state.all_deaths.append(death)

        # Send action results to players
        for player_id, result in summary.action_results.items():
            await self.connection_manager.send_to_player(
                {
                    "type": "night_action_result",
                    "result": result.model_dump()
                },
                player_id
            )

        # Announce deaths
        if summary.deaths:
            death_msg = f"{len(summary.deaths)} player(s) died last night: "
            death_msg += ", ".join([
                f"{next(p for p in self.game_state.players if p.player_id == d.player_id).name}"
                for d in summary.deaths
            ])

            await self.broadcast_system_message(death_msg)

        logger.info(f"Night phase complete: {len(summary.deaths)} deaths")

    async def run_day_discussion(self):
        """Run day discussion phase - AIs chat and vote."""
        logger.info("Day discussion phase starting...")

        # AIs participate in discussion
        ai_players = [
            p for p in self.game_state.players
            if p.is_alive and not p.is_human
        ]

        # AIs make occasional chat messages during day
        for _ in range(3):  # 3 rounds of chat
            # Random selection of AIs to speak
            import random
            speakers = random.sample(
                ai_players,
                min(3, len(ai_players))  # 3 AIs speak per round
            )

            for player in speakers:
                decision = await self.decision_engine.decide_chat_message(
                    self.game_state,
                    player.player_id
                )

                if decision.should_speak and decision.message:
                    chat_msg = ChatMessage(
                        player_id=player.player_id,
                        player_name=player.name,
                        message=decision.message,
                        phase=PhaseType.DAY_DISCUSSION.value,
                        day_number=self.game_state.current_day
                    )

                    self.game_state.all_chat_messages.append(chat_msg)

                    await self.connection_manager.broadcast({
                        "type": "chat_message",
                        "message": chat_msg.model_dump()
                    })

            # Wait a bit between chat rounds
            await asyncio.sleep(5)

        # Collect accusation votes
        vote_decisions = await self.decision_engine.batch_decide_votes(
            self.game_state,
            [p.player_id for p in ai_players],
            vote_type="accusation"
        )

        votes = [
            Vote(
                voter_id=player_id,
                target_id=decision.vote_for_player_id,
                vote_type="accusation"
            )
            for player_id, decision in vote_decisions.items()
        ]

        # Process votes
        result = self.voting_manager.process_accusation_votes(
            self.game_state,
            votes
        )

        # Set accused player if someone got majority
        self.game_state.accused_player_id = result.winner_id

        if result.winner_id:
            accused = next(
                p for p in self.game_state.players
                if p.player_id == result.winner_id
            )
            await self.broadcast_system_message(
                f"{accused.name} has been put on trial!"
            )
        else:
            await self.broadcast_system_message(
                "No one was put on trial today."
            )

        # Run phase timer
        await self.phase_manager.run_phase_loop()

    async def run_defense_phase(self):
        """Run defense phase - accused player defends."""
        if not self.game_state.accused_player_id:
            return

        accused_id = self.game_state.accused_player_id
        accused = next(
            p for p in self.game_state.players
            if p.player_id == accused_id
        )

        logger.info(f"Defense phase: {accused.name} defends...")

        if not accused.is_human:
            # AI makes defense
            decision = await self.decision_engine.decide_defense(
                self.game_state,
                accused_id
            )

            defense_msg = ChatMessage(
                player_id=accused_id,
                player_name=accused.name,
                message=decision.defense_speech,
                phase=PhaseType.DEFENSE.value,
                day_number=self.game_state.current_day
            )

            self.game_state.all_chat_messages.append(defense_msg)

            await self.connection_manager.broadcast({
                "type": "chat_message",
                "message": defense_msg.model_dump()
            })

        # Run phase timer
        await self.phase_manager.run_phase_loop()

    async def run_judgment_phase(self):
        """Run judgment phase - vote guilty/innocent."""
        if not self.game_state.accused_player_id:
            return

        logger.info("Judgment phase: voting...")

        # Collect judgment votes from AIs
        ai_players = [
            p for p in self.game_state.players
            if p.is_alive and not p.is_human and p.player_id != self.game_state.accused_player_id
        ]

        vote_decisions = await self.decision_engine.batch_decide_votes(
            self.game_state,
            [p.player_id for p in ai_players],
            vote_type="judgment"
        )

        votes = [
            Vote(
                voter_id=player_id,
                target_id=self.game_state.accused_player_id,
                vote_type="judgment",
                guilty=decision.guilty
            )
            for player_id, decision in vote_decisions.items()
        ]

        # Process judgment
        result = self.voting_manager.process_judgment_votes(
            self.game_state,
            self.game_state.accused_player_id,
            votes
        )

        self.game_state.last_judgment_result = result

        # Run phase timer
        await self.phase_manager.run_phase_loop()

    async def run_judgment_results(self):
        """Announce judgment results."""
        if not self.game_state.last_judgment_result:
            return

        result = self.game_state.last_judgment_result
        verdict = result.verdict

        await self.broadcast_system_message(
            f"Verdict: {verdict.upper()} "
            f"({result.guilty_votes} guilty, {result.innocent_votes} innocent)"
        )

        # If guilty, player will be executed (handled in last words phase)
        # If innocent, clear accused
        if verdict == "innocent" or verdict == "tied":
            self.game_state.accused_player_id = None

        await asyncio.sleep(5)  # Show results

    async def run_last_words(self):
        """Run last words phase - executed player speaks."""
        if not self.game_state.accused_player_id:
            return

        if not self.game_state.last_judgment_result:
            return

        if self.game_state.last_judgment_result.verdict != "guilty":
            return

        accused_id = self.game_state.accused_player_id
        accused = next(
            p for p in self.game_state.players
            if p.player_id == accused_id
        )

        logger.info(f"Last words: {accused.name}...")

        # Execute player
        death = DeathInfo(
            player_id=accused_id,
            day_number=self.game_state.current_day,
            phase="Day",
            cause="Lynched",
            role_revealed=accused.role.name
        )

        accused.is_alive = False
        accused.death_info = death
        self.game_state.all_deaths.append(death)

        await self.broadcast_system_message(
            f"{accused.name} was lynched. They were a {accused.role.name}."
        )

        # Clear accused
        self.game_state.accused_player_id = None

        await asyncio.sleep(10)  # Time for last words

    async def transition_phase(self):
        """Transition to next phase."""
        next_phase = await self.phase_controller.transition_to_next_phase(
            self.game_state
        )

        self.game_state.current_phase = next_phase

        # Increment day if transitioning to night
        if next_phase.phase_type == PhaseType.NIGHT:
            self.game_state.current_day += 1

        # Broadcast phase change
        await self.ws_handler.broadcast_phase_change(
            next_phase.phase_type,
            next_phase.duration,
            next_phase.phase_number
        )

        # Update contexts
        self.context_manager.update_all_contexts(self.game_state)

    def check_victory(self) -> Optional[str]:
        """
        Check if any faction has won.

        Returns:
            Winning faction name or None
        """
        alive_players = [p for p in self.game_state.players if p.is_alive]

        if not alive_players:
            return "draw"

        # Count alive by faction
        alive_by_faction = {}
        for player in alive_players:
            faction = player.role.faction
            alive_by_faction[faction] = alive_by_faction.get(faction, 0) + 1

        # Town wins if all evils dead
        if alive_by_faction.get("Mafia", 0) == 0 and alive_by_faction.get("Neutral Killing", 0) == 0:
            return "Town"

        # Mafia wins if they equal or outnumber town
        mafia_count = alive_by_faction.get("Mafia", 0)
        town_count = alive_by_faction.get("Town", 0)

        if mafia_count >= town_count:
            return "Mafia"

        # No winner yet
        return None

    async def end_game(self, winner: str):
        """End the game and announce winner."""
        logger.info(f"Game over! Winner: {winner}")

        self.running = False

        await self.broadcast_system_message(f"Game Over! {winner} wins!")

        # Show all roles
        role_reveal = "Final roles:\n"
        for player in self.game_state.players:
            status = "ALIVE" if player.is_alive else "DEAD"
            role_reveal += f"  {player.name}: {player.role.name} [{status}]\n"

        await self.broadcast_system_message(role_reveal)

    async def broadcast_system_message(self, message: str):
        """Broadcast a system message to all players."""
        await self.connection_manager.broadcast({
            "type": "system_message",
            "message": message
        })

        logger.info(f"[SYSTEM] {message}")

    def on_phase_start(self, phase_type: PhaseType):
        """Callback when phase starts."""
        logger.info(f"Phase started: {phase_type.value}")

    def on_phase_end(self, phase_type: PhaseType):
        """Callback when phase ends."""
        logger.info(f"Phase ended: {phase_type.value}")
