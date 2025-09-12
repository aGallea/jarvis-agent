import logging
import wave

from pathlib import Path
from typing import Optional
import array
import sounddevice as sd
import numpy as np

logger = logging.getLogger(__name__)


class SounddeviceAudioHandler:
    """Alternative audio handler using sounddevice and simpleaudio"""

    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = np.int16
        self.array_typecode = "h"  # For array.array (16-bit signed)

        # Recording state
        self.is_recording = False
        self.recorded_data = None
        self.stream = None

    async def initialize(self):
        """Initialize audio system"""
        try:
            # if SOUNDDEVICE_AVAILABLE:
            # Test sounddevice
            sd.check_output_settings()
            sd.check_input_settings()
            logger.info("Audio system initialized with sounddevice")
            return True
            # elif PLAYSOUND3_AVAILABLE:
            #     logger.info("Audio system initialized with playsound3 (playback only)")
            #     return True
            # else:
            #     logger.error("No audio libraries available")
            #     return False
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            return False

    async def cleanup(self):
        """Cleanup audio resources"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
        logger.info("Audio system cleaned up")

    async def record_audio(self, duration: float = 5.0) -> Optional[bytes]:
        """
        Record audio for specified duration using sounddevice

        Args:
            duration: Recording duration in seconds

        Returns:
            Audio data as bytes or None if failed
        """
        try:
            logger.info(f"Recording audio for {duration} seconds...")

            # Record audio

            audio_data = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
            )
            sd.wait()  # Wait until recording is finished

            # Convert to bytes (audio_data is a numpy array-like from sounddevice)
            audio_bytes = audio_data.tobytes()
            logger.info("Audio recording completed")
            return audio_bytes

        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            return None

    async def play_audio(self, audio_data: bytes):
        """
        Play audio data through speakers

        Args:
            audio_data: Audio data to play
        """
        try:
            # if SOUNDDEVICE_AVAILABLE:
            await self._play_with_sounddevice(audio_data)
            # elif PLAYSOUND3_AVAILABLE:
            #     await self._play_with_playsound3(audio_data)
            # else:
            #     logger.error("No audio playback libraries available")

        except Exception as e:
            logger.error(f"Error playing audio: {e}")

    async def _play_with_sounddevice(self, audio_data: bytes):
        """Play audio using sounddevice"""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=self.dtype)

            # Reshape if stereo
            if self.channels == 2:
                audio_array = audio_array.reshape(-1, 2)

            logger.info("Playing audio with sounddevice...")
            sd.play(audio_array, samplerate=self.sample_rate)
            sd.wait()  # Wait until playback is finished
            logger.info("Audio playback completed")

        except Exception as e:
            logger.error(f"sounddevice playback error: {e}")
            raise

    async def play_audio_file(self, file_path: Path):
        """Play audio from WAV file"""
        try:
            with wave.open(str(file_path), "rb") as wf:
                # Get the file's audio properties
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())

                logger.info(f"Playing audio file: {file_path}")
                logger.info(
                    f"File properties - Sample rate: {sample_rate}Hz, Channels: {channels}, Sample width: {sample_width} bytes"
                )

                # Convert frames to numpy array with correct dtype based on sample width
                if sample_width == 1:
                    dtype = np.uint8
                elif sample_width == 2:
                    dtype = np.int16
                elif sample_width == 4:
                    dtype = np.int32
                else:
                    logger.error(f"Unsupported sample width: {sample_width}")
                    return

                audio_array = np.frombuffer(frames, dtype=dtype)

                # Reshape if stereo
                if channels == 2:
                    audio_array = audio_array.reshape(-1, 2)

                # Play using the file's original sample rate
                logger.info("Playing audio with sounddevice...")
                sd.play(audio_array, samplerate=sample_rate)
                sd.wait()  # Wait until playback is finished
                logger.info("Audio playback completed")

        except Exception as e:
            logger.error(f"Error playing audio file: {e}")

    async def save_audio_to_file(self, audio_data: bytes, file_path: Path):
        """Save audio data to WAV file"""
        try:
            with wave.open(str(file_path), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data)
            logger.info(f"Audio saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")

    # Continuous recording methods for compatibility
    async def start_continuous_recording(self):
        """Start continuous recording"""
        # if not SOUNDDEVICE_AVAILABLE:
        # logger.error("Continuous recording requires sounddevice")
        # return

        self.is_recording = True
        self.recorded_data = []

        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning(f"Audio callback status: {status}")
            if self.is_recording and self.recorded_data is not None:
                self.recorded_data.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                callback=audio_callback,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
            )
            self.stream.start()
            logger.info("Started continuous recording")
        except Exception as e:
            logger.error(f"Error starting continuous recording: {e}")
            self.is_recording = False

    async def stop_continuous_recording(self) -> Optional[bytes]:
        """Stop continuous recording and return audio data"""
        if not self.is_recording or not self.stream:
            return None

        try:
            self.is_recording = False
            self.stream.stop()
            self.stream.close()
            self.stream = None

            if self.recorded_data:
                # Concatenate all recorded chunks using array
                audio_array = array.array(self.array_typecode)
                for chunk in self.recorded_data:
                    audio_array.extend(chunk.flatten())
                audio_bytes = audio_array.tobytes()
                logger.info("Continuous recording stopped")
                return audio_bytes

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")

        return None

    async def get_audio_chunk(self) -> Optional[bytes]:
        """Get a chunk of audio during continuous recording"""
        # For this implementation, we collect everything and return in stop_continuous_recording
        # This is a simplified version - in practice you might want to yield chunks
        if self.is_recording and self.recorded_data:
            return b"chunk"  # Placeholder
        return None

    def record_voice_until_silence(self, should_stop_callback=None):
        """Record audio until silence is detected using energy-based VAD."""
        SAMPLE_RATE = 16000
        FRAME_DURATION = 30  # ms
        FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)

        # Energy-based voice activity detection parameters
        ENERGY_THRESHOLD = 1000000  # Adjust based on your environment
        SILENCE_FRAMES_THRESHOLD = 20  # ~600ms silence
        NON_RELEVANT_SILENCE_FRAMES_THRESHOLD = (
            120  # ~3 seconds of non-relevant silence
        )
        HIGH_ENERGY_FRAMES_THRESHOLD = (
            5  # Minimum high energy frames to consider valid speech
        )
        ZCR_MIN = 0.05  # Minimum zero-crossing rate to consider as speech

        print("🎤 Listening...")
        buffer = []
        silence_frames = 0
        high_energy = 0
        speaking = False
        iteration = 0

        def is_speech_frame(frame: np.ndarray):
            if len(frame) == 0:
                return False

            energy = np.sum(frame.astype(np.int32) ** 2) / len(frame)
            # print(f"Energy: {energy}")

            # Calculate zero-crossing rate with proper handling of edge cases
            if len(frame) <= 1:
                zcr = 0.0
            else:
                # Flatten frame if it's 2D
                frame_flat = frame.flatten()
                sign_changes = np.diff(np.sign(frame_flat))
                # Only count actual zero crossings (non-zero changes)
                zcr = (
                    np.sum(np.abs(sign_changes) > 0) / (len(frame_flat) - 1)
                    if len(frame_flat) > 1
                    else 0.0
                )

            # print(f"ZCR: {zcr}")
            is_speech_frame = energy > ENERGY_THRESHOLD and zcr > ZCR_MIN
            if is_speech_frame:
                print(f"Energy: {energy}, ZCR: {zcr}")
            return is_speech_frame

        with sd.InputStream(
            channels=1, samplerate=SAMPLE_RATE, dtype="int16"
        ) as stream:
            while True:
                iteration += 1

                # Check if we should stop recording (external signal)
                if should_stop_callback and should_stop_callback():
                    logger.info("🛑 Recording stopped by external signal")
                    break

                # print("reading stream...")
                frame, _ = stream.read(FRAME_SIZE)
                # print("frame read done.")

                # Convert frame to array for energy calculation
                # frame_array = array.array("h", frame.flatten())

                # Calculate energy (sum of squares)
                # energy = sum(sample * sample for sample in frame_array)
                # Simple energy-based voice activity detection
                # if energy > ENERGY_THRESHOLD and iteration > 5:
                if is_speech_frame(frame):
                    print("🗣️ Speech frame detected")
                    high_energy += 1
                    if not speaking:
                        speaking = True
                    # print(f"high energy: {energy}")
                    buffer.append(frame)
                    silence_frames = 0
                else:
                    if speaking:
                        # print(f"low energy: {energy}")
                        silence_frames += 1
                        if (
                            silence_frames > SILENCE_FRAMES_THRESHOLD
                            and high_energy > HIGH_ENERGY_FRAMES_THRESHOLD
                        ):
                            print("🤫 Silence detected, stopping...")
                            break
                        elif silence_frames > NON_RELEVANT_SILENCE_FRAMES_THRESHOLD:
                            print("🔇 Too much silence, stopping...")
                            break
                        # Add small amount of silence frames to buffer when speaking
                        buffer.append(frame)

        # Concatenate all frames
        # audio_array = array.array("h")
        # for chunk in buffer:
        #     audio_array.extend(chunk)
        return b"".join(buffer)
