"""Role assignment system - assigns roles to 15 players at game start."""
import random
import yaml
from pathlib import Path
from typing import Dict, List
from loguru import logger

from ..models.role import (
    Role, RoleList, RoleSlot, RoleConstraint, RoleAbility,
    FactionType, AttackValue, DefenseValue, PlayerRoleAssignment
)
from ..models.player import Player


class RoleRegistry:
    """Registry of all available roles loaded from YAML."""

    def __init__(self, config_path: str = "config/roles.yaml"):
        self.roles: Dict[str, Role] = {}
        self.role_lists: Dict[str, RoleList] = {}
        self._load_roles(config_path)

    def _load_roles(self, config_path: str) -> None:
        """Load roles from YAML configuration."""
        path = Path(__file__).parent.parent / config_path

        if not path.exists():
            raise FileNotFoundError(f"Roles configuration not found: {path}")

        with open(path, 'r') as f:
            config = yaml.safe_load(f)

        # Load all role categories
        for category in ['town_investigative', 'town_killing', 'town_protective',
                        'town_support', 'mafia_killing', 'mafia_deception',
                        'mafia_support', 'neutral_killing', 'neutral_evil',
                        'neutral_benign']:
            if category in config:
                for role_id, role_data in config[category].items():
                    self._parse_role(role_data)

        # Load role lists
        if 'role_lists' in config:
            for list_name, list_data in config['role_lists'].items():
                self._parse_role_list(list_name, list_data)

        logger.success(f"Loaded {len(self.roles)} roles and {len(self.role_lists)} role lists")

    def _parse_role(self, data: dict) -> None:
        """Parse a single role from YAML."""
        # Parse abilities
        abilities = []
        for ability_data in data.get('abilities', []):
            abilities.append(RoleAbility(
                name=ability_data['name'],
                description=ability_data['description'],
                action_type=ability_data['action_type'],
                priority=ability_data['priority'],
                max_uses=ability_data.get('max_uses'),
                cooldown_nights=ability_data.get('cooldown_nights', 0),
                targets_required=ability_data.get('targets_required', 1)
            ))

        # Create role
        role = Role(
            id=data['id'],
            name=data['name'],
            faction=FactionType(data['faction']),
            category=data['category'],
            alignment=data['alignment'],
            attack=AttackValue(data.get('attack', 0)),
            defense=DefenseValue(data.get('defense', 0)),
            unique=data.get('unique', False),
            abilities=abilities,
            immunities=data.get('immunities', []),
            summary=data['summary'],
            goal=data['goal']
        )

        self.roles[role.id] = role

    def _parse_role_list(self, name: str, data: dict) -> None:
        """Parse a role list from YAML."""
        slots = []
        for slot_data in data['slots']:
            constraint = RoleConstraint(
                type=slot_data['constraint']['type'],
                value=slot_data['constraint']['value']
            )
            slot = RoleSlot(
                position=slot_data['position'],
                constraint=constraint
            )
            slots.append(slot)

        role_list = RoleList(
            name=data['name'],
            description=data['description'],
            slots=slots
        )

        self.role_lists[name] = role_list

    def get_role(self, role_id: str) -> Role:
        """Get role by ID."""
        if role_id not in self.roles:
            raise KeyError(f"Role not found: {role_id}")
        return self.roles[role_id]

    def get_role_list(self, list_name: str) -> RoleList:
        """Get role list by name."""
        if list_name not in self.role_lists:
            raise KeyError(f"Role list not found: {list_name}")
        return self.role_lists[list_name]

    def get_roles_by_category(self, category: str) -> List[Role]:
        """Get all roles in a category."""
        return [r for r in self.roles.values() if r.category == category]

    def get_roles_by_faction(self, faction: str) -> List[Role]:
        """Get all roles in a faction."""
        return [r for r in self.roles.values() if r.faction.value == faction]


