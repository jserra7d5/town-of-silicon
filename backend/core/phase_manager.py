"""Phase management system with adaptive timing for AI processing."""
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
from loguru import logger

from ..models.game import GamePhase, PhaseType
from ..config.settings import settings


class AdaptivePhaseTimer:
    """
    Adaptive timer that extends phases based on AI activity.

    With 64K context and 20B model, AIs need more time than smaller models.
    This system automatically extends phases when needed.
    """

    def __init__(
        self,
        base_duration: float,
        max_extensions: int = 6,
        extension_increment: float = 5.0
    ):
        self.base_duration = base_duration
        self.remaining_time = base_duration
        self.max_extensions = max_extensions
        self.extension_increment = extension_increment
        self.extensions_used = 0

        # AI activity tracking
        self.pending_ais: set[int] = set()
        self.recent_messages: list[datetime] = []

    def tick(self, delta_time: float) -> bool:
        """
        Update timer.

        Args:
            delta_time: Time elapsed since last tick (seconds)

        Returns:
            True if phase should end, False otherwise
        """
        self.remaining_time -= delta_time

        # Check if we should extend
        if self.should_extend():
            self.extend()

        return self.remaining_time <= 0

    def should_extend(self) -> bool:
        """Check if phase should be extended."""
        # Don't extend if max extensions reached
        if self.extensions_used >= self.max_extensions:
            return False

        # Extend if AIs still processing and time running low
        if self.pending_ais and self.remaining_time < 5.0:
            return True

        # Extend if chat is very active
        if self.is_chat_active() and self.remaining_time < 3.0:
            return True

        return False

    def extend(self) -> None:
        """Extend the phase timer."""
        self.remaining_time += self.extension_increment
        self.extensions_used += 1

        logger.info(
            f"Phase extended (+{self.extension_increment}s), "
            f"{self.extensions_used}/{self.max_extensions} used"
        )

    def is_chat_active(self) -> bool:
        """Check if chat has recent activity."""
        now = datetime.now()
        recent = [
            t for t in self.recent_messages
            if (now - t).total_seconds() < 5.0
        ]
        return len(recent) >= 3  # 3+ messages in last 5 seconds

    def mark_ai_pending(self, ai_id: int) -> None:
        """Mark an AI as still processing."""
        self.pending_ais.add(ai_id)

    def mark_ai_done(self, ai_id: int) -> None:
        """Mark an AI as done processing."""
        self.pending_ais.discard(ai_id)

    def record_message(self) -> None:
        """Record a chat message for activity tracking."""
        self.recent_messages.append(datetime.now())

        # Keep only recent messages
        cutoff = datetime.now() - timedelta(seconds=30)
        self.recent_messages = [
            t for t in self.recent_messages if t > cutoff
        ]


