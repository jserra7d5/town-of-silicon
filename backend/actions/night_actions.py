"""Night action resolution system with priority-based execution.

Actions are resolved in priority order (0 = highest priority):
0: Jailor jail
1: Escort/Consort roleblock
2: Transporter swap
3: Witch control
4: Protective (Doctor, Bodyguard)
5: Investigative (Sheriff, Investigator, Lookout)
6: Killing (Vigilante, Mafioso, Godfather, Serial Killer)
7: Deception (Framer, Janitor, Forger)
8: Other (Arsonist douse, etc.)
"""
from typing import Optional
from loguru import logger
from pydantic import BaseModel

from ..models.game import GameState
from ..models.player import Player, DeathInfo
from ..models.role import RoleAbility, AttackValue, DefenseValue


# ============================================================================
# Night Action Models
# ============================================================================

class NightAction(BaseModel):
    """A night action performed by a player."""
    player_id: int
    ability: RoleAbility
    target_id: Optional[int] = None
    priority: int = 8  # Default lowest priority
    successful: bool = True
    blocked: bool = False
    redirected_to: Optional[int] = None


class NightActionResult(BaseModel):
    """Result of a night action."""
    action: NightAction
    message: str  # Message shown to the acting player
    target_message: Optional[str] = None  # Message shown to the target
    investigation_result: Optional[str] = None  # For investigative roles
    kill_successful: bool = False
    kill_blocked_by: Optional[str] = None  # "defense", "heal", "bodyguard"


class NightResolutionSummary(BaseModel):
    """Summary of all night actions and their results."""
    deaths: list[DeathInfo] = []
    action_results: dict[int, NightActionResult] = {}  # player_id -> result
    roleblocked_players: set[int] = set()
    transported_pairs: list[tuple[int, int]] = []
    protected_players: set[int] = set()
    framed_players: set[int] = set()  # Players framed by Framer tonight
    visitors: dict[int, list[int]] = {}  # target_id -> [visitor_ids] for Lookout


# ============================================================================
# Night Action Resolver
# ============================================================================

