"""
Voice router for Hume AI EVI integration.
Provides endpoints for token generation and voice chat WebSocket proxy.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

import structlog
from agents.auth.auth0_config import (
    get_current_user_id,
    token_verifier,
    extract_user_id,
)
from agents.services.voice_service import HumeVoiceService
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketState

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/voice",
    tags=["voice"],
)


def detect_agent_intent(transcription: str) -> Optional[str]:
    """
    Detect if transcription is just a basic acknowledgment.

    Returns None for very basic acknowledgments (EVI handles),
    otherwise returns "general" (send to backend agents).

    Philosophy: Almost everything goes to backend agents, they provide final_completion,
    and EVI speaks it naturally. This ensures consistent, up-to-date responses.
    """
    transcription_lower = transcription.lower().strip()

    # Only the most basic acknowledgments - EVI handles these
    basic_acknowledgments = [
        "hi", "hello", "hey",
        "thanks", "thank you",
        "bye", "goodbye",
        "ok", "okay", "sure"
    ]

    if transcription_lower in basic_acknowledgments:
        return None

    # Everything else goes to backend agents
    # This includes: greetings with questions, capability questions, tasks, analysis, etc.
    return "general"


@router.post("/token")
async def get_voice_token(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Generate a short-lived access token for Hume EVI.

    This endpoint is called by the frontend to get a token for
    establishing a WebSocket connection to Hume EVI.

    Returns:
        JSON with access_token and expires_in
    """
    try:
        voice_service = HumeVoiceService(request.app.state.redis_storage_service)
        token_data = await voice_service.generate_access_token()

        if not token_data:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Voice service unavailable. Please configure Hume API credentials."
                },
            )

        logger.info("Generated voice token for user", user_id=user_id[:8])

        return JSONResponse(
            status_code=200,
            content=token_data,
        )

    except Exception as e:
        logger.error(f"Error generating voice token: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate voice token: {str(e)}"},
        )


@router.get("/config")
async def get_voice_config(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get user's voice configuration preferences.

    Returns:
        JSON with voice settings (voice_name, narration_enabled, etc.)
    """
    try:
        voice_service = HumeVoiceService(request.app.state.redis_storage_service)
        config = await voice_service.get_voice_config(user_id)

        return JSONResponse(
            status_code=200,
            content=config,
        )

    except Exception as e:
        logger.error(f"Error retrieving voice config: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve voice config: {str(e)}"},
        )


@router.post("/config")
async def save_voice_config(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Save user's voice configuration preferences.

    Expects JSON body with voice settings.
    """
    try:
        config_data = await request.json()
        voice_service = HumeVoiceService(request.app.state.redis_storage_service)
        success = await voice_service.save_voice_config(user_id, config_data)

        if success:
            return JSONResponse(
                status_code=200,
                content={"message": "Voice config saved successfully"},
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to save voice config"},
            )

    except Exception as e:
        logger.error(f"Error saving voice config: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to save voice config: {str(e)}"},
        )


