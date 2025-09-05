from contextlib import asynccontextmanager
import asyncio
import logging
from fastapi import FastAPI
from jarvis_agent.settings import Settings
from jarvis_agent.routes.health import router as health_router
from jarvis_agent.routes.websocket import router as websocket_router
from jarvis_agent.routes.websocket_api import router as websocket_api_router
from jarvis_agent.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


def create_services(app: FastAPI):
    """Initialize and configure application services"""
    # Initialize WebSocket manager
    app.state.websocket_manager = WebSocketManager()
    logger.info("WebSocket manager initialized")


async def periodic_cleanup(websocket_manager: WebSocketManager):
    """Periodic task to clean up stale WebSocket connections"""
    while True:
        try:
            await asyncio.sleep(60)  # Run every minute
            await websocket_manager.cleanup_stale_connections()
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = Settings()
    try:
        create_services(app)

        # Start periodic cleanup task
        cleanup_task = asyncio.create_task(
            periodic_cleanup(app.state.websocket_manager)
        )
        app.state.cleanup_task = cleanup_task

        logger.info("Ready to accept requests.")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    yield

    # Cancel cleanup task on shutdown
    if hasattr(app.state, "cleanup_task"):
        app.state.cleanup_task.cancel()
        try:
            await app.state.cleanup_task
        except asyncio.CancelledError:
            pass

    logger.info("Shutting down...")


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="J.A.R.V.I.S Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(websocket_router)
    app.include_router(websocket_api_router)

    return app
