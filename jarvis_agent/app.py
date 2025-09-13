from contextlib import asynccontextmanager
import asyncio
import logging
from fastapi import FastAPI
from jarvis_agent.settings import Settings
from jarvis_agent.routes.health import router as health_router
from jarvis_agent.routes.websocket import router as websocket_router
from jarvis_agent.routes.websocket_api import router as websocket_api_router
from jarvis_agent.routes.voice_control import router as voice_control_router
from jarvis_agent.services.websocket_manager import WebSocketManager
from jarvis_agent.services.voice_processor import VoiceProcessor
from jarvis_agent.services.audio.audio_handler import AudioHandler
from jarvis_agent.services.backend_client import BackendClient

logger = logging.getLogger(__name__)


async def create_services(app: FastAPI):
    """Initialize and configure application services"""

    # Initialize backend client
    app.state.backend_client = BackendClient(app.state.settings.backend_url)
    await app.state.backend_client.start()
    logger.info("Backend client initialized")

    # Initialize audio handler first
    app.state.audio_handler = AudioHandler()
    await app.state.audio_handler.initialize()
    logger.info("Audio handler initialized")

    # Initialize WebSocket manager with audio handler
    app.state.websocket_manager = WebSocketManager(
        audio_handler=app.state.audio_handler
    )
    logger.info("WebSocket manager initialized")

    # Initialize voice processor
    app.state.voice_processor = VoiceProcessor(
        settings=app.state.settings,
        audio_handler=app.state.audio_handler,
        websocket_manager=app.state.websocket_manager,
        backend_client=app.state.backend_client,
    )
    logger.info("Voice processor initialized")

    # Now set the voice processor reference in the websocket manager
    app.state.websocket_manager.voice_processor = app.state.voice_processor
    logger.info("Voice processor reference set in WebSocket manager")


async def voice_listening_loop(voice_processor: VoiceProcessor):
    """Background task for continuous voice listening"""
    logger.info("Starting voice listening loop...")
    current_mode = None  # Track current mode for logging state changes

    try:
        while True:
            try:
                # Only listen if voice listening is enabled
                if voice_processor.is_listening_enabled():
                    # Check if wake word was recently detected
                    if voice_processor.is_wake_word_recently_detected():
                        # Log mode change if needed
                        if current_mode != "command":
                            logger.info("Switching to command listening mode")
                            current_mode = "command"

                        # Listen for commands since wake word was detected
                        await voice_processor.listen_for_command()
                    else:
                        # Log mode change if needed
                        if current_mode != "wake_word":
                            logger.info("Switching to wake word listening mode")
                            current_mode = "wake_word"

                        # Listen for wake word
                        await voice_processor.listen_for_wake_word()

                    await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                else:
                    if current_mode is not None:
                        logger.info("Voice listening disabled")
                        current_mode = None
                    await asyncio.sleep(
                        0.5
                    )  # Longer delay when disabled to save resources
            except Exception as e:
                logger.error(f"Error in voice listening loop: {e}")
                await asyncio.sleep(1)  # Wait a bit before retrying
    except asyncio.CancelledError:
        logger.info("Voice listening loop cancelled")
    except Exception as e:
        logger.error(f"Fatal error in voice listening loop: {e}")


async def periodic_cleanup(websocket_manager: WebSocketManager):
    """Periodic task to clean up stale WebSocket connections"""
    while True:
        try:
            await asyncio.sleep(60)
            await websocket_manager.cleanup_stale_connections()
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = Settings()
    try:
        await create_services(app)

        # Start periodic cleanup task
        cleanup_task = asyncio.create_task(
            periodic_cleanup(app.state.websocket_manager)
        )
        app.state.cleanup_task = cleanup_task

        # Start voice listening task
        voice_task = asyncio.create_task(
            voice_listening_loop(app.state.voice_processor)
        )
        app.state.voice_task = voice_task

        logger.info("Ready to accept requests and listening for voice commands.")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    yield

    # Cancel background tasks on shutdown
    tasks_to_cancel = []

    if hasattr(app.state, "voice_task"):
        tasks_to_cancel.append(app.state.voice_task)

    for task in tasks_to_cancel:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Cleanup audio resources
    if hasattr(app.state, "audio_handler"):
        await app.state.audio_handler.cleanup()

    # Cleanup backend client
    if hasattr(app.state, "backend_client"):
        await app.state.backend_client.close()

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
    app.include_router(voice_control_router)

    return app