@router.websocket("/chat")
async def voice_chat_websocket(
    websocket: WebSocket,
    conversation_id: str,
):
    """
    WebSocket endpoint that bridges frontend voice chat with the backend agent system.

    This endpoint:
    1. Receives audio input from frontend
    2. Manages voice transcription state
    3. Injects transcribed messages into the existing chat workflow
    4. Streams agent updates back as voice notifications

    Args:
        websocket: WebSocket connection from frontend
        conversation_id: ID of the conversation
    """
    user_id = None

    try:
        await websocket.accept()

        # Wait for authentication message
        auth_message = await websocket.receive_json()

        if auth_message.get("type") != "auth":
            await websocket.send_json({
                "type": "error",
                "error": "Authentication required as first message"
            })
            await websocket.close()
            return

        # Extract and validate token
        token = auth_message.get("token", "").replace("Bearer ", "")
        if not token:
            await websocket.send_json({
                "type": "error",
                "error": "No authentication token provided"
            })
            await websocket.close()
            return

        # Validate token with Auth0
        try:
            payload = token_verifier.verify(token)
            user_id = extract_user_id(payload)
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "error": "Invalid authentication token"
            })
            await websocket.close()
            return

        logger.info(
            "Voice WebSocket connection established",
            user_id=user_id[:8],
            conversation_id=conversation_id,
        )

        # Register voice WebSocket with manager (voice-specific messages only)
        await websocket.app.state.manager.add_voice_connection(
            websocket=websocket,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        # Don't register as main connection - let ChatView's WebSocket remain the main connection
        # This way UI updates work in real-time through the regular chat WebSocket
        # Voice WebSocket only receives voice-specific messages (agent_response, agent_context)

        # Send connection established message
        await websocket.send_json({
            "type": "voice_connection_established",
            "data": "Voice mode active",
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        voice_service = HumeVoiceService(websocket.app.state.redis_storage_service)

        # Get user context for voice session
        context = await voice_service.get_user_context(user_id, conversation_id)
        voice_config = await voice_service.get_voice_config(user_id)

        # Send session settings to frontend
        session_settings = voice_service.get_session_settings(
            system_prompt=context["system_prompt"],
            context=context["context"],
            variables=context["variables"],
            voice_name=voice_config.get("voice_name", "ITO"),
        )

        # Include config_id for EVI connection
        config_id = os.getenv("HUME_EVI_CONFIG_ID")

        await websocket.send_json({
            "type": "session_settings",
            "data": session_settings,
            "config_id": config_id,  # Send config_id to frontend
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Handle incoming voice messages
        while True:
            try:
                message_text = await websocket.receive_text()
                message_data = json.loads(message_text)

                message_type = message_data.get("type")

                if message_type == "voice_transcription":
                    # User's speech has been transcribed by frontend/Hume
                    transcription = message_data.get("text", "")

                    logger.info(
                        "Received voice transcription",
                        user_id=user_id[:8],
                        transcription=transcription[:50],
                    )

                    # Send acknowledgment
                    await websocket.send_json({
                        "type": "transcription_received",
                        "text": transcription,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                    # EVI tool calling handles intent - this is a tool call query
                    logger.info(
                        "Received tool call query from EVI",
                        user_id=user_id[:8],
                        query=transcription[:50],
                    )

                    # Inject into backend agent workflow and get message ID
                    success, actual_message_id = await websocket.app.state.manager.inject_voice_message(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        message_text=transcription,
                        message_id=message_data.get("message_id"),
                    )

                    # Notify frontend to show agent workflow on screen
                    await websocket.send_json({
                        "type": "agent_triggered",
                        "intent": "tool_call",
                        "text": transcription,
                        "message_id": actual_message_id,  # Include the backend-generated ID
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif message_type == "audio_chunk":
                    # Frontend sending raw audio chunks
                    # TODO: Implement speech-to-text processing here
                    # For now, just silently acknowledge to avoid warnings
                    logger.debug(
                        "Received audio chunk",
                        user_id=user_id[:8],
                        chunk_size=len(message_data.get("data", "")),
                    )
                    # Once we have transcription, we would call inject_voice_message here

                elif message_type == "voice_status":
                    # Frontend sending status updates (listening, speaking, etc.)
                    status = message_data.get("status")
                    logger.debug(
                        "Voice status update",
                        user_id=user_id[:8],
                        status=status,
                    )

                elif message_type == "ping":
                    # Keep-alive ping
                    await websocket.send_json({"type": "pong"})

                else:
                    logger.warning(
                        f"Unknown voice message type: {message_type}",
                        user_id=user_id[:8],
                    )

            except json.JSONDecodeError:
                logger.error("Invalid JSON in voice message")
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid message format",
                })
                continue

    except WebSocketDisconnect:
        logger.info(
            "Voice WebSocket disconnected",
            user_id=user_id[:8] if user_id else "unknown",
            conversation_id=conversation_id,
        )

    except Exception as e:
        logger.error(
            f"Error in voice WebSocket: {str(e)}",
            user_id=user_id[:8] if user_id else "unknown",
            conversation_id=conversation_id,
        )

        # Try to send error message
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                })
        except:
            pass

    finally:
        # Remove voice connection from manager
        if user_id:
            try:
                # Always remove voice connection
                websocket.app.state.manager.remove_voice_connection(
                    user_id=user_id,
                    conversation_id=conversation_id,
                )

                # If this voice WebSocket was registered as main (voice-only mode),
                # remove it from main connections too
                main_connection = websocket.app.state.manager.get_connection(
                    user_id, conversation_id
                )
                if main_connection == websocket:
                    websocket.app.state.manager.remove_connection(
                        user_id=user_id,
                        conversation_id=conversation_id,
                    )
                    logger.info(
                        "Removed voice WebSocket from main connections",
                        user_id=user_id[:8],
                    )
            except:
                pass

        # Clean up
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except:
            pass

        logger.info(
            "Voice WebSocket connection closed",
            user_id=user_id[:8] if user_id else "unknown",
            conversation_id=conversation_id,
        )
