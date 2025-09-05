import logging
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from jarvis_agent.services.websocket_manager import WebSocketManager, MessageType
from jarvis_agent.dependencies import get_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/websocket", tags=["websocket-api"])


class SendMessageRequest(BaseModel):
    """Request model for sending messages to WebSocket clients"""

    message_type: MessageType
    data: Dict[str, Any]
    client_id: Optional[str] = None  # If None, broadcast to all clients
    exclude_clients: Optional[List[str]] = None


class BroadcastMessageRequest(BaseModel):
    """Request model for broadcasting messages to all WebSocket clients"""

    message_type: MessageType
    data: Dict[str, Any]
    exclude_clients: Optional[List[str]] = None


@router.post("/send")
async def send_message(
    request: SendMessageRequest,
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """
    Send a message to a specific WebSocket client or broadcast to all clients.

    Args:
        request: Message request containing type, data, and target client

    Returns:
        Success status and delivery information
    """
    try:
        if request.client_id:
            # Send to specific client
            success = await websocket_manager.send_message_to_client(
                request.client_id, request.message_type, request.data
            )

            if not success:
                raise HTTPException(
                    status_code=404,
                    detail=f"Client {request.client_id} not found or message delivery failed",
                )

            return {
                "status": "success",
                "message": f"Message sent to client {request.client_id}",
                "delivery": "unicast",
            }
        else:
            # Broadcast to all clients
            await websocket_manager.broadcast_message(
                request.message_type, request.data, request.exclude_clients
            )

            connected_count = len(websocket_manager.get_connected_clients())
            excluded_count = (
                len(request.exclude_clients) if request.exclude_clients else 0
            )
            delivered_count = connected_count - excluded_count

            return {
                "status": "success",
                "message": f"Message broadcasted to {delivered_count} clients",
                "delivery": "broadcast",
                "delivered_to": delivered_count,
                "total_connected": connected_count,
            }

    except Exception as e:
        logger.error(f"Error sending WebSocket message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.post("/broadcast")
async def broadcast_message(
    request: BroadcastMessageRequest,
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """
    Broadcast a message to all connected WebSocket clients.

    Args:
        request: Broadcast request containing message type, data, and exclusions

    Returns:
        Success status and delivery information
    """
    try:
        await websocket_manager.broadcast_message(
            request.message_type, request.data, request.exclude_clients
        )

        connected_count = len(websocket_manager.get_connected_clients())
        excluded_count = len(request.exclude_clients) if request.exclude_clients else 0
        delivered_count = connected_count - excluded_count

        return {
            "status": "success",
            "message": f"Message broadcasted to {delivered_count} clients",
            "delivered_to": delivered_count,
            "total_connected": connected_count,
            "excluded": excluded_count,
        }

    except Exception as e:
        logger.error(f"Error broadcasting WebSocket message: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to broadcast message: {str(e)}"
        )


@router.get("/clients")
async def get_connected_clients(
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """
    Get information about currently connected WebSocket clients.

    Returns:
        List of connected clients with their metadata
    """
    try:
        clients = []
        for client_id in websocket_manager.get_connected_clients():
            metadata = websocket_manager.get_client_metadata(client_id)
            clients.append({"client_id": client_id, "metadata": metadata})

        # Also get the enriched client info summary
        client_summary = websocket_manager.get_client_info_summary()

        return {
            "status": "success",
            "total_connected": len(clients),
            "clients": clients,
            "client_summary": client_summary,
        }

    except Exception as e:
        logger.error(f"Error retrieving connected clients: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve clients: {str(e)}"
        )


@router.get("/clients/{client_id}")
async def get_client_info(
    client_id: str, websocket_manager: WebSocketManager = Depends(get_websocket_manager)
):
    """
    Get information about a specific WebSocket client.

    Args:
        client_id: ID of the client to retrieve information for

    Returns:
        Client information and metadata
    """
    try:
        if not websocket_manager.is_client_connected(client_id):
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        metadata = websocket_manager.get_client_metadata(client_id)

        return {
            "status": "success",
            "client_id": client_id,
            "connected": True,
            "metadata": metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving client info: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve client info: {str(e)}"
        )


@router.delete("/clients/{client_id}")
async def disconnect_client(
    client_id: str, websocket_manager: WebSocketManager = Depends(get_websocket_manager)
):
    """
    Forcefully disconnect a specific WebSocket client.

    Args:
        client_id: ID of the client to disconnect

    Returns:
        Success status
    """
    try:
        if not websocket_manager.is_client_connected(client_id):
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        await websocket_manager.disconnect(client_id)

        return {"status": "success", "message": f"Client {client_id} disconnected"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting client: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to disconnect client: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_stale_connections(
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """
    Manually trigger cleanup of stale WebSocket connections.

    Returns:
        Status of cleanup operation
    """
    try:
        initial_count = len(websocket_manager.get_connected_clients())
        await websocket_manager.cleanup_stale_connections()
        final_count = len(websocket_manager.get_connected_clients())
        cleaned_count = initial_count - final_count

        return {
            "status": "success",
            "message": f"Cleanup completed. Removed {cleaned_count} stale connections",
            "initial_connections": initial_count,
            "final_connections": final_count,
            "cleaned_connections": cleaned_count,
        }
    except Exception as e:
        logger.error(f"Error during manual cleanup: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cleanup connections: {str(e)}"
        )


# Convenience endpoints for common message types


@router.post("/send/notification")
async def send_notification(
    title: str,
    message: str,
    client_id: Optional[str] = None,
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """
    Send a notification message to client(s).

    Args:
        title: Notification title
        message: Notification message
        client_id: Optional specific client ID (broadcasts if None)
    """
    notification_data = {
        "title": title,
        "message": message,
        "timestamp": None,  # Will be added by WebSocketManager
    }

    if client_id:
        success = await websocket_manager.send_message_to_client(
            client_id, MessageType.NOTIFICATION, notification_data
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        return {"status": "success", "message": f"Notification sent to {client_id}"}
    else:
        await websocket_manager.broadcast_message(
            MessageType.NOTIFICATION, notification_data
        )
        count = len(websocket_manager.get_connected_clients())
        return {"status": "success", "message": f"Notification sent to {count} clients"}


@router.post("/send/text")
async def send_text_message(
    message: str,
    sender: str = "jarvis",
    client_id: Optional[str] = None,
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """
    Send a text message to client(s).

    Args:
        message: Text message content
        sender: Message sender identifier
        client_id: Optional specific client ID (broadcasts if None)
    """
    text_data = {
        "message": message,
        "from": sender,
        "timestamp": None,  # Will be added by WebSocketManager
    }

    if client_id:
        success = await websocket_manager.send_message_to_client(
            client_id, MessageType.TEXT_MESSAGE, text_data
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        return {"status": "success", "message": f"Text message sent to {client_id}"}
    else:
        await websocket_manager.broadcast_message(MessageType.TEXT_MESSAGE, text_data)
        count = len(websocket_manager.get_connected_clients())
        return {"status": "success", "message": f"Text message sent to {count} clients"}
