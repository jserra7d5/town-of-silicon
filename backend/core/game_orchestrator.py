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
from ..core.game_persistence import GamePersistence
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

        # Persistence
        self.persistence = GamePersistence()

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

        # Main game loop with error recovery
        while self.running:
            try:
                # Check win conditions
                winner = self.check_victory()
                if winner:
                    await self.end_game(winner)
                    break

                # Run current phase
                await self.run_current_phase()

                # Transition to next phase
                await self.transition_phase()

            except Exception as e:
                logger.error(f"Critical error in game loop: {e}")
                # Try to broadcast error and continue
                try:
                    await self.broadcast_system_message(
                        f"Game error occurred: {str(e)[:100]}. Attempting to continue..."
                    )
                    # Force transition to next phase to recover
                    await self.transition_phase()
                except Exception as recovery_error:
                    logger.error(f"Failed to recover from game loop error: {recovery_error}")
                    # End game gracefully
                    await self.end_game("draw")
                    break

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

    async def run_mafia_night_chat(self):
        """Run Mafia coordination chat at start of night."""
        # Get alive Mafia members
        mafia_members = [
            p for p in self.game_state.players
            if p.is_alive and (
                p.role.faction.value == "Mafia" if hasattr(p.role.faction, 'value')
                else str(p.role.faction) == "Mafia"
            )
        ]

        if len(mafia_members) <= 1:
            # No coordination needed if only 1 or 0 Mafia left
            return

        logger.info(f"{len(mafia_members)} Mafia members coordinating...")

        # Give Mafia members a chance to chat
        await self.broadcast_system_message(
            f"The Mafia is meeting in secret..."
        )

        # AI Mafia members discuss strategy
        ai_mafia = [m for m in mafia_members if not m.is_human]

        for mafia in ai_mafia:
            # Decide if this Mafia member wants to say something
            decision = await self.decision_engine.decide_chat_message(
                self.game_state,
                mafia.player_id,
                context_hint="Mafia night chat - coordinate with other Mafia members"
            )

            if decision.should_speak and decision.message:
                mafia_chat_msg = ChatMessage(
                    player_id=mafia.player_id,
                    player_name=f"[MAFIA] {mafia.name}",
                    message=decision.message,
                    phase=PhaseType.NIGHT.value,
                    day_number=self.game_state.current_day,
                    visible_to_dead=False
                )

                self.game_state.all_chat_messages.append(mafia_chat_msg)

                # Broadcast to Mafia only
                await self.connection_manager.broadcast_to_mafia(
                    {
                        "type": "mafia_chat",
                        "message": mafia_chat_msg.model_dump()
                    },
                    self.game_state
                )

                logger.info(f"Mafia {mafia.name}: {decision.message}")

        # Short delay for human Mafia member to read/respond
        if any(m.is_human for m in mafia_members):
            await asyncio.sleep(5)

    async def run_current_phase(self):
        """Run the current phase with error handling."""
        phase_type = self.game_state.current_phase.phase_type

        logger.info(f"Running {phase_type.value} phase...")

        try:
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

        except Exception as e:
            logger.error(f"Error in {phase_type.value} phase: {e}")
            await self.broadcast_system_message(
                f"Error in {phase_type.value} phase. Skipping to next phase..."
            )
            # Phase will be transitioned by caller

    async def run_night_phase(self):
        """Run night phase - collect and resolve night actions."""
        logger.info("Night phase starting...")

        # Mafia coordination chat at start of night
        await self.run_mafia_night_chat()

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
            logger.info(f"Waiting for human player action...")

            # Wait up to 30 seconds for human action
            human_action = None
            try:
                human_action_data = await asyncio.wait_for(
                    self.ws_handler.action_queue.get(),
                    timeout=30.0
                )

                if human_action_data.get("type") == "night_action":
                    ability = human.role.abilities[0]
                    human_action = NightAction(
                        player_id=self.human_player_id,
                        ability=ability,
                        target_id=human_action_data.get("target_id"),
                        priority=ability.priority
                    )
                    actions.append(human_action)
                    logger.info(f"Human player submitted night action targeting {human_action.target_id}")

            except asyncio.TimeoutError:
                logger.warning("Human player did not submit action in time")
                # No action submitted - human skips their turn

        # Run phase timer
        await self.phase_manager.run_phase_loop()

        # Resolve night actions with error handling
        logger.info(f"Resolving {len(actions)} night actions...")
        try:
            summary = self.night_resolver.resolve_night(self.game_state, actions)
        except Exception as e:
            logger.error(f"Error resolving night actions: {e}")
            # Create empty summary to continue game
            from ..actions.night_actions import NightResolutionSummary
            summary = NightResolutionSummary()
            await self.broadcast_system_message(
                "An error occurred during night resolution. Continuing..."
            )

        # Apply deaths with error recovery
        for death in summary.deaths:
            try:
                player = next(
                    p for p in self.game_state.players
                    if p.player_id == death.player_id
                )
                player.is_alive = False
                player.death_info = death
                self.game_state.all_deaths.append(death)
            except StopIteration:
                logger.error(f"Could not find player {death.player_id} for death")
            except Exception as e:
                logger.error(f"Error applying death to player {death.player_id}: {e}")

        # Send action results to players
        for player_id, result in summary.action_results.items():
            try:
                await self.connection_manager.send_to_player(
                    {
                        "type": "night_action_result",
                        "result": result.model_dump()
                    },
                    player_id
                )
            except Exception as e:
                logger.error(f"Error sending action result to player {player_id}: {e}")

        # Announce deaths with error handling
        if summary.deaths:
            try:
                death_msg = f"{len(summary.deaths)} player(s) died last night: "
                death_names = []
                for d in summary.deaths:
                    try:
                        player = next(p for p in self.game_state.players if p.player_id == d.player_id)
                        death_names.append(player.name)
                    except StopIteration:
                        death_names.append(f"Player {d.player_id}")

                death_msg += ", ".join(death_names)
                await self.broadcast_system_message(death_msg)
            except Exception as e:
                logger.error(f"Error announcing deaths: {e}")

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

        # Collect accusation votes from AIs
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

        # Collect human vote if alive
        human = self.game_state.players[self.human_player_id]
        if human.is_alive:
            logger.info("Waiting for human player vote...")
            try:
                human_vote_data = await asyncio.wait_for(
                    self.ws_handler.action_queue.get(),
                    timeout=30.0
                )

                if human_vote_data.get("type") == "vote":
                    human_vote = Vote(
                        voter_id=self.human_player_id,
                        target_id=human_vote_data.get("target_id"),
                        vote_type="accusation"
                    )
                    votes.append(human_vote)
                    logger.info(f"Human voted for player {human_vote.target_id}")

            except asyncio.TimeoutError:
                logger.warning("Human player did not vote (abstain)")
                # Abstain - no vote added

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

        # Collect human judgment vote if alive and not accused
        human = self.game_state.players[self.human_player_id]
        if human.is_alive and human.player_id != self.game_state.accused_player_id:
            logger.info("Waiting for human player judgment vote...")
            try:
                human_vote_data = await asyncio.wait_for(
                    self.ws_handler.action_queue.get(),
                    timeout=20.0
                )

                if human_vote_data.get("type") == "vote":
                    human_vote = Vote(
                        voter_id=self.human_player_id,
                        target_id=self.game_state.accused_player_id,
                        vote_type="judgment",
                        guilty=human_vote_data.get("guilty")
                    )
                    votes.append(human_vote)
                    verdict = "guilty" if human_vote.guilty else "innocent"
                    logger.info(f"Human voted {verdict}")

            except asyncio.TimeoutError:
                logger.warning("Human player did not vote (abstain)")
                # Abstain - no vote added

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

        # Check for individual role wins (Jester, Executioner)
        await self.check_individual_wins(accused_id)

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

    async def check_individual_wins(self, lynched_player_id: int) -> None:
        """
        Check for individual role wins (Jester, Executioner) after a lynch.

        Args:
            lynched_player_id: ID of the player who was just lynched
        """
        lynched_player = next(
            (p for p in self.game_state.players if p.player_id == lynched_player_id),
            None
        )

        if not lynched_player:
            return

        # Check if Jester was lynched
        if lynched_player.role.id == "jester":
            logger.info(f"Jester {lynched_player.name} wins by getting lynched!")
            await self.broadcast_system_message(
                f"🎭 {lynched_player.name} was a Jester and wins by getting lynched!"
            )
            # Jester can choose to kill someone who voted guilty (not implemented yet)

        # Check if any Executioner's target was lynched
        for player in self.game_state.players:
            if player.role.id == "executioner" and player.is_alive:
                # Check if this player's target was lynched
                # Executioner target is stored in role metadata (not implemented in current model)
                # For now, we'll skip this - would need to add target tracking to Player model
                pass

    def check_victory(self) -> Optional[str]:
        """
        Check if any faction has won.

        Returns:
            Winning faction name or None
        """
        alive_players = [p for p in self.game_state.players if p.is_alive]

        if not alive_players:
            return "draw"

        # Count alive by faction and role
        alive_by_faction = {}
        alive_roles = {}

        for player in alive_players:
            faction = player.role.faction.value if hasattr(player.role.faction, 'value') else str(player.role.faction)
            role_id = player.role.id

            alive_by_faction[faction] = alive_by_faction.get(faction, 0) + 1
            alive_roles[role_id] = alive_roles.get(role_id, 0) + 1

        town_count = alive_by_faction.get("Town", 0)
        mafia_count = alive_by_faction.get("Mafia", 0)
        nk_count = alive_by_faction.get("Neutral Killing", 0)
        neutral_evil_count = alive_by_faction.get("Neutral Evil", 0)
        neutral_benign_count = alive_by_faction.get("Neutral Benign", 0)

        # Serial Killer solo win: Only Serial Killers (and maybe Survivors) remain
        if nk_count > 0 and town_count == 0 and mafia_count == 0 and neutral_evil_count == 0:
            # Check if only NK and neutral benign remain
            if alive_roles.get("serial_killer", 0) > 0:
                return "Serial Killer"
            elif alive_roles.get("arsonist", 0) > 0:
                return "Arsonist"
            elif alive_roles.get("werewolf", 0) > 0:
                return "Werewolf"
            elif alive_roles.get("juggernaut", 0) > 0:
                return "Juggernaut"

        # Mafia wins if they equal or outnumber town (and no NK left)
        if mafia_count > 0 and mafia_count >= town_count and nk_count == 0:
            return "Mafia"

        # Town wins if all evils dead (Mafia, NK, and non-benign neutrals)
        if mafia_count == 0 and nk_count == 0 and neutral_evil_count == 0:
            return "Town"

        # No winner yet
        return None

    async def end_game(self, winner: str):
        """End the game and announce winner."""
        logger.info(f"Game over! Winner: {winner}")

        self.running = False

        await self.broadcast_system_message(f"Game Over! {winner} wins!")

        # Determine individual winners
        individual_winners = []

        # Survivors win if they're alive
        for player in self.game_state.players:
            if player.is_alive and player.role.id == "survivor":
                individual_winners.append(f"{player.name} (Survivor)")
            # Amnesiac wins with the faction they remembered
            elif player.is_alive and player.role.id == "amnesiac":
                individual_winners.append(f"{player.name} (Amnesiac)")

        if individual_winners:
            await self.broadcast_system_message(
                f"Also won: {', '.join(individual_winners)}"
            )

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

        # Auto-save at end of each day
        if phase_type == PhaseType.NIGHT:
            try:
                self.save_game_auto()
            except Exception as e:
                logger.error(f"Auto-save failed: {e}")

    def save_game(self, save_name: Optional[str] = None) -> str:
        """
        Save current game state.

        Args:
            save_name: Optional name for the save

        Returns:
            Path to saved file
        """
        if not self.game_state:
            raise RuntimeError("No game to save")

        try:
            save_path = self.persistence.save_game(self.game_state, save_name)
            logger.success(f"Game saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Failed to save game: {e}")
            raise

    def save_game_auto(self) -> Optional[str]:
        """
        Create an autosave.

        Returns:
            Path to autosave file, or None if save failed
        """
        if not self.game_state:
            return None

        try:
            save_path = self.persistence.autosave(self.game_state)
            logger.info(f"Auto-saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Auto-save failed: {e}")
            return None

    async def load_game(self, save_name: str) -> GameState:
        """
        Load game from save file and restore state.

        Args:
            save_name: Name of save file to load

        Returns:
            Loaded game state
        """
        try:
            # Load game state
            loaded_state = self.persistence.load_game(save_name)

            # Set as current game state
            self.game_state = loaded_state
            self.ws_handler.set_game_state(loaded_state)

            # Find human player
            for player in loaded_state.players:
                if player.is_human:
                    self.human_player_id = player.player_id
                    break

            # Restore AI contexts
            self.context_manager.update_all_contexts(loaded_state)

            # Broadcast loaded state to all clients
            await self.ws_handler.broadcast_game_state()

            await self.broadcast_system_message(
                f"Game loaded from save (Day {loaded_state.current_day}, "
                f"{loaded_state.current_phase.phase_type.value})"
            )

            logger.success(f"Game loaded and restored")
            return loaded_state

        except Exception as e:
            logger.error(f"Failed to load game: {e}")
            raise

    def list_saves(self):
        """
        List all available save files.

        Returns:
            List of save metadata
        """
        return self.persistence.list_saves()
