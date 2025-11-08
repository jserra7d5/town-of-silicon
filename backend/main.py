"""
Town of Silicon - Main FastAPI Application

Single-player Town of Salem with AI agents powered by oss-20b (64K context).
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from config.settings import settings
from ai.llm_client import llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Context Size: {settings.llm_context_size:,} tokens (64K!)")

    # Load LLM model
    try:
        await asyncio.to_thread(llm_client.load_model)
        logger.success("LLM model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load LLM model: {e}")
        logger.warning("Application starting without LLM - AI players will not work")

    yield

    # Shutdown
    logger.info("Shutting down...")
    llm_client.unload_model()
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
        "llm_loaded": llm_client._loaded,
        "context_size": settings.llm_context_size
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


# API routes (to be added)
# from api import websocket, game, admin
# app.include_router(websocket.router)
# app.include_router(game.router, prefix="/api/game")
# app.include_router(admin.router, prefix="/api/admin")


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
