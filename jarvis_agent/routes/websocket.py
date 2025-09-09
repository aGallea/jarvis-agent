import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jarvis_agent.services.websocket_manager import WebSocketManager, MessageType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


def get_websocket_manager() -> Optional[WebSocketManager]:
    """Dependency to get the WebSocket manager from app state"""
    # This will be injected from the app state
    return None


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier"),
    device_type: Optional[str] = Query(
        None, description="Type of device (mobile, web, etc.)"
    ),
    app_version: Optional[str] = Query(None, description="App version"),
):
    """
    WebSocket endpoint for React Native and other clients to connect.

    Query Parameters:
    - client_id: Unique identifier for the client (required)
    - device_type: Optional device type information
    - app_version: Optional app version information

    Usage from React Native:
    ws://your-server:8001/ws/connect?client_id=your-unique-id&device_type=mobile&app_version=1.0.0
    """
    # Get WebSocket manager from app state
    websocket_manager: WebSocketManager = websocket.app.state.websocket_manager

    # Prepare client metadata
    metadata = {
        "device_type": device_type,
        "app_version": app_version,
        "user_agent": websocket.headers.get("user-agent"),
        "origin": websocket.headers.get("origin"),
        "is_jarvis_app": client_id
        == "jarvis-app-backend",  # Special flag for jarvis-app
    }

    try:
        # Connect the client
        await websocket_manager.connect(websocket, client_id, metadata)

        # Keep the connection alive and handle messages
        while True:
            try:
                # Wait for message from client
                message = await websocket.receive_text()

                # Handle the message
                response = await websocket_manager.handle_message(client_id, message)
                logger.debug(f"Message handled for {client_id}: {response}")

            except WebSocketDisconnect:
                logger.info(f"Client {client_id} disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error handling message from {client_id}: {e}")
                # Only try to send error message if client is still connected
                if websocket_manager.is_client_connected(client_id):
                    try:
                        await websocket_manager.send_message_to_client(
                            client_id,
                            MessageType.ERROR,
                            {"error": "Message processing error", "details": str(e)},
                        )
                    except Exception as send_error:
                        logger.warning(
                            f"Failed to send error message to {client_id}: {send_error}"
                        )
                        # Connection is broken, break out of loop
                        break
                else:
                    # Client is no longer connected, break out of loop
                    logger.info(
                        f"Client {client_id} is no longer connected, exiting message loop"
                    )
                    break

    except Exception as e:
        logger.error(f"WebSocket connection error for {client_id}: {e}")
    finally:
        # Clean up connection
        await websocket_manager.disconnect(client_id)


@router.get("/status")
async def websocket_status():
    """
    Get WebSocket server status and connected clients.
    Useful for debugging and monitoring.
    """
    # This endpoint would need access to the WebSocket manager
    # For now, return a placeholder response
    return {
        "status": "WebSocket server running",
        "endpoint": "/ws/connect",
        "message": "Use GET /api/websocket/clients for connected clients info",
    }


@router.get("/clients")
async def get_connected_clients():
    """
    Get information about currently connected WebSocket clients.
    Useful for monitoring and debugging.
    """
    # This would need to be implemented with access to the WebSocket manager
    # from the app state in a real scenario
    return {
        "message": "This endpoint needs to be connected to the WebSocket manager",
        "note": "Implementation requires dependency injection from app state",
    }
