"""
Dependencies for the Jarvis Agent application.
"""

from fastapi import Request
from jarvis_agent.services.websocket_manager import WebSocketManager


def get_websocket_manager(request: Request) -> WebSocketManager:
    """
    Get the WebSocket manager from the application state.

    Args:
        request: FastAPI request object containing app state

    Returns:
        WebSocketManager instance
    """
    return request.app.state.websocket_manager
