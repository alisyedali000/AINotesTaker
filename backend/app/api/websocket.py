"""WebSocket endpoint for real-time voice interaction."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.conversation import ConversationOrchestrator
from app.agents.session import get_session, remove_session
from app.database.connection import async_session_factory
from app.services.openai_service import OpenAIService
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)
router = APIRouter()


class VoiceConnection:
    """Manages one WebSocket voice session with interrupt support."""

    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.audio_buffer = bytearray()
        self.audio_mime = "audio/webm"
        self.client_transcript_hint = ""
        self.openai = OpenAIService()
        self.session_state = get_session(session_id)
        self._tts_task: asyncio.Task | None = None
        self._processing = False
        self._cancel_tts = asyncio.Event()

    async def send_json(self, data: dict[str, Any]) -> None:
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            logger.warning("Failed to send WS message: %s", e)

    async def send_status(self, status: str) -> None:
        await self.send_json({"type": "status", "status": status})

    async def handle_message(self, data: dict[str, Any]) -> None:
        msg_type = data.get("type")

        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return

        if msg_type == "interrupt":
            await self._handle_interrupt()
            return

        # Legacy chunked upload (invalid webm if concatenated) — prefer audio_upload
        if msg_type == "audio_chunk":
            chunk_b64 = data.get("data", "")
            if chunk_b64:
                self.audio_buffer.extend(base64.b64decode(chunk_b64))
            if data.get("mime"):
                self.audio_mime = data["mime"]
            return

        if msg_type == "audio_upload":
            chunk_b64 = data.get("data", "")
            if chunk_b64:
                self.audio_buffer = bytearray(base64.b64decode(chunk_b64))
            if data.get("mime"):
                self.audio_mime = data["mime"]
            return

        if msg_type == "text_hint":
            self.client_transcript_hint = (data.get("text") or "").strip()
            return

        if msg_type == "audio_end":
            await self._process_utterance()
            return

        if msg_type == "text":
            # Fallback for testing without microphone
            text = data.get("text", "").strip()
            if text:
                await self._run_conversation_turn(text)
            return

    async def _handle_interrupt(self) -> None:
        """Cancel ongoing TTS and notify client."""
        self._cancel_tts.set()
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass
        self._tts_task = None
        await self.send_json({"type": "tts_cancelled"})
        await self.send_status("listening")

    async def _process_utterance(self) -> None:
        if self._processing:
            await self._handle_interrupt()

        if len(self.audio_buffer) < 100:
            await self.send_json({
                "type": "error",
                "message": "I didn't hear anything. Could you try again?",
            })
            await self.send_status("listening")
            return

        self._processing = True
        await self.send_status("processing")
        audio_bytes = bytes(self.audio_buffer)
        self.audio_buffer.clear()

        transcript = ""
        try:
            transcript = await self.openai.transcribe_audio(audio_bytes, self.audio_mime)
        except Exception as e:
            logger.error("STT error (%d bytes, %s): %s", len(audio_bytes), self.audio_mime, e)
            if self.client_transcript_hint:
                transcript = self.client_transcript_hint
                logger.info("Using browser transcript hint fallback")

        if not transcript.strip():
            if self.client_transcript_hint:
                transcript = self.client_transcript_hint
            else:
                await self.send_json({
                    "type": "transcript",
                    "role": "assistant",
                    "text": "I didn't fully catch that. Could you repeat?",
                })
                await self._speak("I didn't fully catch that. Could you repeat?")
                self._processing = False
                self.client_transcript_hint = ""
                await self.send_status("listening")
                return

        self.client_transcript_hint = ""

        await self.send_json({"type": "transcript", "role": "user", "text": transcript})
        await self._run_conversation_turn(transcript)
        self._processing = False

    async def _run_conversation_turn(self, user_text: str) -> None:
        async with async_session_factory() as db_session:
            orchestrator = ConversationOrchestrator(
                openai=self.openai,
                task_service=TaskService(db_session),
                session=self.session_state,
            )
            response_text, _action = await orchestrator.process_user_text(user_text)

        await self.send_json({"type": "transcript", "role": "assistant", "text": response_text})
        await self._speak(response_text)

    async def _speak(self, text: str) -> None:
        """Stream TTS to client with interrupt support."""
        self._cancel_tts.clear()
        await self.send_json({"type": "tts_start"})
        await self.send_status("speaking")

        async def _stream() -> None:
            try:
                async for chunk in self.openai.stream_tts(text):
                    if self._cancel_tts.is_set():
                        break
                    await self.send_json({
                        "type": "audio_chunk",
                        "data": OpenAIService.encode_audio_chunk(chunk),
                        "format": "mp3",
                    })
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("TTS stream error: %s", e)
                await self.send_json({
                    "type": "error",
                    "message": "I had trouble speaking that response.",
                })

        self._tts_task = asyncio.create_task(_stream())
        try:
            await self._tts_task
        except asyncio.CancelledError:
            pass
        finally:
            if not self._cancel_tts.is_set():
                await self.send_json({"type": "tts_end"})
            await self.send_status("listening")


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = str(uuid.uuid4())
    conn = VoiceConnection(websocket, session_id)

    await conn.send_json({"type": "connected", "session_id": session_id})
    await conn.send_status("listening")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await conn.send_json({"type": "error", "message": "Invalid message format"})
                continue
            await conn.handle_message(data)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        try:
            await conn.send_json({"type": "error", "message": "Connection error. Please reconnect."})
        except Exception:
            pass
    finally:
        if conn._tts_task and not conn._tts_task.done():
            conn._tts_task.cancel()
        remove_session(session_id)
