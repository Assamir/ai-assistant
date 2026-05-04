"""
API routes for the Assystent backend.
Defines REST endpoints and WebSocket connections.
"""

from fastapi import APIRouter, Depends
from typing import Any

router = APIRouter()

@router.get("/status")
async def get_status():
    """Get system status"""
    return {"status": "running", "message": "Assystent backend is operational"}

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@router.get("/config")
async def get_config():
    """Get current configuration"""
    return {"config": "placeholder"}

@router.post("/voice/transcribe")
async def transcribe_voice():
    """Endpoint for voice transcription"""
    return {"message": "Voice transcription placeholder"}

@router.post("/voice/speak")
async def speak_text():
    """Endpoint for text-to-speech"""
    return {"message": "Text-to-speech placeholder"}

# WebSocket endpoint will be added later