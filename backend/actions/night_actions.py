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

        # Clear temporary night-specific states
        self._clear_night_states(game_state)

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
        if ability_name == "jail":
            return self._handle_jail(game_state, action, actual_target)

        elif ability_name == "execute":
            return self._handle_execute(game_state, action)

        elif ability_name == "alert":
            return self._handle_alert(game_state, action)

        elif ability_name == "vest":
            return self._handle_vest(game_state, action)

        elif ability_name == "blackmail":
            return self._handle_blackmail(game_state, action, actual_target)

        elif ability_name == "douse":
            return self._handle_douse(game_state, action, actual_target)

        elif ability_name == "ignite":
            return self._handle_ignite(game_state, action)

        elif ability_name == "maul":
            return self._handle_maul(game_state, action, actual_target)

        elif ability_name == "control":
            return self._handle_control(game_state, action)

        elif ability_name in ["escort", "consort", "roleblock"]:
            return self._handle_roleblock(game_state, action, actual_target)

        elif ability_name == "transport":
            return self._handle_transport(game_state, action)

        elif ability_name in ["heal", "protect"]:
            return self._handle_protect(game_state, action, actual_target)

        elif ability_name in ["guard"]:
            return self._handle_guard(game_state, action, actual_target)

        elif ability_name in ["interrogate", "investigate", "watch"]:
            return self._handle_investigate(game_state, action, actual_target)

        elif ability_name == "bug":
            return self._handle_spy(game_state, action, actual_target)

        elif ability_name == "seance":
            return self._handle_medium_seance(game_state, action, actual_target)

        elif ability_name == "revive":
            return self._handle_retributionist_revive(game_state, action, actual_target)

        elif ability_name == "disguise":
            return self._handle_disguise(game_state, action, actual_target)

        elif ability_name == "hypnotize":
            return self._handle_hypnotize(game_state, action, actual_target)

        elif ability_name == "rampage":
            return self._handle_juggernaut_rampage(game_state, action, actual_target)

        elif ability_name == "forge":
            return self._handle_forge_will(game_state, action, actual_target)

        elif ability_name == "remember":
            return self._handle_amnesiac_remember(game_state, action, actual_target)

        elif ability_name == "haunt":
            return self._handle_jester_haunt(game_state, action, actual_target)

        elif ability_name in ["attack", "shoot", "assassinate", "kill"]:
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

        target = self._get_player(game_state, target_id)

        # Check if target is Serial Killer - they kill roleblockers
        if target.role.id == "serial_killer":
            # Serial Killer kills the roleblocker
            death = DeathInfo(
                player_id=action.player_id,
                day_number=game_state.current_day,
                phase="Night",
                cause="Killed by Serial Killer",
                killer_id=target_id
            )
            self.summary.deaths.append(death)

            logger.info(f"Serial Killer {target_id} killed roleblocker {action.player_id}")

            return NightActionResult(
                action=action,
                message=f"You were killed by a Serial Killer!",
                target_message="You were roleblocked but you killed your attacker!",
                kill_successful=True
            )

        # Check if target is immune to roleblocking
        if "roleblock" in target.role.immunities:
            return NightActionResult(
                action=action,
                message=f"{target.name} is immune to roleblocking!",
                target_message="Someone tried to roleblock you but you are immune!"
            )

        # Add to roleblocked set
        self.summary.roleblocked_players.add(target_id)

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

        attacker = self._get_player(game_state, action.player_id)
        ability_name = action.ability.name.lower()

        # Check if this ability has limited uses (e.g., Vigilante Shoot)
        if not self._check_ability_uses(attacker, ability_name):
            return NightActionResult(
                action=action,
                message=f"You have no {ability_name}s remaining!"
            )

        # Decrement uses (attack attempt counts even if blocked)
        self._decrement_ability_uses(attacker, ability_name)

        target = self._get_player(game_state, target_id)

        # Check if target is an alerted Veteran - they kill all visitors
        if target.is_alerted:
            # Veteran kills the attacker
            death = DeathInfo(
                player_id=action.player_id,
                day_number=game_state.current_day,
                phase="Night",
                cause="Killed by Veteran",
                killer_id=target_id
            )
            self.summary.deaths.append(death)

            logger.info(f"Alerted Veteran {target_id} killed attacker {action.player_id}")

            return NightActionResult(
                action=action,
                message=f"You were killed by a Veteran on alert!",
                kill_successful=False
            )

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

        janitor = self._get_player(game_state, action.player_id)

        # Check if Janitor has cleans remaining
        if not self._check_ability_uses(janitor, "clean"):
            return NightActionResult(
                action=action,
                message="You have no cleans remaining!"
            )

        target = self._get_player(game_state, target_id)

        # Mark target for cleaning - will be applied if they die tonight
        # Check if target dies in the deaths list and mark as cleaned
        for death in self.summary.deaths:
            if death.player_id == target_id:
                death.cleaned = True
                # Decrement uses only if cleaning is successful
                self._decrement_ability_uses(janitor, "clean")
                logger.info(f"Janitor {action.player_id} cleaned {target_id}")
                return NightActionResult(
                    action=action,
                    message=f"You cleaned {target.name}'s body. Their role and will are hidden."
                )

        # Target didn't die, cleaning saved for later
        # Note: Use is not decremented if target doesn't die
        logger.info(f"Janitor {action.player_id} prepared to clean {target_id}")

        return NightActionResult(
            action=action,
            message=f"You will clean {target.name} if they die tonight."
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

    # ========================================================================
    # New Role Ability Handlers
    # ========================================================================

    def _handle_jail(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Jailor jail action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to jail anyone."
            )

        target = self._get_player(game_state, target_id)

        # Jail roleblocks and protects the target
        target.in_jail = True
        target.jailed_by = action.player_id
        self.summary.roleblocked_players.add(target_id)
        self.summary.protected_players.add(target_id)

        logger.info(f"Jailor {action.player_id} jailed {target_id}")

        return NightActionResult(
            action=action,
            message=f"You jailed {target.name}. They are roleblocked and protected.",
            target_message="You were hauled off to jail!"
        )

    def _handle_execute(
        self,
        game_state: GameState,
        action: NightAction
    ) -> NightActionResult:
        """Handle Jailor execute action."""
        jailor = self._get_player(game_state, action.player_id)

        # Check if Jailor has executions remaining
        if not self._check_ability_uses(jailor, "execute"):
            return NightActionResult(
                action=action,
                message="You have no executions remaining!"
            )

        # Find jailed player
        jailed_player = None
        for player in game_state.players:
            if player.in_jail and player.jailed_by == action.player_id:
                jailed_player = player
                break

        if not jailed_player:
            return NightActionResult(
                action=action,
                message="You have no one in jail to execute."
            )

        # Decrement uses (will be set to 0 if executing Town)
        self._decrement_ability_uses(jailor, "execute")

        # Execute the jailed player (Unstoppable attack)
        death = DeathInfo(
            player_id=jailed_player.player_id,
            day_number=game_state.current_day,
            phase="Night",
            cause="Executed by Jailor",
            killer_id=action.player_id
        )

        self.summary.deaths.append(death)

        logger.info(f"Jailor {action.player_id} executed {jailed_player.player_id}")

        # Check if executed a Town member (Jailor loses ALL executions)
        if jailed_player.role.faction.value == "Town" if hasattr(jailed_player.role.faction, 'value') else str(jailed_player.role.faction) == "Town":
            self._set_ability_uses(jailor, "execute", 0)
            return NightActionResult(
                action=action,
                message=f"You executed {jailed_player.name}, but they were TOWN! You have lost your executions.",
                kill_successful=True
            )

        return NightActionResult(
            action=action,
            message=f"You executed {jailed_player.name}.",
            kill_successful=True
        )

    def _handle_alert(
        self,
        game_state: GameState,
        action: NightAction
    ) -> NightActionResult:
        """Handle Veteran alert action."""
        veteran = self._get_player(game_state, action.player_id)

        # Check if Veteran has alerts remaining
        if not self._check_ability_uses(veteran, "alert"):
            return NightActionResult(
                action=action,
                message="You have no alerts remaining!"
            )

        veteran.is_alerted = True

        # Decrement uses
        self._decrement_ability_uses(veteran, "alert")

        logger.info(f"Veteran {action.player_id} is on alert")

        return NightActionResult(
            action=action,
            message="You are on alert! You will attack anyone who visits you."
        )

    def _handle_vest(
        self,
        game_state: GameState,
        action: NightAction
    ) -> NightActionResult:
        """Handle Survivor vest action."""
        survivor = self._get_player(game_state, action.player_id)

        # Check if Survivor has vests remaining
        if not self._check_ability_uses(survivor, "vest"):
            return NightActionResult(
                action=action,
                message="You have no bulletproof vests remaining!"
            )

        survivor.is_vested = True

        # Add to protected players (basic defense)
        self.summary.protected_players.add(action.player_id)

        # Decrement uses
        self._decrement_ability_uses(survivor, "vest")

        logger.info(f"Survivor {action.player_id} put on a vest")

        return NightActionResult(
            action=action,
            message="You put on a bulletproof vest. You have Basic defense tonight."
        )

    def _handle_blackmail(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Blackmailer blackmail action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to blackmail anyone."
            )

        target = self._get_player(game_state, target_id)
        target.is_blackmailed = True
        target.can_speak = False

        logger.info(f"Blackmailer {action.player_id} blackmailed {target_id}")

        return NightActionResult(
            action=action,
            message=f"You blackmailed {target.name}. They cannot speak tomorrow.",
            target_message="Someone threatened you last night! You cannot speak during the day."
        )

    def _handle_douse(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Arsonist douse action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to douse anyone."
            )

        target = self._get_player(game_state, target_id)
        target.is_doused = True

        logger.info(f"Arsonist {action.player_id} doused {target_id}")

        return NightActionResult(
            action=action,
            message=f"You doused {target.name} in gasoline."
        )

    def _handle_ignite(
        self,
        game_state: GameState,
        action: NightAction
    ) -> NightActionResult:
        """Handle Arsonist ignite action."""
        # Kill all doused players
        kills = 0
        for player in game_state.players:
            if player.is_doused and player.is_alive:
                # Unstoppable attack
                death = DeathInfo(
                    player_id=player.player_id,
                    day_number=game_state.current_day,
                    phase="Night",
                    cause="Burned by Arsonist",
                    killer_id=action.player_id
                )
                self.summary.deaths.append(death)
                player.is_doused = False  # Clear douse status
                kills += 1

        logger.info(f"Arsonist {action.player_id} ignited {kills} players")

        if kills == 0:
            return NightActionResult(
                action=action,
                message="You ignited, but no one was doused."
            )

        return NightActionResult(
            action=action,
            message=f"You ignited {kills} player(s)!",
            kill_successful=True
        )

    def _handle_maul(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Werewolf maul action (full moon only)."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to maul anyone."
            )

        werewolf = self._get_player(game_state, action.player_id)

        # Check cooldown (every other night)
        if not self._check_cooldown(werewolf, action.ability, game_state.current_day):
            return NightActionResult(
                action=action,
                message="It's not a full moon tonight. You cannot transform."
            )

        # Update cooldown
        self._update_cooldown(werewolf, "maul", game_state.current_day)

        target = self._get_player(game_state, target_id)

        # Kill target with Powerful attack
        attack = AttackValue.POWERFUL
        defense = target.role.defense

        deaths_caused = []

        if self._can_kill(attack, defense):
            death = DeathInfo(
                player_id=target_id,
                day_number=game_state.current_day,
                phase="Night",
                cause="Mauled by Werewolf",
                killer_id=action.player_id
            )
            self.summary.deaths.append(death)
            deaths_caused.append(target.name)

        # Also kill all visitors to the target
        visitors = self.summary.visitors.get(target_id, [])
        for visitor_id in visitors:
            if visitor_id == action.player_id:
                continue  # Don't kill self

            visitor = self._get_player(game_state, visitor_id)
            if self._can_kill(attack, visitor.role.defense):
                death = DeathInfo(
                    player_id=visitor_id,
                    day_number=game_state.current_day,
                    phase="Night",
                    cause="Mauled by Werewolf",
                    killer_id=action.player_id
                )
                self.summary.deaths.append(death)
                deaths_caused.append(visitor.name)

        logger.info(f"Werewolf {action.player_id} mauled {len(deaths_caused)} players")

        if deaths_caused:
            return NightActionResult(
                action=action,
                message=f"You transformed and mauled: {', '.join(deaths_caused)}",
                kill_successful=True
            )
        else:
            return NightActionResult(
                action=action,
                message="You transformed but your targets had too much defense."
            )

    def _handle_control(
        self,
        game_state: GameState,
        action: NightAction
    ) -> NightActionResult:
        """Handle Witch control action."""
        # Witch needs two targets: controlled player and new target
        # This is complex - requires UI to select two targets
        # For now, simplified implementation
        logger.warning("Witch control not fully implemented - requires dual target selection")

        return NightActionResult(
            action=action,
            message="You controlled your target (simplified implementation)."
        )

    def _handle_guard(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Bodyguard guard action (protect + counterattack)."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to guard anyone."
            )

        target = self._get_player(game_state, target_id)

        # Give target powerful defense
        self.summary.protected_players.add(target_id)

        # Note: Counterattack will be handled in post-processing
        # when we know who attacked the target

        logger.info(f"Bodyguard {action.player_id} is guarding {target_id}")

        return NightActionResult(
            action=action,
            message=f"You are guarding {target.name} tonight."
        )

    # ========================================================================
    # Additional Role Ability Handlers
    # ========================================================================

    def _handle_spy(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Spy bug action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to bug anyone."
            )

        target = self._get_player(game_state, target_id)

        # Spy sees visitors (like Lookout) AND can hear Mafia chat
        visitors = self.summary.visitors.get(target_id, [])
        
        visitor_names = [self._get_player(game_state, v).name for v in visitors] if visitors else []
        
        result = f"You bugged {target.name}. "
        if visitor_names:
            result += f"Visitors: {', '.join(visitor_names)}. "
        else:
            result += "No one visited them. "
        
        result += "You also hear Mafia conversations."

        logger.info(f"Spy {action.player_id} bugged {target_id}")

        return NightActionResult(
            action=action,
            message=result
        )

    def _handle_medium_seance(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Medium seance action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to seance anyone."
            )

        target = self._get_player(game_state, target_id)

        # Check if target is dead
        if target.is_alive:
            return NightActionResult(
                action=action,
                message=f"{target.name} is still alive. You cannot seance them."
            )

        # Medium can talk to dead player (requires special chat channel)
        logger.info(f"Medium {action.player_id} is seancing {target_id}")

        return NightActionResult(
            action=action,
            message=f"You are holding a seance with {target.name}. You can speak to them tonight.",
            target_message=f"A Medium is holding a seance with you. You can speak to them."
        )

    def _handle_retributionist_revive(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Retributionist revive action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to revive anyone."
            )

        retributionist = self._get_player(game_state, action.player_id)

        # Check if Retributionist has revive uses remaining (should be 1)
        if not self._check_ability_uses(retributionist, "revive"):
            return NightActionResult(
                action=action,
                message="You have already used your revive!"
            )

        target = self._get_player(game_state, target_id)

        # Check if target is dead
        if target.is_alive:
            return NightActionResult(
                action=action,
                message=f"{target.name} is still alive!"
            )

        # Check if target was Town
        target_faction = target.role.faction.value if hasattr(target.role.faction, 'value') else str(target.role.faction)
        if target_faction != "Town":
            return NightActionResult(
                action=action,
                message=f"{target.name} was not a Town member. You can only revive Town."
            )

        # Revive the player
        target.is_alive = True
        target.death_info = None

        # Decrement uses (one-time use)
        self._decrement_ability_uses(retributionist, "revive")

        logger.info(f"Retributionist {action.player_id} revived {target_id}")

        return NightActionResult(
            action=action,
            message=f"You revived {target.name}! They are back in the game.",
            target_message="You have been revived by a Retributionist!"
        )

    def _handle_disguise(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Disguiser disguise action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to disguise."
            )

        disguiser = self._get_player(game_state, action.player_id)

        # Check if Disguiser has disguises remaining
        if not self._check_ability_uses(disguiser, "disguise"):
            return NightActionResult(
                action=action,
                message="You have no disguises remaining!"
            )

        target = self._get_player(game_state, target_id)

        # Decrement uses (attempt counts as use)
        self._decrement_ability_uses(disguiser, "disguise")

        # Disguiser will appear as target if target dies
        # This requires post-processing to swap roles after death
        logger.info(f"Disguiser {action.player_id} will disguise as {target_id}")

        return NightActionResult(
            action=action,
            message=f"You will disguise as {target.name} if they die tonight."
        )

    def _handle_hypnotize(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Hypnotist hypnotize action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to hypnotize anyone."
            )

        target = self._get_player(game_state, target_id)

        # Hypnotist gives target false information
        # Simplified: just notify hypnotist
        logger.info(f"Hypnotist {action.player_id} hypnotized {target_id}")

        return NightActionResult(
            action=action,
            message=f"You hypnotized {target.name}. They will receive false information."
        )

    def _handle_juggernaut_rampage(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Juggernaut rampage action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to attack anyone."
            )

        target = self._get_player(game_state, target_id)
        juggernaut = self._get_player(game_state, action.player_id)

        # Juggernaut's attack power increases with each kill
        # Count previous kills (simplified - would track in player state)
        kills_count = 0
        for death in game_state.all_deaths:
            if death.killer_id == action.player_id:
                kills_count += 1

        # Attack power escalates: Basic -> Powerful -> Unstoppable
        if kills_count >= 2:
            attack = AttackValue.UNSTOPPABLE
        elif kills_count >= 1:
            attack = AttackValue.POWERFUL
        else:
            attack = AttackValue.BASIC

        defense = target.role.defense

        if self._can_kill(attack, defense):
            death = DeathInfo(
                player_id=target_id,
                day_number=game_state.current_day,
                phase="Night",
                cause="Killed by Juggernaut",
                killer_id=action.player_id
            )
            self.summary.deaths.append(death)

            logger.info(f"Juggernaut {action.player_id} killed {target_id} (attack level: {attack})")

            return NightActionResult(
                action=action,
                message=f"You killed {target.name}! Your power grows stronger.",
                kill_successful=True
            )
        else:
            return NightActionResult(
                action=action,
                message=f"Your target's defense was too high!",
                kill_blocked_by="defense"
            )

    def _handle_forge_will(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Forger forge will action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to forge a will."
            )

        forger = self._get_player(game_state, action.player_id)

        # Check if Forger has forges remaining
        if not self._check_ability_uses(forger, "forge"):
            return NightActionResult(
                action=action,
                message="You have no forges remaining!"
            )

        target = self._get_player(game_state, target_id)

        # Decrement uses (attempt counts as use)
        self._decrement_ability_uses(forger, "forge")

        # Forger needs a fake will text (requires UI input)
        # Simplified: just mark that will will be forged
        logger.info(f"Forger {action.player_id} will forge {target_id}'s will")

        return NightActionResult(
            action=action,
            message=f"You will forge {target.name}'s will if they die tonight."
        )

    def _handle_amnesiac_remember(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Amnesiac remember action."""
        if target_id is None:
            return NightActionResult(
                action=action,
                message="You decided not to remember."
            )

        amnesiac = self._get_player(game_state, action.player_id)

        # Check if Amnesiac has remember uses remaining (should be 1)
        if not self._check_ability_uses(amnesiac, "remember"):
            return NightActionResult(
                action=action,
                message="You have already remembered a role!"
            )

        target = self._get_player(game_state, target_id)

        # Check if target is dead
        if target.is_alive:
            return NightActionResult(
                action=action,
                message=f"{target.name} is still alive. You can only remember dead players."
            )

        # Amnesiac becomes the target's role
        amnesiac.role = target.role
        amnesiac.faction = target.faction

        # Decrement uses (one-time use)
        self._decrement_ability_uses(amnesiac, "remember")

        logger.info(f"Amnesiac {action.player_id} remembered and became {target.role.name}")

        return NightActionResult(
            action=action,
            message=f"You remembered! You are now a {target.role.name}."
        )

    def _handle_jester_haunt(
        self,
        game_state: GameState,
        action: NightAction,
        target_id: Optional[int]
    ) -> NightActionResult:
        """Handle Jester haunt action (dead Jester haunting guilty voter)."""
        jester = self._get_player(game_state, action.player_id)

        # Check if Jester can haunt
        if not jester.can_haunt:
            return NightActionResult(
                action=action,
                message="You cannot haunt anyone."
            )

        # Check if Jester has haunt uses remaining (should be 1)
        if not self._check_ability_uses(jester, "haunt"):
            return NightActionResult(
                action=action,
                message="You have already used your haunt!"
            )

        if target_id is None:
            # Jester chose not to haunt
            jester.can_haunt = False
            self._decrement_ability_uses(jester, "haunt")
            return NightActionResult(
                action=action,
                message="You decided not to haunt anyone."
            )

        # Check if target voted guilty
        if target_id not in jester.jester_guilty_voters:
            return NightActionResult(
                action=action,
                message="You can only haunt someone who voted you guilty!"
            )

        target = self._get_player(game_state, target_id)

        # Check if target is still alive
        if not target.is_alive:
            return NightActionResult(
                action=action,
                message=f"{target.name} is already dead!"
            )

        # Haunt kills with Unstoppable attack (ignores all protection)
        death = DeathInfo(
            player_id=target_id,
            day_number=game_state.current_day,
            phase="Night",
            cause="Haunted by Jester",
            killer_id=action.player_id
        )

        self.summary.deaths.append(death)

        # Disable haunt and decrement uses
        jester.can_haunt = False
        self._decrement_ability_uses(jester, "haunt")

        logger.info(f"Jester {action.player_id} haunted {target_id}")

        return NightActionResult(
            action=action,
            message=f"You haunted {target.name}! They will die tonight.",
            kill_successful=True
        )

    # ========================================================================
    # Ability Use Tracking & Cooldowns
    # ========================================================================

    def _check_cooldown(self, player: Player, ability: RoleAbility, current_night: int) -> bool:
        """
        Check if ability is off cooldown.

        Args:
            player: Player using the ability
            ability: The ability being used
            current_night: Current night number

        Returns:
            True if ability is ready to use, False if on cooldown
        """
        if ability.cooldown_nights == 0:
            return True  # No cooldown

        ability_name = ability.name.lower()

        # Check if ability has been used before
        if ability_name not in player.ability_last_used_night:
            return True  # First use, always ready

        last_used = player.ability_last_used_night[ability_name]
        nights_since_use = current_night - last_used

        # Must wait cooldown_nights before using again
        return nights_since_use > ability.cooldown_nights

    def _update_cooldown(self, player: Player, ability_name: str, current_night: int) -> None:
        """
        Update the last used night for an ability.

        Args:
            player: Player who used the ability
            ability_name: Name of the ability used
            current_night: Current night number
        """
        player.ability_last_used_night[ability_name] = current_night
        logger.debug(
            f"Player {player.player_id} used {ability_name} on night {current_night}"
        )

    def _check_ability_uses(self, player: Player, ability_name: str) -> bool:
        """
        Check if player has remaining uses for an ability.

        Args:
            player: Player using the ability
            ability_name: Name of the ability to check

        Returns:
            True if player can use ability, False otherwise
        """
        # If ability not in dictionary, it's unlimited use
        if ability_name not in player.ability_uses_remaining:
            return True

        uses_remaining = player.ability_uses_remaining[ability_name]
        return uses_remaining > 0

    def _decrement_ability_uses(self, player: Player, ability_name: str) -> None:
        """
        Decrement the uses remaining for an ability.

        Args:
            player: Player who used the ability
            ability_name: Name of the ability used
        """
        if ability_name in player.ability_uses_remaining:
            player.ability_uses_remaining[ability_name] -= 1
            logger.debug(
                f"Player {player.player_id} used {ability_name}. "
                f"Uses remaining: {player.ability_uses_remaining[ability_name]}"
            )

    def _set_ability_uses(self, player: Player, ability_name: str, uses: int) -> None:
        """
        Set the uses remaining for an ability to a specific value.

        Args:
            player: Player whose ability to modify
            ability_name: Name of the ability
            uses: Number of uses to set
        """
        player.ability_uses_remaining[ability_name] = uses
        logger.debug(
            f"Player {player.player_id} {ability_name} uses set to {uses}"
        )

    def _clear_night_states(self, game_state: GameState) -> None:
        """Clear temporary night-specific states on all players."""
        for player in game_state.players:
            # Clear states that only last one night
            player.is_alerted = False
            player.is_vested = False
            player.in_jail = False
            player.jailed_by = None
            # Note: is_blackmailed persists until next day
            # Note: is_doused persists until ignited or cleaned
