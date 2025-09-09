"""
Voice control API routes
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from jarvis_agent.dependencies import get_voice_processor
from jarvis_agent.services.voice_processor import VoiceProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/start-continuous")
async def start_continuous_listening(
    voice_processor: VoiceProcessor = Depends(get_voice_processor),
) -> Dict[str, str]:
    """Start continuous listening mode for voice commands"""
    try:
        await voice_processor.start_continuous_listening()
        return {"status": "success", "message": "Continuous listening started"}
    except Exception as e:
        logger.error(f"Error starting continuous listening: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop-continuous")
async def stop_continuous_listening(
    voice_processor: VoiceProcessor = Depends(get_voice_processor),
) -> Dict[str, str]:
    """Stop continuous listening mode"""
    try:
        await voice_processor.stop_continuous_listening()
        return {"status": "success", "message": "Continuous listening stopped"}
    except Exception as e:
        logger.error(f"Error stopping continuous listening: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_voice_status(
    voice_processor: VoiceProcessor = Depends(get_voice_processor),
) -> Dict[str, Any]:
    """Get current voice listening status"""
    return {
        "is_listening": voice_processor.is_listening,
        "wake_word": voice_processor.wake_word,
    }
