"""
Voice processing module for wake word detection and voice commands
"""

import asyncio
import logging
import time

from jarvis_agent.services.websocket_manager import WebSocketManager
from jarvis_agent.services.audio.audio_handler import AudioHandler

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """Handles voice processing including wake word detection and command processing"""

    def __init__(
        self, audio_handler: AudioHandler, websocket_manager: WebSocketManager
    ):
        self.audio_handler = audio_handler
        self.websocket_manager = websocket_manager
        self.wake_word = "JARVIS"
        self.is_listening = False
        self.last_activity_time = time.time()

    def _record_voice_until_silence_sync(self):
        return self.audio_handler.record_voice_until_silence()

    async def listen_for_wake_word(self):
        """Listen for wake word activation"""
        try:
            # Record short audio clip for wake word detection
            audio_data = await asyncio.to_thread(self._record_voice_until_silence_sync)

            # audio_data = await self.audio_handler.record_audio(duration=2.0)
            if not audio_data:
                return
            # for debugging, play back the recorded audio
            # await self.audio_handler.play_audio(audio_data)

            # Convert to text and check for wake word
            text = await self.websocket_manager.speech_to_text(audio_data)
            if text and self.wake_word.lower() in text.lower():
                logger.info("Wake word detected!")
            # print(text)
            #     await self.handle_wake_word_activation()

        except Exception as e:
            logger.error(f"Error in wake word detection: {e}")

    async def handle_wake_word_activation(self):
        """Handle wake word activation and start listening for command"""
        try:
            # Play activation sound or speak confirmation
            await self.speak_response("Yes?")

            # Listen for actual command
            await self.process_voice_command()

        except Exception as e:
            logger.error(f"Error handling wake word activation: {e}")

    async def process_voice_command(self):
        """Process a voice command from user"""
        try:
            logger.info("Listening for voice command...")

            # Record user command
            audio_data = self.audio_handler.record_voice_until_silence()
            # audio_data = await self.audio_handler.record_audio(duration=5.0)
            if not audio_data:
                logger.warning("No audio data received")
                return

            await self.audio_handler.play_audio(audio_data)
            # Convert speech to text
            user_input = await self.websocket_manager.speech_to_text(audio_data)
            if not user_input:
                logger.warning("Could not transcribe audio")
                await self.speak_response("I didn't catch that. Could you repeat?")
                return

            logger.info(f"User said: {user_input}")

            # Generate response using LLM
            response = await self.websocket_manager.generate_response(user_input)
            if not response:
                response = "I'm having trouble processing your request right now."

            # Convert response to speech and play
            await self.speak_response(response)

        except Exception as e:
            logger.error(f"Error processing voice command: {e}")
            await self.speak_response("Sorry, I encountered an error.")

    async def speak_response(self, text: str):
        """Convert text to speech and play it"""
        try:
            logger.info(f"Speaking: {text}")

            # Get audio from TTS service
            audio_data = await self.websocket_manager.text_to_speech(text)
            if audio_data:
                await self.audio_handler.play_audio(audio_data)
            else:
                logger.error("Failed to generate TTS audio")

        except Exception as e:
            logger.error(f"Error in speech response: {e}")

    async def start_continuous_listening(self):
        """Start continuous listening mode"""
        logger.info("Starting continuous listening mode...")
        self.is_listening = True

        await self.audio_handler.start_continuous_recording()

        try:
            while self.is_listening:
                # Get audio chunk
                audio_chunk = await self.audio_handler.get_audio_chunk()
                if audio_chunk:
                    # Simple voice activity detection (placeholder)
                    if self.detect_voice_activity(audio_chunk):
                        self.last_activity_time = time.time()
                        logger.debug("Voice activity detected")

                    # Check for silence timeout
                    if time.time() - self.last_activity_time > 3.0:
                        logger.info("Silence detected, processing command...")
                        await self.process_recorded_command()
                        self.last_activity_time = time.time()

                await asyncio.sleep(0.1)

        finally:
            await self.audio_handler.stop_continuous_recording()

    async def stop_continuous_listening(self):
        """Stop continuous listening mode"""
        logger.info("Stopping continuous listening mode...")
        self.is_listening = False

    async def process_recorded_command(self):
        """Process command from continuous recording"""
        try:
            # Stop recording and get audio data
            audio_data = await self.audio_handler.stop_continuous_recording()
            if audio_data:
                # Process the command
                user_input = await self.websocket_manager.speech_to_text(audio_data)
                if user_input and user_input.strip():
                    logger.info(f"Continuous mode - User said: {user_input}")

                    response = await self.websocket_manager.generate_response(
                        user_input
                    )
                    if response:
                        await self.speak_response(response)

            # Restart continuous recording
            await self.audio_handler.start_continuous_recording()

        except Exception as e:
            logger.error(f"Error processing recorded command: {e}")

    def detect_voice_activity(self, audio_chunk: bytes) -> bool:
        """
        Simple voice activity detection
        This is a placeholder - in a real implementation you'd use
        proper VAD algorithms or libraries
        """
        # Placeholder implementation
        # In reality, you'd analyze the audio amplitude, frequency, etc.
        return len(audio_chunk) > 0  # Simplified check

    async def execute_command(self, command: str) -> str:
        """
        Execute specific commands locally

        Args:
            command: Command to execute

        Returns:
            Response text
        """
        command_lower = command.lower().strip()

        # Basic local commands
        if "time" in command_lower:
            current_time = time.strftime("%H:%M %p")
            return f"The current time is {current_time}"

        elif "date" in command_lower:
            current_date = time.strftime("%A, %B %d, %Y")
            return f"Today is {current_date}"

        elif "hello" in command_lower or "hi" in command_lower:
            return "Hello! How can I help you today?"

        elif "goodbye" in command_lower or "bye" in command_lower:
            return "Goodbye! Have a great day!"

        return "I'm not sure how to help with that."
        # For other commands, use the backend LLM
        # else:
        #     return await self.backend_client.generate_response(command)