class RoleAssignmentSystem:
    """Assigns roles to 15 players following role list constraints."""

    def __init__(self, registry: RoleRegistry):
        self.registry = registry

    def assign_roles(
        self,
        role_list_name: str = "classic",
        human_position: int | None = None,
        seed: int | None = None
    ) -> List[PlayerRoleAssignment]:
        """
        Assign roles to 15 players.

        Args:
            role_list_name: Name of role list to use (e.g., "classic")
            human_position: Position for human player (1-15), None for random
            seed: Random seed for reproducibility

        Returns:
            List of 15 player role assignments

        Raises:
            ValueError: If role assignment fails validation
        """
        if seed is not None:
            random.seed(seed)

        # Get role list
        role_list = self.registry.get_role_list(role_list_name)

        logger.info(f"Assigning roles using '{role_list_name}' role list")

        # Assign roles for each slot
        assignments: List[PlayerRoleAssignment] = []
        assigned_unique_roles: set[str] = set()

        for slot in role_list.slots:
            role = self._select_role_for_slot(
                slot,
                assigned_unique_roles
            )

            # Mark unique role as assigned
            if role.unique:
                assigned_unique_roles.add(role.id)

            # Create assignment
            assignment = PlayerRoleAssignment(
                player_id=slot.position,
                role=role,
                faction=role.faction,
                is_human=False  # Will set later
            )

            assignments.append(assignment)
            logger.debug(f"Slot {slot.position}: {role.name} ({role.faction.value})")

        # Assign human player position
        if human_position is None:
            human_position = random.randint(1, 15)

        assignments[human_position - 1].is_human = True

        logger.info(f"Human player assigned to position {human_position} ({assignments[human_position - 1].role.name})")

        # Validate assignments
        self._validate_assignments(assignments)

        return assignments

    def _select_role_for_slot(
        self,
        slot: RoleSlot,
        assigned_unique: set[str]
    ) -> Role:
        """
        Select a role for a slot based on its constraint.

        Args:
            slot: Role slot with constraint
            assigned_unique: Set of already-assigned unique role IDs

        Returns:
            Selected role

        Raises:
            ValueError: If no valid role available
        """
        constraint = slot.constraint

        # Get possible roles based on constraint type
        if constraint.type == "specific":
            # Specific role (e.g., "jailor")
            role = self.registry.get_role(constraint.value)
            possible_roles = [role]

        elif constraint.type == "category":
            # Category (e.g., "Town Investigative")
            possible_roles = self.registry.get_roles_by_category(constraint.value)

        elif constraint.type == "faction":
            # Faction (e.g., "Town")
            possible_roles = self.registry.get_roles_by_faction(constraint.value)

        elif constraint.type == "any":
            # Any role
            possible_roles = list(self.registry.roles.values())

        else:
            raise ValueError(f"Unknown constraint type: {constraint.type}")

        # Filter out already-assigned unique roles
        available_roles = [
            r for r in possible_roles
            if not r.unique or r.id not in assigned_unique
        ]

        if not available_roles:
            raise ValueError(
                f"No available roles for slot {slot.position} "
                f"(constraint: {constraint.type}={constraint.value})"
            )

        # Randomly select from available roles
        return random.choice(available_roles)

    def _validate_assignments(self, assignments: List[PlayerRoleAssignment]) -> None:
        """
        Validate role assignments.

        Raises:
            ValueError: If assignments are invalid
        """
        # Check count
        if len(assignments) != 15:
            raise ValueError(f"Must have exactly 15 assignments, got {len(assignments)}")

        # Check for duplicate unique roles
        unique_roles = [a.role.id for a in assignments if a.role.unique]
        if len(unique_roles) != len(set(unique_roles)):
            raise ValueError("Duplicate unique roles assigned")

        # Count factions
        town_count = sum(1 for a in assignments if a.faction == FactionType.TOWN)
        mafia_count = sum(1 for a in assignments if a.faction == FactionType.MAFIA)

        logger.info(f"Faction distribution: {town_count} Town, {mafia_count} Mafia, "
                   f"{15 - town_count - mafia_count} Neutral")

        # Validate balance
        if town_count < 7:
            logger.warning(f"Only {town_count} Town roles - game may be unbalanced")

        if mafia_count < 1:
            raise ValueError("Must have at least 1 Mafia role")

        if mafia_count > 5:
            logger.warning(f"{mafia_count} Mafia roles - game may be unbalanced")

        # Check for Godfather + Mafioso
        mafia_roles = [a.role.id for a in assignments if a.faction == FactionType.MAFIA]
        has_godfather = "godfather" in mafia_roles
        has_mafioso = "mafioso" in mafia_roles

        if has_mafioso and not has_godfather:
            logger.info("Mafioso without Godfather - Mafioso will become Godfather")

        logger.success("Role assignments validated successfully")

    def create_players_from_assignments(
        self,
        assignments: List[PlayerRoleAssignment]
    ) -> List[Player]:
        """
        Create Player objects from assignments.

        Args:
            assignments: Role assignments

        Returns:
            List of 15 Player objects
        """
        players = []

        for assignment in assignments:
            # Generate player name
            if assignment.is_human:
                name = "You"
            else:
                name = self._generate_ai_name(assignment.player_id)

            # Initialize ability uses
            ability_uses = {}
            for ability in assignment.role.abilities:
                if ability.max_uses is not None:
                    ability_uses[ability.name] = ability.max_uses

            player = Player(
                player_id=assignment.player_id,
                name=name,
                role=assignment.role,
                faction=assignment.faction,
                is_human=assignment.is_human,
                ability_uses_remaining=ability_uses
            )

            players.append(player)

        return players

    def _generate_ai_name(self, player_id: int) -> str:
        """Generate a name for an AI player."""
        # Classic Town of Salem names
        names = [
            "John Hathorne", "Sarah Good", "William Hobbs", "James Bayley",
            "Mary Warren", "Edward Bishop", "Ann Putnam", "Thomas Danforth",
            "Cotton Mather", "Giles Corea", "Martha Corey", "Samuel Sewall",
            "Samuel Parris", "Betty Parris", "Deodat Lawson"
        ]

        # Use player_id to consistently assign same name
        return names[(player_id - 1) % len(names)]


# Global registry instance
role_registry = RoleRegistry()
role_assignment_system = RoleAssignmentSystem(role_registry)
