import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from fastapi import WebSocket
from enum import Enum
from pathlib import Path
from jarvis_agent.services.audio.audio_handler import AudioHandler

if TYPE_CHECKING:
    from jarvis_agent.services.voice_processor import VoiceProcessor

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
    Manages WebSocket connection for a single authenticated client.
    """

    def __init__(
        self,
        audio_handler: Optional["AudioHandler"] = None,
        voice_processor: Optional["VoiceProcessor"] = None,
    ):
        # Store single active connection
        self.active_connection: Optional[WebSocket] = None
        self.client_id: Optional[str] = None
        self.connection_metadata: Dict[str, Any] = {}
        self.SECRET_PASSWORD = "TEMP_PASS"

        # Store pending requests for request-response matching
        self.pending_requests: Dict[str, asyncio.Future] = {}

        # Audio handler for playing sounds
        self.audio_handler = audio_handler

        # Voice processor for controlling listening
        self.voice_processor = voice_processor

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        password: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Accept a new WebSocket connection after password authentication.

        Args:
            websocket: The WebSocket connection
            client_id: Unique identifier for the client
            password: Authentication password
            metadata: Optional metadata about the client (device info, etc.)
        """
        # Check password first
        if password != self.SECRET_PASSWORD:
            await websocket.close(code=4001, reason="Invalid password")
            logger.warning(f"Authentication failed for client {client_id}")
            return False

        # If another client is already connected, disconnect them
        if self.active_connection is not None:
            logger.info(
                f"Disconnecting existing client {self.client_id} for new connection"
            )
            await self.disconnect()

        try:
            await websocket.accept()
            logger.debug(f"WebSocket accepted for client {client_id}")
        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection for {client_id}: {e}")
            raise

        self.active_connection = websocket
        self.client_id = client_id
        connection_metadata = metadata or {}
        connection_metadata["connected_at"] = asyncio.get_event_loop().time()
        self.connection_metadata = connection_metadata

        logger.info(f"Client {client_id} connected successfully and authenticated")

        # Send welcome message
        try:
            await self.send_message_to_client(
                MessageType.SYSTEM_STATUS,
                {"status": "connected", "message": "Welcome to J.A.R.V.I.S Agent"},
            )
        except Exception as e:
            logger.error(f"Failed to send welcome message to {client_id}: {e}")

        return True

    async def disconnect(self):
        """
        Disconnect the current client and clean up resources.
        """
        if self.active_connection is not None:
            try:
                # Only try to close if not already disconnected
                if self.active_connection.client_state.name not in [
                    "DISCONNECTED",
                    "DISCONNECTING",
                ]:
                    await self.active_connection.close()
            except Exception as e:
                logger.debug(f"Error closing connection for {self.client_id}: {e}")

            # Always clean up
            self.active_connection = None
            old_client_id = self.client_id
            self.client_id = None
            self.connection_metadata = {}

            logger.info(f"Client {old_client_id} disconnected")

    async def send_message_to_client(
        self, message_type: MessageType, data: Any
    ) -> bool:
        """
        Send a message to the connected client.

        Args:
            message_type: Type of message
            data: Message payload

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if self.active_connection is None or self.client_id is None:
            logger.debug("No client connected")
            return False

        try:
            # Check if the websocket connection is still valid and connected
            if self.active_connection.client_state.name not in ["CONNECTED"]:
                logger.debug(
                    f"Client {self.client_id} is not connected (state: {self.active_connection.client_state.name})"
                )
                await self.disconnect()
                return False

            message = {
                "type": message_type.value,
                "timestamp": asyncio.get_event_loop().time(),
                "data": data,
            }

            await self.active_connection.send_text(json.dumps(message))
            logger.debug(f"Sent message to {self.client_id}: {message_type.value}")
            return True

        except Exception as e:
            logger.error(f"Error sending message to {self.client_id}: {e}")
            await self.disconnect()
            return False

    async def broadcast_message(
        self,
        message_type: MessageType,
        data: Any,
        exclude_clients: Optional[List[str]] = None,
    ):
        """
        Send a message to the connected client (single client implementation).

        Args:
            message_type: Type of message
            data: Message payload
            exclude_clients: Not used in single client implementation
        """
        success = await self.send_message_to_client(message_type, data)
        if success:
            logger.info(f"Sent {message_type.value} to client")
        else:
            logger.warning(f"Failed to send {message_type.value} to client")

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
                    MessageType.ERROR,
                    {"error": f"Unknown message type: {message_type}"},
                )
                return {"status": "error", "message": "Unknown message type"}

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {client_id}: {e}")
            await self.send_message_to_client(
                MessageType.ERROR, {"error": "Invalid JSON format"}
            )
            return {"status": "error", "message": "Invalid JSON"}

        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
            await self.send_message_to_client(
                MessageType.ERROR, {"error": "Internal server error"}
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
            MessageType.TEXT_MESSAGE,
            {"message": response_text, "from": "jarvis"},
        )

        return {"status": "processed", "message": message}

    async def _handle_system_status_request(
        self, client_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle system status request"""
        status = {
            "active_connections": 1 if self.active_connection else 0,
            "server_status": "running",
            "connected_clients": [self.client_id] if self.client_id else [],
        }

        await self.send_message_to_client(MessageType.SYSTEM_STATUS, status)

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
        if self.client_id:
            self.connection_metadata.update(
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
                MessageType.ERROR,
                {"error": f"Unknown agent command: {command}"},
            )
            return {"status": "error", "message": "Unknown agent command"}

        # Send acknowledgment back to client
        await self.send_message_to_client(
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

        if not self.audio_handler:
            logger.warning("No audio handler available for audio testing")
            return {"action": "test_audio", "result": "No audio handler available"}

        try:
            # Try to play a test audio file if it exists
            test_audio_path = (
                Path(__file__).parent.parent / "assets" / "audio" / "test_audio.wav"
            )
            if test_audio_path.exists():
                logger.info(f"Playing test audio file: {test_audio_path}")
                await self.audio_handler.play_audio_file(test_audio_path)
                return {
                    "action": "test_audio",
                    "result": "Test audio file played successfully",
                }
            else:
                logger.info("Test audio file not found, skipping audio test")
                return {"action": "test_audio", "result": "Test audio file not found"}

        except Exception as e:
            logger.error(f"Error playing test audio: {e}")
            return {"action": "test_audio", "result": f"Audio test failed: {str(e)}"}

    async def _handle_start_listening(self, client_id: str) -> Dict[str, Any]:
        """Handle start listening command"""
        logger.info(f"Starting listening mode for client {client_id}")

        if not self.voice_processor:
            logger.warning("No voice processor available for listening control")
            return {
                "action": "start_listening",
                "result": "No voice processor available",
            }

        try:
            # Enable voice listening in the voice processor
            self.voice_processor.enable_listening()

            # Update client metadata to indicate listening state
            if self.client_id:
                self.connection_metadata["listening_state"] = "active"

            logger.info("Voice listening activated successfully")
            return {"action": "start_listening", "result": "Listening mode activated"}

        except Exception as e:
            logger.error(f"Error starting listening mode: {e}")
            return {
                "action": "start_listening",
                "result": f"Failed to start listening: {str(e)}",
            }

    async def _handle_stop_listening(self, client_id: str) -> Dict[str, Any]:
        """Handle stop listening command"""
        logger.info(f"Stopping listening mode for client {client_id}")

        if not self.voice_processor:
            logger.warning("No voice processor available for listening control")
            return {
                "action": "stop_listening",
                "result": "No voice processor available",
            }

        try:
            # Disable voice listening in the voice processor
            self.voice_processor.disable_listening()

            # Update client metadata to indicate listening state
            if self.client_id:
                self.connection_metadata["listening_state"] = "inactive"

            logger.info("Voice listening deactivated successfully")
            return {"action": "stop_listening", "result": "Listening mode deactivated"}

        except Exception as e:
            logger.error(f"Error stopping listening mode: {e}")
            return {
                "action": "stop_listening",
                "result": f"Failed to stop listening: {str(e)}",
            }

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
        self,
        client_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle TTS response from jarvis-app"""
        logger.info(f"Received TTS response from {client_id}")

        # Extract the audio data and request ID
        audio_data = payload.get("audio_data")  # Base64 encoded
        request_id = payload.get("request_id")
        sample_rate = payload.get("sample_rate", 24000)  # Default to 24kHz

        # Complete the pending request if it exists
        if request_id and request_id in self.pending_requests:
            future = self.pending_requests[request_id]
            if not future.done():
                future.set_result({"audio_data": audio_data})

        # Play the audio if we have an audio handler and audio data
        if self.audio_handler and audio_data:
            try:
                # Decode base64 audio data and play it
                import base64

                audio_bytes = base64.b64decode(audio_data)
                await self.audio_handler.play_audio(audio_bytes, sample_rate)
                logger.info("TTS audio played successfully")
            except Exception as e:
                logger.error(f"Error playing TTS audio: {e}")

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
        """Clean up connection if it's no longer valid"""
        if self.active_connection is None:
            return

        try:
            if self.active_connection.client_state.name in [
                "DISCONNECTED",
                "DISCONNECTING",
            ]:
                logger.info(f"Cleaning up stale connection for client {self.client_id}")
                await self.disconnect()
        except Exception:
            # If we can't check the state, consider it stale
            logger.info(f"Cleaning up stale connection for client {self.client_id}")
            await self.disconnect()

    def get_connected_clients(self) -> List[str]:
        """Get list of connected client IDs"""
        return [self.client_id] if self.client_id else []

    def get_client_metadata(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific client"""
        if client_id == self.client_id:
            return self.connection_metadata
        return None

    def is_client_connected(self, client_id: str) -> bool:
        """Check if a client is currently connected and the connection is valid"""
        if client_id != self.client_id or self.active_connection is None:
            return False

        try:
            # Check if the websocket is in a connected state
            return self.active_connection.client_state.name == "CONNECTED"
        except Exception as e:
            logger.debug(f"Error checking connection state for {client_id}: {e}")
            # If we can't check the state, assume disconnected
            return False

    def get_client_info_summary(self) -> Dict[str, Any]:
        """Get a summary of all connected clients with their info"""
        if not self.client_id or not self.active_connection:
            return {"total_clients": 0, "clients": []}

        # Get the actual listening state from voice processor if available
        listening_state = "unknown"
        if self.voice_processor:
            listening_state = (
                "active" if self.voice_processor.is_listening_enabled() else "inactive"
            )
        else:
            listening_state = self.connection_metadata.get(
                "listening_state", "inactive"
            )

        client_info = {
            "client_id": self.client_id,
            "client_type": self.connection_metadata.get("client_type", "unknown"),
            "device_type": self.connection_metadata.get("device_type", "unknown"),
            "app_version": self.connection_metadata.get("app_version", "unknown"),
            "connected_at": self.connection_metadata.get("connected_at"),
            "info_received": self.connection_metadata.get("info_received", False),
            "listening_state": listening_state,
        }

        return {"total_clients": 1, "clients": [client_info]}

    def is_listening_enabled(self) -> bool:
        """Check if voice listening is currently enabled"""
        if self.voice_processor:
            return self.voice_processor.is_listening_enabled()
        return False

    # Methods for voice processing integration
    async def speech_to_text(self, audio_data: bytes) -> str:
        """
        Convert speech audio to text.
        This is a placeholder - integrate with actual STT service.

        Args:
            audio_data: Raw audio bytes

        Returns:
            Transcribed text
        """
        logger.info("STT request received (placeholder implementation)")
        # TODO: Implement actual speech-to-text conversion
        # For now, return empty string to prevent errors
        return ""

    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech audio.
        This is a placeholder - integrate with actual TTS service.

        Args:
            text: Text to convert to speech

        Returns:
            Audio data as bytes
        """
        logger.info(
            f"TTS request received for text: '{text}' (placeholder implementation)"
        )
        # TODO: Implement actual text-to-speech conversion
        # For now, return empty bytes to prevent errors
        return b""

    async def text_to_speech_and_play(self, text: str) -> bool:
        """
        Convert text to speech and play it immediately using the audio handler.

        Args:
            text: Text to convert to speech

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.audio_handler:
            logger.warning("No audio handler available for TTS playback")
            return False

        try:
            # Get audio data from TTS
            audio_data = await self.text_to_speech(text)
            if audio_data:
                # Play the audio
                await self.audio_handler.play_audio(audio_data)
                logger.info(f"TTS audio played for text: '{text}'")
                return True
            else:
                logger.warning("No audio data received from TTS")
                return False
        except Exception as e:
            logger.error(f"Error in text_to_speech_and_play: {e}")
            return False

    async def generate_response(self, user_input: str) -> str:
        """
        Generate response using LLM.
        This is a placeholder - integrate with actual LLM service.

        Args:
            user_input: User's input text

        Returns:
            Generated response text
        """
        logger.info(
            f"LLM request received for input: '{user_input}' (placeholder implementation)"
        )
        # TODO: Implement actual LLM response generation
        # For now, return a simple echo response
        return f"I heard you say: {user_input}. This is a placeholder response."
