import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional, Any
from fastapi import WebSocket
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Enum for different message types"""

    VOICE_COMMAND = "voice_command"
    SYSTEM_STATUS = "system_status"
    NOTIFICATION = "notification"
    AUDIO_DATA = "audio_data"
    TEXT_MESSAGE = "text_message"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    CLIENT_INFO = "client_info"
    AGENT_COMMAND = "agent_command"

    # Jarvis-app specific message types
    STT_REQUEST = "stt_request"
    STT_RESPONSE = "stt_response"
    TTS_REQUEST = "tts_request"
    TTS_RESPONSE = "tts_response"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"


class WebSocketManager:
    """
    Manages WebSocket connections and handles bidirectional communication
    with React Native clients and jarvis-app backend.
    """

    def __init__(self):
        # Store active connections with client IDs
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.jarvis_app_client_id = "jarvis-app-backend"

        # Store pending requests for request-response matching
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Accept a new WebSocket connection and register the client.

        Args:
            websocket: The WebSocket connection
            client_id: Unique identifier for the client
            metadata: Optional metadata about the client (device info, etc.)
        """
        await websocket.accept()

        # If client already exists, close old connection
        if client_id in self.active_connections:
            await self.disconnect(client_id)

        self.active_connections[client_id] = websocket
        connection_metadata = metadata or {}
        connection_metadata["connected_at"] = asyncio.get_event_loop().time()
        self.connection_metadata[client_id] = connection_metadata

        logger.info(
            f"Client {client_id} connected. Total connections: {len(self.active_connections)}"
        )

        # Send welcome message
        if client_id == self.jarvis_app_client_id:
            await self.send_message_to_client(
                client_id,
                MessageType.SYSTEM_STATUS,
                {
                    "status": "connected",
                    "message": "J.A.R.V.I.S Agent backend connection established",
                },
            )
        else:
            await self.send_message_to_client(
                client_id,
                MessageType.SYSTEM_STATUS,
                {"status": "connected", "message": "Welcome to J.A.R.V.I.S Agent"},
            )

    async def disconnect(self, client_id: str):
        """
        Disconnect a client and clean up resources.

        Args:
            client_id: The client to disconnect
        """
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                # Only try to close if not already disconnected
                if websocket.client_state.name not in ["DISCONNECTED", "DISCONNECTING"]:
                    await websocket.close()
            except Exception as e:
                logger.debug(f"Error closing connection for {client_id}: {e}")

            # Always clean up from our tracking dictionaries
            del self.active_connections[client_id]
            if client_id in self.connection_metadata:
                del self.connection_metadata[client_id]

            logger.info(
                f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}"
            )

    async def send_message_to_client(
        self, client_id: str, message_type: MessageType, data: Any
    ) -> bool:
        """
        Send a message to a specific client.

        Args:
            client_id: Target client ID
            message_type: Type of message
            data: Message payload

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if client_id not in self.active_connections:
            logger.debug(f"Client {client_id} not found in active connections")
            return False

        try:
            websocket = self.active_connections[client_id]

            # Check if the websocket connection is still valid
            if websocket.client_state.name == "DISCONNECTED":
                logger.debug(f"Client {client_id} is already disconnected")
                await self.disconnect(client_id)
                return False

            message = {
                "type": message_type.value,
                "timestamp": asyncio.get_event_loop().time(),
                "data": data,
            }

            await websocket.send_text(json.dumps(message))
            logger.debug(f"Sent message to {client_id}: {message_type.value}")
            return True

        except Exception as e:
            logger.error(f"Error sending message to {client_id}: {e}")
            await self.disconnect(client_id)
            return False

    async def broadcast_message(
        self,
        message_type: MessageType,
        data: Any,
        exclude_clients: Optional[List[str]] = None,
    ):
        """
        Broadcast a message to all connected clients.

        Args:
            message_type: Type of message
            data: Message payload
            exclude_clients: List of client IDs to exclude from broadcast
        """
        exclude_clients = exclude_clients or []

        message = {
            "type": message_type.value,
            "timestamp": asyncio.get_event_loop().time(),
            "data": data,
        }

        disconnected_clients = []

        for client_id, websocket in self.active_connections.items():
            if client_id in exclude_clients:
                continue

            try:
                await websocket.send_text(json.dumps(message))
                logger.debug(
                    f"Broadcasted message to {client_id}: {message_type.value}"
                )
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)

        logger.info(
            f"Broadcasted {message_type.value} to {len(self.active_connections) - len(exclude_clients)} clients"
        )

    async def handle_message(self, client_id: str, message: str) -> Dict[str, Any]:
        """
        Handle incoming message from a client.

        Args:
            client_id: ID of the client that sent the message
            message: Raw message string

        Returns:
            Dict containing response data
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            payload = data.get("data", {})

            logger.info(f"Received message from {client_id}: {message_type}")

            # Handle different message types
            if message_type == MessageType.PING.value:
                await self.send_message_to_client(
                    client_id,
                    MessageType.PONG,
                    {"timestamp": asyncio.get_event_loop().time()},
                )
                return {"status": "pong_sent"}

            elif message_type == MessageType.VOICE_COMMAND.value:
                # Process voice command
                response = await self._handle_voice_command(client_id, payload)
                return response

            elif message_type == MessageType.TEXT_MESSAGE.value:
                # Process text message
                response = await self._handle_text_message(client_id, payload)
                return response

            elif message_type == MessageType.SYSTEM_STATUS.value:
                # Handle system status request
                response = await self._handle_system_status_request(client_id, payload)
                return response

            elif message_type == MessageType.CLIENT_INFO.value:
                # Handle client identification/information
                response = await self._handle_client_info(client_id, payload)
                return response

            elif message_type == MessageType.AGENT_COMMAND.value:
                # Handle agent commands
                response = await self._handle_agent_command(client_id, payload)
                return response

            elif message_type == MessageType.STT_RESPONSE.value:
                # Handle STT response from jarvis-app
                response = await self._handle_stt_response(client_id, payload)
                return response

            elif message_type == MessageType.TTS_RESPONSE.value:
                # Handle TTS response from jarvis-app
                response = await self._handle_tts_response(client_id, payload)
                return response

            elif message_type == MessageType.LLM_RESPONSE.value:
                # Handle LLM response from jarvis-app
                response = await self._handle_llm_response(client_id, payload)
                return response

            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_message_to_client(
                    client_id,
                    MessageType.ERROR,
                    {"error": f"Unknown message type: {message_type}"},
                )
                return {"status": "error", "message": "Unknown message type"}

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {client_id}: {e}")
            await self.send_message_to_client(
                client_id, MessageType.ERROR, {"error": "Invalid JSON format"}
            )
            return {"status": "error", "message": "Invalid JSON"}

        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
            await self.send_message_to_client(
                client_id, MessageType.ERROR, {"error": "Internal server error"}
            )
            return {"status": "error", "message": str(e)}

    async def _handle_voice_command(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle voice command from client"""
        command = payload.get("command", "")

        logger.info(f"Processing voice command from {client_id}: {command}")

        # TODO: Integrate with your voice processing service
        # For now, just echo back
        response_text = f"Received voice command: {command}"

        await self.send_message_to_client(
            client_id,
            MessageType.TEXT_MESSAGE,
            {"message": response_text, "from": "jarvis"},
        )

        return {"status": "processed", "command": command}

    async def _handle_text_message(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle text message from client"""
        message = payload.get("message", "")

        logger.info(f"Processing text message from {client_id}: {message}")

        # TODO: Integrate with your AI/NLP processing
        # For now, just echo back
        response_text = f"J.A.R.V.I.S received: {message}"

        await self.send_message_to_client(
            client_id,
            MessageType.TEXT_MESSAGE,
            {"message": response_text, "from": "jarvis"},
        )

        return {"status": "processed", "message": message}

    async def _handle_system_status_request(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle system status request"""
        status = {
            "active_connections": len(self.active_connections),
            "server_status": "running",
            "connected_clients": list(self.active_connections.keys()),
        }

        await self.send_message_to_client(client_id, MessageType.SYSTEM_STATUS, status)

        return {"status": "sent", "data": status}

    async def _handle_client_info(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle client identification/information message"""
        client_type = payload.get("client_type")
        device_type = payload.get("device_type")
        app_version = payload.get("app_version")
        timestamp = payload.get("timestamp")

        logger.info(
            f"Received client info from {client_id}: {client_type} ({device_type}) v{app_version}"
        )

        # Update client metadata with the received information
        if client_id in self.connection_metadata:
            self.connection_metadata[client_id].update(
                {
                    "client_type": client_type,
                    "device_type": device_type,
                    "app_version": app_version,
                    "client_timestamp": timestamp,
                    "info_received": True,
                }
            )

        # Send acknowledgment back to client
        await self.send_message_to_client(
            client_id,
            MessageType.SYSTEM_STATUS,
            {
                "status": "client_info_received",
                "message": f"Client information received for {client_type}",
                "client_id": client_id,
            },
        )

        return {
            "status": "processed",
            "client_type": client_type,
            "device_type": device_type,
            "app_version": app_version,
        }

    async def _handle_agent_command(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle agent command from client"""
        command = payload.get("command", "")
        timestamp = payload.get("timestamp")

        logger.info(f"Processing agent command from {client_id}: {command}")

        # Handle different agent commands
        if command == "Test audio":
            # Handle test audio command
            response = await self._handle_test_audio(client_id)

        elif command == "Start listening":
            # Handle start listening command
            response = await self._handle_start_listening(client_id)

        elif command == "Stop listening":
            # Handle stop listening command
            response = await self._handle_stop_listening(client_id)

        else:
            logger.warning(f"Unknown agent command: {command}")
            await self.send_message_to_client(
                client_id,
                MessageType.ERROR,
                {"error": f"Unknown agent command: {command}"},
            )
            return {"status": "error", "message": "Unknown agent command"}

        # Send acknowledgment back to client
        await self.send_message_to_client(
            client_id,
            MessageType.SYSTEM_STATUS,
            {
                "status": "agent_command_processed",
                "message": f"Agent command '{command}' processed successfully",
                "command": command,
                "timestamp": timestamp,
            },
        )

        return {"status": "processed", "command": command, "response": response}

    async def _handle_test_audio(self, client_id: str) -> Dict[str, Any]:
        """Handle test audio command"""
        logger.info(f"Testing audio for client {client_id}")

        # TODO: Implement actual audio testing logic
        # This could involve:
        # - Testing microphone access
        # - Testing speaker output
        # - Running audio diagnostics

        return {"action": "test_audio", "result": "Audio test initiated"}

    async def _handle_start_listening(self, client_id: str) -> Dict[str, Any]:
        """Handle start listening command"""
        logger.info(f"Starting listening mode for client {client_id}")

        # TODO: Implement actual listening logic
        # This could involve:
        # - Activating voice recognition
        # - Starting audio stream processing
        # - Setting client state to listening

        # Update client metadata to indicate listening state
        if client_id in self.connection_metadata:
            self.connection_metadata[client_id]["listening_state"] = "active"

        return {"action": "start_listening", "result": "Listening mode activated"}

    async def _handle_stop_listening(self, client_id: str) -> Dict[str, Any]:
        """Handle stop listening command"""
        logger.info(f"Stopping listening mode for client {client_id}")

        # TODO: Implement actual stop listening logic
        # This could involve:
        # - Deactivating voice recognition
        # - Stopping audio stream processing
        # - Setting client state to idle

        # Update client metadata to indicate listening state
        if client_id in self.connection_metadata:
            self.connection_metadata[client_id]["listening_state"] = "inactive"

        return {"action": "stop_listening", "result": "Listening mode deactivated"}

    async def _handle_stt_response(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle STT response from jarvis-app"""
        logger.info(f"Received STT response from {client_id}")

        # Extract the transcribed text and request ID
        text = payload.get("text")
        request_id = payload.get("request_id")

        # Complete the pending request if it exists
        if request_id and request_id in self.pending_requests:
            future = self.pending_requests[request_id]
            if not future.done():
                future.set_result({"text": text})

        logger.info(f"STT result: {text}")
        return {
            "status": "stt_response_received",
            "text": text,
            "request_id": request_id,
        }

    async def _handle_tts_response(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle TTS response from jarvis-app"""
        logger.info(f"Received TTS response from {client_id}")

        # Extract the audio data and request ID
        audio_data = payload.get("audio_data")  # Base64 encoded
        request_id = payload.get("request_id")

        # Complete the pending request if it exists
        if request_id and request_id in self.pending_requests:
            future = self.pending_requests[request_id]
            if not future.done():
                future.set_result({"audio_data": audio_data})

        logger.info(
            f"TTS result received, audio_data length: {len(audio_data) if audio_data else 0}"
        )
        return {
            "status": "tts_response_received",
            "audio_data": audio_data,
            "request_id": request_id,
        }

    async def _handle_llm_response(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle LLM response from jarvis-app"""
        logger.info(f"Received LLM response from {client_id}")

        # Extract the generated response and request ID
        response_text = payload.get("response")
        request_id = payload.get("request_id")

        # Complete the pending request if it exists
        if request_id and request_id in self.pending_requests:
            future = self.pending_requests[request_id]
            if not future.done():
                future.set_result({"response": response_text})

        logger.info(f"LLM result: {response_text}")
        return {
            "status": "llm_response_received",
            "response": response_text,
            "request_id": request_id,
        }

    async def cleanup_stale_connections(self):
        """Clean up connections that are no longer valid"""
        stale_clients = []

        for client_id, websocket in self.active_connections.items():
            try:
                if websocket.client_state.name in ["DISCONNECTED", "DISCONNECTING"]:
                    stale_clients.append(client_id)
            except Exception:
                # If we can't check the state, consider it stale
                stale_clients.append(client_id)

        for client_id in stale_clients:
            logger.info(f"Cleaning up stale connection for client {client_id}")
            await self.disconnect(client_id)

        if stale_clients:
            logger.info(f"Cleaned up {len(stale_clients)} stale connections")

    def get_connected_clients(self) -> List[str]:
        """Get list of connected client IDs"""
        return list(self.active_connections.keys())

    def get_client_metadata(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific client"""
        return self.connection_metadata.get(client_id)

    def is_client_connected(self, client_id: str) -> bool:
        """Check if a client is currently connected and the connection is valid"""
        if client_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[client_id]
            # Check if the websocket is in a connected state
            return websocket.client_state.name not in ["DISCONNECTED", "DISCONNECTING"]
        except Exception:
            # If we can't check the state, assume disconnected
            return False

    def get_client_info_summary(self) -> Dict[str, Any]:
        """Get a summary of all connected clients with their info"""
        clients = []
        for client_id in self.active_connections.keys():
            metadata = self.connection_metadata.get(client_id, {})
            client_info = {
                "client_id": client_id,
                "client_type": metadata.get("client_type", "unknown"),
                "device_type": metadata.get("device_type", "unknown"),
                "app_version": metadata.get("app_version", "unknown"),
                "connected_at": metadata.get("connected_at"),
                "info_received": metadata.get("info_received", False),
                "listening_state": metadata.get("listening_state", "inactive"),
            }
            clients.append(client_info)

        return {"total_clients": len(clients), "clients": clients}

    def is_jarvis_app_connected(self) -> bool:
        """Check if jarvis-app backend is connected"""
        return self.is_client_connected(self.jarvis_app_client_id)

    async def speech_to_text(self, audio_data: bytes) -> Optional[str]:
        """
        Convert speech to text via jarvis-app backend

        Args:
            audio_data: Audio data to transcribe

        Returns:
            Transcribed text or None
        """
        if not self.is_jarvis_app_connected():
            logger.error("jarvis-app backend not connected for STT")
            return None

        try:
            import base64

            # Generate unique request ID
            request_id = uuid.uuid4().hex

            # Convert bytes to base64 for JSON transmission
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")

            message_data = {
                "request_id": request_id,
                "audio_data": audio_b64,
                "format": "bytes",
                "timestamp": asyncio.get_event_loop().time(),
            }

            # Create future for response
            response_future = asyncio.Future()
            self.pending_requests[request_id] = response_future

            try:
                # Send STT request to jarvis-app
                success = await self.send_message_to_client(
                    self.jarvis_app_client_id, MessageType.STT_REQUEST, message_data
                )

                if not success:
                    logger.error("Failed to send STT request to jarvis-app")
                    return None

                # Wait for response with timeout
                try:
                    response = await asyncio.wait_for(response_future, timeout=10.0)
                    return response.get("text")
                except asyncio.TimeoutError:
                    logger.error("STT request timed out")
                    return None

            finally:
                # Clean up pending request
                self.pending_requests.pop(request_id, None)

        except Exception as e:
            logger.error(f"Error in speech_to_text: {e}")
            return None

    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """
        Convert text to speech via jarvis-app backend

        Args:
            text: Text to convert to speech

        Returns:
            Audio data or None
        """
        if not self.is_jarvis_app_connected():
            logger.error("jarvis-app backend not connected for TTS")
            return None

        try:
            # Generate unique request ID
            request_id = uuid.uuid4().hex

            message_data = {
                "request_id": request_id,
                "text": text,
                "timestamp": asyncio.get_event_loop().time(),
            }

            # Create future for response
            response_future = asyncio.Future()
            self.pending_requests[request_id] = response_future

            try:
                # Send TTS request to jarvis-app
                success = await self.send_message_to_client(
                    self.jarvis_app_client_id, MessageType.TTS_REQUEST, message_data
                )

                if not success:
                    logger.error("Failed to send TTS request to jarvis-app")
                    return None

                # Wait for response with timeout
                try:
                    response = await asyncio.wait_for(response_future, timeout=15.0)
                    audio_b64 = response.get("audio_data")
                    if audio_b64:
                        import base64

                        return base64.b64decode(audio_b64)
                    return None
                except asyncio.TimeoutError:
                    logger.error("TTS request timed out")
                    return None

            finally:
                # Clean up pending request
                self.pending_requests.pop(request_id, None)

        except Exception as e:
            logger.error(f"Error in text_to_speech: {e}")
            return None

    async def generate_response(self, user_input: str) -> Optional[str]:
        """
        Generate response using LLM via jarvis-app backend

        Args:
            user_input: User's input text

        Returns:
            Generated response
        """
        if not self.is_jarvis_app_connected():
            logger.error("jarvis-app backend not connected for LLM")
            return None

        try:
            # Generate unique request ID
            request_id = uuid.uuid4().hex

            message_data = {
                "request_id": request_id,
                "user_input": user_input,
                "timestamp": asyncio.get_event_loop().time(),
            }

            # Create future for response
            response_future = asyncio.Future()
            self.pending_requests[request_id] = response_future

            try:
                # Send LLM request to jarvis-app
                success = await self.send_message_to_client(
                    self.jarvis_app_client_id, MessageType.LLM_REQUEST, message_data
                )

                if not success:
                    logger.error("Failed to send LLM request to jarvis-app")
                    return None

                # Wait for response with timeout
                try:
                    response = await asyncio.wait_for(response_future, timeout=30.0)
                    return response.get("response")
                except asyncio.TimeoutError:
                    logger.error("LLM request timed out")
                    return None

            finally:
                # Clean up pending request
                self.pending_requests.pop(request_id, None)

        except Exception as e:
            logger.error(f"Error in generate_response: {e}")
            return None