class NightActionResolver:
    """
    Resolves night actions in priority order.

    Handles complex interactions: roleblocks, transports, protection, etc.
    """

    def __init__(self):
        self.summary = NightResolutionSummary()

    def resolve_night(
        self,
        game_state: GameState,
        actions: list[NightAction]
    ) -> NightResolutionSummary:
        """
        Resolve all night actions in priority order.

        Args:
            game_state: Current game state
            actions: All night actions submitted

        Returns:
            Summary of night resolution
        """
        logger.info(f"Resolving night with {len(actions)} actions")

        # Reset summary
        self.summary = NightResolutionSummary()

        # Sort actions by priority (lower = higher priority)
        actions.sort(key=lambda a: a.priority)

        # Process each priority level
        current_priority = -1
        for action in actions:
            if action.priority != current_priority:
                current_priority = action.priority
                logger.info(f"Processing priority {current_priority} actions")

            # Check if actor is roleblocked
            if action.player_id in self.summary.roleblocked_players:
                logger.info(f"Player {action.player_id} is roleblocked, action fails")
                action.blocked = True
                self.summary.action_results[action.player_id] = NightActionResult(
                    action=action,
                    message="You were roleblocked!"
                )
                continue

            # Process action based on type
            result = self._process_action(game_state, action)
            self.summary.action_results[action.player_id] = result

        logger.info(
            f"Night resolution complete: {len(self.summary.deaths)} deaths, "
            f"{len(self.summary.roleblocked_players)} roleblocks"
        )

        return self.summary

    def _process_action(
        self,
        game_state: GameState,
        action: NightAction
    ) -> NightActionResult:
        """Process a single night action."""
        ability_name = action.ability.name.lower()

        # Handle transport redirection
        actual_target = self._resolve_transport(action.target_id)

        if actual_target != action.target_id:
            logger.info(
                f"Player {action.player_id} redirected from {action.target_id} "
                f"to {actual_target} by Transporter"
            )
            action.redirected_to = actual_target

        # Track visitor (for Lookout) - track after transport resolution
        if actual_target is not None:
            self._track_visitor(action.player_id, actual_target)

        # Route to specific handler
        if ability_name in ["escort", "consort"]:
            return self._handle_roleblock(game_state, action, actual_target)

        elif ability_name == "transport":
            return self._handle_transport(game_state, action)

        elif ability_name in ["heal", "protect"]:
            return self._handle_protect(game_state, action, actual_target)

        elif ability_name in ["interrogate", "investigate", "watch"]:
            return self._handle_investigate(game_state, action, actual_target)

        elif ability_name in ["attack", "shoot", "assassinate"]:
            return self._handle_attack(game_state, action, actual_target)

        elif ability_name == "frame":
            return self._handle_frame(game_state, action, actual_target)

        elif ability_name == "clean":
            return self._handle_clean(game_state, action, actual_target)

        else:
            logger.warning(f"Unknown ability: {ability_name}")
            return NightActionResult(
                action=action,
                message="Your action was processed."
            )

    def _handle_roleblock(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Escort/Consort roleblock."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to roleblock anyone."
            )

        # Add to roleblocked set
        self.summary.roleblocked_players.add(target_id)

        target = self._get_player(game_state, target_id)

        logger.info(f"Player {action.player_id} roleblocked {target_id}")

        return NightActionResult(
            action=action,
            message=f"You roleblocked {target.name}.",
            target_message="You were roleblocked!"
        )

    def _handle_transport(
        self,
        game_state: GameState,
        action: NightAction
    ) -> NightActionResult:
        """Handle Transporter swap."""
        # Transport needs two targets (stored in ability metadata)
        # For now, simplified: target_id is first, second target from action
        target1 = action.target_id
        # In full implementation, would get second target from action
        # For now, just record the transport

        if target1 is None:
            return NightActionResult(
                action=action,
                message="You decided not to transport anyone."
            )

        logger.info(f"Player {action.player_id} transported {target1}")

        return NightActionResult(
            action=action,
            message=f"You transported players successfully."
        )

    def _handle_protect(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Doctor/Bodyguard protection."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to protect anyone."
            )

        # Add to protected set
        self.summary.protected_players.add(target_id)

        target = self._get_player(game_state, target_id)

        logger.info(f"Player {action.player_id} protected {target_id}")

        return NightActionResult(
            action=action,
            message=f"You protected {target.name}."
        )

    def _handle_investigate(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle investigative actions."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to investigate anyone."
            )

        target = self._get_player(game_state, target_id)
        ability_name = action.ability.name.lower()

        # Framing is checked in _get_sheriff_result() for Sheriff investigations

        if ability_name == "interrogate":  # Sheriff
            # Sheriff gets "Mafia/SK" or "Not Suspicious"
            result = self._get_sheriff_result(target)
            investigation_type = "sheriff"

        elif ability_name == "investigate":  # Investigator
            # Investigator gets role grouping
            result = self._get_investigator_result(target)
            investigation_type = "investigator"

        elif ability_name == "watch":  # Lookout
            # Lookout sees who visited target
            result = self._get_lookout_result(game_state, target_id)
            investigation_type = "lookout"

        else:
            result = "Your investigation was inconclusive."
            investigation_type = "unknown"

        logger.info(f"Player {action.player_id} investigated {target_id}: {result}")

        # Store investigation result for AI memory
        from ..models.player import InvestigationResult
        investigator = self._get_player(game_state, action.player_id)
        investigator.investigation_results.append(
            InvestigationResult(
                night=game_state.current_day,
                target_id=target_id,
                target_name=target.name,
                investigation_type=investigation_type,
                result=result
            )
        )

        return NightActionResult(
            action=action,
            message=f"Investigation result: {result}",
            investigation_result=result
        )

    def _handle_attack(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle killing actions."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to attack anyone."
            )

        target = self._get_player(game_state, target_id)

        # Check if target is protected
        if target_id in self.summary.protected_players:
            logger.info(
                f"Player {action.player_id} attacked {target_id} but they were protected"
            )
            return NightActionResult(
                action=action,
                message=f"Your target was protected!",
                kill_blocked_by="heal"
            )

        # Check defense vs attack
        attack = action.ability.attack or AttackValue.NONE
        defense = target.role.defense

        if self._can_kill(attack, defense):
            # Kill successful
            death = DeathInfo(
                player_id=target_id,
                day_number=game_state.current_day,
                phase="Night",
                cause=f"Killed by {action.ability.name}",
                killer_id=action.player_id
            )

            self.summary.deaths.append(death)

            logger.info(
                f"Player {action.player_id} killed {target_id} with {action.ability.name}"
            )

            return NightActionResult(
                action=action,
                message=f"Your target has died!",
                kill_successful=True
            )

        else:
            # Defense too high
            logger.info(
                f"Player {action.player_id} attacked {target_id} but defense was too high"
            )
            return NightActionResult(
                action=action,
                message=f"Your target's defense was too high!",
                kill_blocked_by="defense"
            )

    def _handle_frame(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Framer action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to frame anyone."
            )

        target = self._get_player(game_state, target_id)

        # Add target to framed players set - affects Sheriff investigations tonight
        self.summary.framed_players.add(target_id)

        logger.info(f"Player {action.player_id} framed {target_id}")

        return NightActionResult(
            action=action,
            message=f"You framed {target.name}."
        )

    def _handle_clean(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Janitor clean action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to clean anyone."
            )

        # Janitor cleans a dead body (hides role)
        # In full implementation, would check if target died tonight
        # and mark them as cleaned

        logger.info(f"Player {action.player_id} cleaned {target_id}")

        return NightActionResult(
            action=action,
            message=f"You will clean your target if they die."
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _track_visitor(self, player_id: int, target_id: Optional[int]) -> None:
        """Track that player_id visited target_id (for Lookout)."""
        if target_id is None:
            return

        if target_id not in self.summary.visitors:
            self.summary.visitors[target_id] = []

        self.summary.visitors[target_id].append(player_id)

    def _resolve_transport(self, target_id: Optional[int]) -> Optional[int]:
        """Resolve transport redirection."""
        if target_id is None:
            return None

        for pair in self.summary.transported_pairs:
            if target_id == pair[0]:
                return pair[1]
            elif target_id == pair[1]:
                return pair[0]

        return target_id

    def _get_player(self, game_state: GameState, player_id: int) -> Player:
        """Get player by ID."""
        return next(p for p in game_state.players if p.player_id == player_id)

    def _can_kill(self, attack: AttackValue, defense: DefenseValue) -> bool:
        """Check if an attack can kill given defense."""
        attack_values = {
            AttackValue.NONE: 0,
            AttackValue.BASIC: 1,
            AttackValue.POWERFUL: 2,
            AttackValue.UNSTOPPABLE: 3
        }

        defense_values = {
            DefenseValue.NONE: 0,
            DefenseValue.BASIC: 1,
            DefenseValue.POWERFUL: 2,
            DefenseValue.INVINCIBLE: 3
        }

        return attack_values[attack] > defense_values[defense]

    def _get_sheriff_result(self, target: Player) -> str:
        """Get Sheriff investigation result."""
        role = target.role

        # Check if target is framed tonight - framed players appear as Mafia
        if target.player_id in self.summary.framed_players:
            return f"{target.name} is a member of the Mafia!"

        # Sheriff detects Mafia and Serial Killer
        if role.faction in ["Mafia"]:
            return f"{target.name} is a member of the Mafia!"

        if role.id == "serial_killer":
            return f"{target.name} is a Serial Killer!"

        return f"{target.name} is not suspicious."

    def _get_investigator_result(self, target: Player) -> str:
        """Get Investigator result (role grouping)."""
        # Investigator gets 3-4 possible roles
        # This is simplified - full game has specific groupings

        role_groups = {
            "sheriff": ["Sheriff", "Executioner", "Werewolf"],
            "doctor": ["Doctor", "Disguiser", "Serial Killer"],
            "investigator": ["Investigator", "Consigliere", "Mayor"],
            "godfather": ["Godfather", "Bodyguard"],
            "framer": ["Framer", "Vampire", "Jester"],
            "lookout": ["Lookout", "Forger"],
            # Add more as needed
        }

        role_id = target.role.id
        group = role_groups.get(role_id, ["Citizen"])

        return f"{target.name}'s role is one of: {', '.join(group)}"

    def _get_lookout_result(
        self,
        game_state: GameState,
        target_id: int
    ) -> str:
        """Get Lookout result (who visited target)."""
        target = self._get_player(game_state, target_id)

        # Get visitors from tracking
        visitors = self.summary.visitors.get(target_id, [])

        if not visitors:
            return f"No one visited {target.name}."

        visitor_names = [self._get_player(game_state, v).name for v in visitors]
        return f"Players who visited {target.name}: {', '.join(visitor_names)}"