class PhaseManager:
    """
    Manages game phases with adaptive timing.

    Handles transitions between phases and manages phase timers.
    """

    def __init__(self):
        self.current_phase: Optional[GamePhase] = None
        self.timer: Optional[AdaptivePhaseTimer] = None
        self.running = False

        # Phase transition callbacks
        self.on_phase_start: Optional[Callable[[PhaseType], None]] = None
        self.on_phase_end: Optional[Callable[[PhaseType], None]] = None

        # Performance tracking
        self.phase_performance: dict[str, list[float]] = {}

    def start_phase(self, phase_type: PhaseType, duration: Optional[float] = None) -> GamePhase:
        """
        Start a new phase.

        Args:
            phase_type: Type of phase to start
            duration: Duration in seconds (None = use default)

        Returns:
            New GamePhase object
        """
        # Use default duration if not specified
        if duration is None:
            duration = self._get_default_duration(phase_type)

        # Adjust duration based on performance history
        if settings.enable_auto_calibration:
            duration = self._calibrate_duration(phase_type, duration)

        # Create phase
        self.current_phase = GamePhase(
            phase_type=phase_type,
            phase_number=self._get_phase_number(phase_type),
            duration=duration,
            remaining_time=duration,
            max_extensions=self._get_max_extensions(phase_type)
        )

        # Create timer
        self.timer = AdaptivePhaseTimer(
            base_duration=duration,
            max_extensions=self.current_phase.max_extensions,
            extension_increment=5.0
        )

        logger.info(
            f"Starting {phase_type.value} phase "
            f"(duration: {duration}s, max_extensions: {self.current_phase.max_extensions})"
        )

        # Call callback
        if self.on_phase_start:
            self.on_phase_start(phase_type)

        return self.current_phase

    async def run_phase_loop(self) -> None:
        """
        Run the phase timer loop.

        Call this in an asyncio task to manage phase timing.
        """
        self.running = True
        start_time = datetime.now()

        while self.running:
            await asyncio.sleep(0.1)  # 10 Hz tick rate

            if self.timer:
                # Update timer
                phase_complete = self.timer.tick(0.1)

                # Update remaining time in phase
                if self.current_phase:
                    self.current_phase.remaining_time = self.timer.remaining_time
                    self.current_phase.extensions_used = self.timer.extensions_used

                # Check if phase should end
                if phase_complete:
                    # Record performance
                    elapsed = (datetime.now() - start_time).total_seconds()
                    self._record_phase_performance(
                        self.current_phase.phase_type.value,
                        elapsed
                    )

                    logger.info(
                        f"Phase {self.current_phase.phase_type.value} complete "
                        f"(took {elapsed:.1f}s)"
                    )

                    # Call callback
                    if self.on_phase_end and self.current_phase:
                        self.on_phase_end(self.current_phase.phase_type)

                    break

    def stop_phase(self) -> None:
        """Stop the current phase."""
        self.running = False

    def mark_ai_pending(self, ai_id: int) -> None:
        """Mark an AI as still processing (for adaptive timing)."""
        if self.timer:
            self.timer.mark_ai_pending(ai_id)

    def mark_ai_done(self, ai_id: int) -> None:
        """Mark an AI as done processing."""
        if self.timer:
            self.timer.mark_ai_done(ai_id)

    def record_message(self) -> None:
        """Record a chat message for activity tracking."""
        if self.timer:
            self.timer.record_message()

    def _get_default_duration(self, phase_type: PhaseType) -> float:
        """Get default duration for a phase type."""
        durations = {
            PhaseType.PREGAME: 3.0,
            PhaseType.NIGHT: settings.night_base_duration,
            PhaseType.DAY_DISCUSSION: settings.day_base_duration,
            PhaseType.DEFENSE: settings.defense_duration,
            PhaseType.JUDGMENT: settings.judgment_duration,
            PhaseType.JUDGMENT_RESULTS: 5.0,
            PhaseType.LAST_WORDS: 10.0,
            PhaseType.POSTGAME: float('inf')
        }
        return durations.get(phase_type, 30.0)

    def _get_max_extensions(self, phase_type: PhaseType) -> int:
        """Get maximum extensions allowed for a phase type."""
        if not settings.ai_enable_extensions:
            return 0

        # Night phase needs more extensions (AI processing)
        if phase_type == PhaseType.NIGHT:
            return settings.ai_max_extensions

        # Day phases can have some extensions
        if phase_type == PhaseType.DAY_DISCUSSION:
            return 6

        # Other phases don't extend
        return 0

    def _get_phase_number(self, phase_type: PhaseType) -> int:
        """Get sequential phase number."""
        # This would be maintained by game state
        # For now, return 0
        return 0

    def _calibrate_duration(self, phase_type: PhaseType, base_duration: float) -> float:
        """
        Calibrate duration based on performance history.

        If phases consistently run long, increase base duration.
        """
        phase_name = phase_type.value

        if phase_name not in self.phase_performance:
            return base_duration

        # Get recent performance
        recent = self.phase_performance[phase_name][-5:]  # Last 5 phases

        if not recent:
            return base_duration

        # Calculate average actual time
        avg_time = sum(recent) / len(recent)

        # If consistently running long, increase base duration
        if avg_time > base_duration * 1.2:  # 20% over
            new_duration = min(avg_time + 5.0, base_duration * 2.0)  # Cap at 2x
            logger.info(
                f"Calibrating {phase_name}: {base_duration}s → {new_duration}s "
                f"(avg actual: {avg_time:.1f}s)"
            )
            return new_duration

        return base_duration

    def _record_phase_performance(self, phase_name: str, duration: float) -> None:
        """Record how long a phase actually took."""
        if phase_name not in self.phase_performance:
            self.phase_performance[phase_name] = []

        self.phase_performance[phase_name].append(duration)

        # Keep only recent history
        if len(self.phase_performance[phase_name]) > 10:
            self.phase_performance[phase_name] = self.phase_performance[phase_name][-10:]


class PhaseTransitionController:
    """
    Controls transitions between game phases.

    Determines which phase comes next based on game state.
    """

    def __init__(self, phase_manager: PhaseManager):
        self.phase_manager = phase_manager

    def determine_next_phase(
        self,
        current_phase: PhaseType,
        game_state
    ) -> PhaseType:
        """
        Determine the next phase based on current phase and game state.

        Args:
            current_phase: Current phase
            game_state: Current game state

        Returns:
            Next phase type
        """
        # Pregame → Night 1
        if current_phase == PhaseType.PREGAME:
            return PhaseType.NIGHT

        # Night → Day (with announcements)
        if current_phase == PhaseType.NIGHT:
            return PhaseType.DAY_DISCUSSION

        # Day discussion → Defense (if vote successful) or Night (if no vote)
        if current_phase == PhaseType.DAY_DISCUSSION:
            if game_state.accused_player_id is not None:
                return PhaseType.DEFENSE
            else:
                return PhaseType.NIGHT

        # Defense → Judgment
        if current_phase == PhaseType.DEFENSE:
            return PhaseType.JUDGMENT

        # Judgment → Results
        if current_phase == PhaseType.JUDGMENT:
            return PhaseType.JUDGMENT_RESULTS

        # Results → Last Words (if guilty) or Day Discussion (if innocent)
        if current_phase == PhaseType.JUDGMENT_RESULTS:
            # This would check the verdict from game state
            # For now, assume guilty
            return PhaseType.LAST_WORDS

        # Last Words → Night
        if current_phase == PhaseType.LAST_WORDS:
            return PhaseType.NIGHT

        # Default: stay in current phase
        logger.warning(f"No transition defined for {current_phase}")
        return current_phase

    async def transition_to_next_phase(self, game_state) -> GamePhase:
        """
        Transition to the next phase.

        Args:
            game_state: Current game state

        Returns:
            New GamePhase
        """
        if not self.phase_manager.current_phase:
            # Start with pregame
            return self.phase_manager.start_phase(PhaseType.PREGAME)

        current = self.phase_manager.current_phase.phase_type
        next_phase = self.determine_next_phase(current, game_state)

        logger.info(f"Transitioning: {current.value} → {next_phase.value}")

        # Stop current phase
        self.phase_manager.stop_phase()

        # Start next phase
        return self.phase_manager.start_phase(next_phase)
