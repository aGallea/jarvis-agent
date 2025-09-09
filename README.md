# jarvis-agent
On-device software that brings J.A.R.V.I.S to life, handling voice and interaction.

## Features

### Voice Processing
- **Continuous Voice Listening**: Runs alongside the FastAPI server to continuously listen for voice commands
- **Wake Word Detection**: Listens for "JARVIS" wake word to activate voice command processing
- **Speech-to-Text**: Converts voice commands to text for processing
- **Text-to-Speech**: Converts responses back to speech for voice interaction
- **Background Processing**: Voice listening runs asynchronously without blocking the web server

### API Endpoints
- **Health Check**: `/health` - Server health status
- **WebSocket**: `/ws` - Real-time communication
- **Voice Control**:
  - `POST /voice/start-continuous` - Start continuous listening mode
  - `POST /voice/stop-continuous` - Stop continuous listening mode
  - `GET /voice/status` - Get current voice listening status

## Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Server**:
   ```bash
   python -m jarvis_agent
   ```

The server will start on the configured host/port and automatically begin listening for voice commands in the background.

## Architecture

The application consists of:

- **FastAPI Server**: Main web server handling HTTP requests and WebSocket connections
- **Voice Processor**: Background service for continuous voice listening and processing
- **Audio Handler**: Manages microphone input and speaker output using sounddevice
- **WebSocket Manager**: Handles real-time communication with clients

## Voice Processing Flow

1. **Background Listening**: The voice processor continuously listens for audio input
2. **Wake Word Detection**: When "JARVIS" is detected, the system activates
3. **Command Processing**: User speaks a command, which is converted to text
4. **Response Generation**: The system generates an appropriate response
5. **Speech Output**: The response is converted to speech and played back

## Development

The voice processing uses a stub implementation of `JarvisAppClient` for development. Replace `/jarvis_agent/services/jarvis_app_client_stub.py` with the actual implementation when available.

### File Structure
```
jarvis_agent/
├── services/
│   ├── voice_processor.py          # Main voice processing logic
│   ├── audio/
│   │   ├── audio_handler.py        # Audio input/output management
│   │   └── sounddevice_audio_handler.py
│   ├── jarvis_app_client_stub.py   # Stub implementation (replace with real client)
│   └── websocket_manager.py
├── routes/
│   ├── voice_control.py            # Voice control API endpoints
│   ├── health.py
│   └── websocket.py
└── app.py                          # Main FastAPI application
```
