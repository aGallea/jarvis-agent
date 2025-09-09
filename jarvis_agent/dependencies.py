"""
Dependencies for the Jarvis Agent application.
"""

from fastapi import Request
from jarvis_agent.services.websocket_manager import WebSocketManager
from jarvis_agent.services.voice_processor import VoiceProcessor
from jarvis_agent.services.audio.audio_handler import AudioHandler


def get_websocket_manager(request: Request) -> WebSocketManager:
    """
    Get the WebSocket manager from the application state.

    Args:
        request: FastAPI request object containing app state

    Returns:
        WebSocketManager instance
    """
    return request.app.state.websocket_manager


def get_voice_processor(request: Request) -> VoiceProcessor:
    """
    Get the voice processor from the application state.

    Args:
        request: FastAPI request object containing app state

    Returns:
        VoiceProcessor instance
    """
    return request.app.state.voice_processor


def get_audio_handler(request: Request) -> AudioHandler:
    """
    Get the audio handler from the application state.

    Args:
        request: FastAPI request object containing app state

    Returns:
        AudioHandler instance
    """
    return request.app.state.audio_handler
