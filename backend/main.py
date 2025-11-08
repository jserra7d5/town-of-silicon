"""
Town of Silicon - Main FastAPI Application

Single-player Town of Salem with AI agents powered by oss-20b (64K context).
"""
import asyncio
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Add parent directory to path for imports to work
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config.settings import settings
from backend.core.game_orchestrator import GameOrchestrator

# Global game orchestrator instance
game_orchestrator: GameOrchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global game_orchestrator

    # Startup
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Context Size: {settings.llm_context_size:,} tokens (64K!)")

    # Initialize game orchestrator
    game_orchestrator = GameOrchestrator()
    try:
        await game_orchestrator.initialize()
        logger.success("Game orchestrator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize game orchestrator: {e}")
        logger.warning("Application starting with errors - game may not work")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if game_orchestrator:
        game_orchestrator.llm_client.unload_model()
    logger.info("Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Single-player Town of Salem with AI agents",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite, React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "llm_loaded": game_orchestrator.llm_client._loaded if game_orchestrator else False,
        "context_size": settings.llm_context_size,
        "game_active": game_orchestrator.running if game_orchestrator else False
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "description": "AI-powered Town of Salem",
        "features": {
            "context_window": "64K tokens",
            "ai_players": 14,
            "no_summarization": True,
            "perfect_memory": True
        },
        "docs": "/docs"
    }


# Game control endpoints
@app.post("/api/game/create")
async def create_game(human_position: int = None):
    """Create a new game."""
    if not game_orchestrator:
        return {"error": "Game orchestrator not initialized"}

    try:
        game_state = await game_orchestrator.create_game(human_position)
        return {
            "status": "success",
            "game_id": "main",  # Single game instance
            "players": [
                {
                    "id": p.player_id,
                    "name": p.name,
                    "is_human": p.is_human
                }
                for p in game_state.players
            ]
        }
    except Exception as e:
        logger.error(f"Error creating game: {e}")
        return {"error": str(e)}


@app.post("/api/game/start")
async def start_game():
    """Start the game loop."""
    if not game_orchestrator:
        return {"error": "Game orchestrator not initialized"}

    if not game_orchestrator.game_state:
        return {"error": "No game created - call /api/game/create first"}

    # Start game in background task
    asyncio.create_task(game_orchestrator.start_game())

    return {
        "status": "success",
        "message": "Game started"
    }


@app.get("/api/game/state")
async def get_game_state():
    """Get current game state."""
    if not game_orchestrator or not game_orchestrator.game_state:
        return {"error": "No active game"}

    return game_orchestrator.game_state.model_dump()


@app.post("/api/game/save")
async def save_game(save_name: str = None):
    """Save the current game."""
    if not game_orchestrator:
        return {"error": "Game orchestrator not initialized"}

    if not game_orchestrator.game_state:
        return {"error": "No active game to save"}

    try:
        save_path = game_orchestrator.save_game(save_name)
        return {
            "status": "success",
            "message": "Game saved successfully",
            "save_path": save_path
        }
    except Exception as e:
        logger.error(f"Error saving game: {e}")
        return {"error": str(e)}


@app.post("/api/game/load")
async def load_game(save_name: str):
    """Load a saved game."""
    if not game_orchestrator:
        return {"error": "Game orchestrator not initialized"}

    try:
        game_state = await game_orchestrator.load_game(save_name)
        return {
            "status": "success",
            "message": "Game loaded successfully",
            "game_id": game_state.game_id,
            "current_day": game_state.current_day,
            "current_phase": game_state.current_phase.phase_type.value
        }
    except FileNotFoundError:
        return {"error": f"Save file not found: {save_name}"}
    except Exception as e:
        logger.error(f"Error loading game: {e}")
        return {"error": str(e)}


@app.get("/api/game/saves")
async def list_saves():
    """List all available save files."""
    if not game_orchestrator:
        return {"error": "Game orchestrator not initialized"}

    try:
        saves = game_orchestrator.list_saves()
        return {
            "status": "success",
            "saves": [save.model_dump() for save in saves]
        }
    except Exception as e:
        logger.error(f"Error listing saves: {e}")
        return {"error": str(e)}


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time game communication.

    Clients connect here to send/receive game events.
    """
    if not game_orchestrator:
        await websocket.close(code=1011, reason="Game orchestrator not initialized")
        return

    # For now, all clients connect as observers
    # In full implementation, would authenticate and assign player_id
    player_id = None  # Human player would be 0

    try:
        await game_orchestrator.ws_handler.handle_connection(websocket, player_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason=str(e))


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )
