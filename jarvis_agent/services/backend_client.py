"""
Backend client service for communicating with the Jarvis backend server.
"""

import io
import logging
from typing import Any, Dict, Optional
import aiohttp
from aiohttp import FormData

logger = logging.getLogger(__name__)


class BackendClient:
    """Client for communicating with the Jarvis backend server"""

    def __init__(self, backend_url: str):
        """
        Initialize the backend client.

        Args:
            backend_url: Base URL of the backend server (e.g., "http://localhost:8000")
        """
        self.backend_url = backend_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def start(self):
        """Initialize the HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def speech_to_text(
        self, audio_data: bytes, filename: str = "audio.wav"
    ) -> Dict[str, Any]:
        """
        Convert speech to text using the backend STT service.

        Args:
            audio_data: Raw audio data in bytes
            filename: Name of the audio file (optional)

        Returns:
            Dictionary containing the transcribed text

        Raises:
            Exception: If the request fails or the backend returns an error
        """
        if not self.session:
            raise RuntimeError(
                "Backend client session not initialized. Call start() first."
            )

        try:
            # Create form data with the audio file
            data = FormData()
            data.add_field(
                "audio",
                io.BytesIO(audio_data),
                filename=filename,
                content_type="audio/wav",
            )

            async with self.session.post(
                f"{self.backend_url}/api/stt", data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.debug(f"STT response: {result}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(
                        f"STT request failed with status {response.status}: {error_text}"
                    )
                    raise Exception(
                        f"STT request failed: {response.status} - {error_text}"
                    )

        except aiohttp.ClientError as e:
            logger.error(f"STT request error: {e}")
            raise Exception(f"STT request error: {e}")

    async def generate_response(
        self, user_input: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate LLM response to user input.

        Args:
            user_input: User's input text
            context: Optional context dictionary

        Returns:
            Dictionary containing the generated response

        Raises:
            Exception: If the request fails or the backend returns an error
        """
        if not self.session:
            raise RuntimeError(
                "Backend client session not initialized. Call start() first."
            )

        request_data: Dict[str, Any] = {
            "user_input": user_input,
        }

        if context:
            request_data["context"] = context

        try:
            async with self.session.post(
                f"{self.backend_url}/api/generate", json=request_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.debug(f"Generate response: {result}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Generate request failed with status {response.status}: {error_text}"
                    )
                    raise Exception(
                        f"Generate request failed: {response.status} - {error_text}"
                    )

        except aiohttp.ClientError as e:
            logger.error(f"Generate request error: {e}")
            raise Exception(f"Generate request error: {e}")

    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech using the backend TTS service.

        Args:
            text: Text to convert to speech

        Returns:
            Audio data as bytes

        Raises:
            Exception: If the request fails or the backend returns an error
        """
        if not self.session:
            raise RuntimeError(
                "Backend client session not initialized. Call start() first."
            )

        request_data = {"text": text}

        try:
            async with self.session.post(
                f"{self.backend_url}/api/tts", json=request_data
            ) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    logger.debug(f"TTS response received: {len(audio_data)} bytes")
                    return audio_data
                else:
                    error_text = await response.text()
                    logger.error(
                        f"TTS request failed with status {response.status}: {error_text}"
                    )
                    raise Exception(
                        f"TTS request failed: {response.status} - {error_text}"
                    )

        except aiohttp.ClientError as e:
            logger.error(f"TTS request error: {e}")
            raise Exception(f"TTS request error: {e}")

    async def health_check(self) -> bool:
        """
        Check if the backend server is healthy.

        Returns:
            True if the server is healthy, False otherwise
        """
        if not self.session:
            await self.start()

        try:
            if self.session:
                async with self.session.get(
                    f"{self.backend_url}/health", timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
            return False
        except Exception as e:
            logger.warning(f"Backend health check failed: {e}")
            return False
