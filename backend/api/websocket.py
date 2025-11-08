"""WebSocket API for real-time game communication.

Handles client connections and real-time game state updates.
"""
import asyncio
from typing import Optional
from loguru import logger
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..models.game import GameState, ChatMessage, PhaseType
from ..models.player import Player


# ============================================================================
# WebSocket Message Models
# ============================================================================

class WSMessage(BaseModel):
    """Base WebSocket message."""
    type: str
    data: dict = {}


class WSGameStateUpdate(BaseModel):
    """Game state update message."""
    type: str = "game_state_update"
    game_state: GameState


class WSChatMessage(BaseModel):
    """Chat message."""
    type: str = "chat_message"
    message: ChatMessage


class WSPhaseChange(BaseModel):
    """Phase change notification."""
    type: str = "phase_change"
    phase: str
    duration: float
    phase_number: int


class WSPlayerAction(BaseModel):
    """Player action from client."""
    type: str  # "night_action", "vote", "chat", "defense"
    player_id: int
    target_id: Optional[int] = None
    message: Optional[str] = None
    guilty: Optional[bool] = None


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections.

    Handles broadcasting game state updates to all connected clients.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.player_connections: dict[int, WebSocket] = {}  # player_id -> websocket

    async def connect(self, websocket: WebSocket, player_id: Optional[int] = None):
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            player_id: Player ID (for authenticated connections)
        """
        await websocket.accept()
        self.active_connections.append(websocket)

        if player_id is not None:
            self.player_connections[player_id] = websocket

        logger.info(
            f"WebSocket connected (total: {len(self.active_connections)}, "
            f"player_id: {player_id})"
        )

    def disconnect(self, websocket: WebSocket, player_id: Optional[int] = None):
        """
        Remove a WebSocket connection.

        Args:
            websocket: WebSocket connection
            player_id: Player ID (if known)
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if player_id and player_id in self.player_connections:
            del self.player_connections[player_id]

        logger.info(
            f"WebSocket disconnected (remaining: {len(self.active_connections)})"
        )

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific client."""
        await websocket.send_json(message)

    async def send_to_player(self, message: dict, player_id: int):
        """Send message to specific player by ID."""
        if player_id in self.player_connections:
            await self.player_connections[player_id].send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

    async def broadcast_to_alive(self, message: dict, game_state: GameState):
        """Broadcast message to all alive players."""
        alive_ids = [p.player_id for p in game_state.players if p.is_alive]

        for player_id in alive_ids:
            if player_id in self.player_connections:
                try:
                    await self.player_connections[player_id].send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to player {player_id}: {e}")

    async def broadcast_to_dead(self, message: dict, game_state: GameState):
        """Broadcast message to all dead players."""
        dead_ids = [p.player_id for p in game_state.players if not p.is_alive]

        for player_id in dead_ids:
            if player_id in self.player_connections:
                try:
                    await self.player_connections[player_id].send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to player {player_id}: {e}")

    async def broadcast_to_mafia(self, message: dict, game_state: GameState):
        """Broadcast message to Mafia members only."""
        mafia_ids = [
            p.player_id for p in game_state.players
            if p.is_alive and p.role.faction == "Mafia"
        ]

        for player_id in mafia_ids:
            if player_id in self.player_connections:
                try:
                    await self.player_connections[player_id].send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to mafia {player_id}: {e}")


# ============================================================================
# WebSocket Handler
# ============================================================================

class WebSocketHandler:
    """
    Handles WebSocket connections and routes messages.

    Integrates with game engine to process player actions.
    """

    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager
        self.game_state: Optional[GameState] = None
        self.action_queue: asyncio.Queue = asyncio.Queue()

    def set_game_state(self, game_state: GameState):
        """Set the current game state reference."""
        self.game_state = game_state

    async def handle_connection(self, websocket: WebSocket, player_id: Optional[int] = None):
        """
        Handle a WebSocket connection lifecycle.

        Args:
            websocket: WebSocket connection
            player_id: Player ID (for authenticated connections)
        """
        await self.manager.connect(websocket, player_id)

        # Send initial game state
        if self.game_state:
            await self.send_game_state(websocket)

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                message = WSMessage(**data)

                # Route message
                await self.route_message(message, websocket, player_id)

        except WebSocketDisconnect:
            self.manager.disconnect(websocket, player_id)
            logger.info(f"Client disconnected (player_id: {player_id})")

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.manager.disconnect(websocket, player_id)

    async def route_message(
        self,
        message: WSMessage,
        websocket: WebSocket,
        player_id: Optional[int]
    ):
        """Route incoming message to appropriate handler."""
        msg_type = message.type

        if msg_type == "chat":
            await self.handle_chat(message, player_id)

        elif msg_type == "night_action":
            await self.handle_night_action(message, player_id)

        elif msg_type == "vote":
            await self.handle_vote(message, player_id)

        elif msg_type == "defense":
            await self.handle_defense(message, player_id)

        elif msg_type == "request_game_state":
            await self.send_game_state(websocket)

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def handle_chat(self, message: WSMessage, player_id: Optional[int]):
        """Handle chat message from player."""
        if not player_id or not self.game_state:
            return

        text = message.data.get("message", "")

        # Validate player can chat
        player = self._get_player(player_id)
        if not player:
            return

        # Create chat message
        chat_msg = ChatMessage(
            player_id=player_id,
            player_name=player.name,
            message=text,
            phase=self.game_state.current_phase.phase_type.value,
            day_number=self.game_state.current_day,
            visible_to_dead=not player.is_alive
        )

        # Add to game state
        self.game_state.all_chat_messages.append(chat_msg)

        # Broadcast based on player status
        if player.is_alive:
            # Living players - everyone sees
            await self.manager.broadcast({
                "type": "chat_message",
                "message": chat_msg.model_dump()
            })
        else:
            # Dead players - only dead see
            await self.manager.broadcast_to_dead(
                {
                    "type": "chat_message",
                    "message": chat_msg.model_dump()
                },
                self.game_state
            )

        # If Mafia chat at night, only Mafia see
        if (player.role.faction == "Mafia" and
            self.game_state.current_phase.phase_type == PhaseType.NIGHT):
            await self.manager.broadcast_to_mafia(
                {
                    "type": "mafia_chat",
                    "message": chat_msg.model_dump()
                },
                self.game_state
            )

    async def handle_night_action(self, message: WSMessage, player_id: Optional[int]):
        """Handle night action submission."""
        if not player_id:
            return

        target_id = message.data.get("target_id")

        # Queue action for processing
        await self.action_queue.put({
            "type": "night_action",
            "player_id": player_id,
            "target_id": target_id
        })

        logger.info(f"Player {player_id} submitted night action targeting {target_id}")

    async def handle_vote(self, message: WSMessage, player_id: Optional[int]):
        """Handle vote submission."""
        if not player_id:
            return

        target_id = message.data.get("target_id")
        guilty = message.data.get("guilty")

        # Queue vote for processing
        await self.action_queue.put({
            "type": "vote",
            "player_id": player_id,
            "target_id": target_id,
            "guilty": guilty
        })

        logger.info(
            f"Player {player_id} submitted vote for {target_id} "
            f"(guilty: {guilty})"
        )

    async def handle_defense(self, message: WSMessage, player_id: Optional[int]):
        """Handle defense speech submission."""
        if not player_id:
            return

        defense = message.data.get("defense", "")

        # Queue defense for processing
        await self.action_queue.put({
            "type": "defense",
            "player_id": player_id,
            "defense": defense
        })

        logger.info(f"Player {player_id} submitted defense: {defense}")

    async def send_game_state(self, websocket: WebSocket):
        """Send current game state to client."""
        if not self.game_state:
            return

        await self.manager.send_personal_message(
            {
                "type": "game_state_update",
                "game_state": self.game_state.model_dump()
            },
            websocket
        )

    async def broadcast_game_state(self):
        """Broadcast game state to all clients."""
        if not self.game_state:
            return

        await self.manager.broadcast({
            "type": "game_state_update",
            "game_state": self.game_state.model_dump()
        })

    async def broadcast_phase_change(self, phase: PhaseType, duration: float, number: int):
        """Broadcast phase change to all clients."""
        await self.manager.broadcast({
            "type": "phase_change",
            "phase": phase.value,
            "duration": duration,
            "phase_number": number
        })

    def _get_player(self, player_id: int) -> Optional[Player]:
        """Get player by ID."""
        if not self.game_state:
            return None

        return next(
            (p for p in self.game_state.players if p.player_id == player_id),
            None
        )
