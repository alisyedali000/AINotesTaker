"""OpenAI wrappers for STT, LLM reasoning, and TTS streaming."""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.agent import AgentAction

logger = logging.getLogger(__name__)

# Strict JSON schema: every property must appear in "required" (use null when unused).
AGENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "create_task",
                "read_tasks",
                "update_task",
                "delete_task",
                "ask_followup",
                "confirm_delete",
                "clarify",
                "noop",
            ],
        },
        "title": {"type": ["string", "null"]},
        "datetime": {"type": ["string", "null"]},
        "task_id": {"type": ["integer", "null"]},
        "task_ids": {
            "type": ["array", "null"],
            "items": {"type": "integer"},
        },
        "tasks": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "datetime": {"type": "string"},
                },
                "required": ["title", "datetime"],
                "additionalProperties": False,
            },
        },
        "filter_date": {"type": ["string", "null"]},
        "filter_time_of_day": {"type": ["string", "null"]},
        "response_text": {"type": "string"},
        "pending_delete_task_id": {"type": ["integer", "null"]},
        "reference_hint": {"type": ["string", "null"]},
    },
    "required": [
        "action",
        "title",
        "datetime",
        "task_id",
        "task_ids",
        "tasks",
        "filter_date",
        "filter_time_of_day",
        "response_text",
        "pending_delete_task_id",
        "reference_hint",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """You are a friendly voice assistant for a task manager app.
The user speaks naturally; you interpret their intent and return structured JSON actions.

Current date/time (UTC): {now_iso}

RULES:
1. Always include a natural, conversational response_text suitable for text-to-speech.
2. For create_task: extract title and ISO datetime. Support multiple tasks via "tasks" array.
3. For read_tasks: set filter_date (today/tomorrow/YYYY-MM-DD) and/or filter_time_of_day.
4. For update_task: use task_id when known from context, or reference_hint for semantic matching.
5. For delete_task: NEVER delete immediately. Use action "confirm_delete" with pending_delete_task_id
   and ask the user to confirm. Only use delete_task when user clearly confirms (yes, sure, do it).
6. For ask_followup or clarify: when ambiguous, ask a short clarifying question in response_text.
7. Use conversation history and recently referenced tasks to resolve "second one", "that task", etc.
8. If user confirms a pending delete, action=delete_task with the task_id.
9. Keep responses concise and warm — this is voice, not text chat.

Recently referenced tasks (most recent first):
{recent_tasks}

Pending delete confirmation task_id: {pending_delete}

Conversation history:
{history}
"""


class OpenAIService:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
        """Speech-to-text using OpenAI transcription API with model fallback."""
        if len(audio_bytes) < 500:
            raise ValueError("Audio too short to transcribe")

        ext = "webm"
        content_type = "audio/webm"
        if "wav" in mime_type:
            ext, content_type = "wav", "audio/wav"
        elif "mp4" in mime_type or "m4a" in mime_type:
            ext, content_type = "mp4", "audio/mp4"
        elif "ogg" in mime_type:
            ext, content_type = "ogg", "audio/ogg"

        models = [settings.stt_model, "whisper-1"]
        seen: set[str] = set()
        last_error: Exception | None = None

        for model in models:
            if model in seen:
                continue
            seen.add(model)
            try:
                file_obj = io.BytesIO(audio_bytes)
                file_obj.name = f"recording.{ext}"

                # New transcribe models prefer json; whisper accepts text
                response_format = "json" if "transcribe" in model else "text"
                transcription = await self.client.audio.transcriptions.create(
                    model=model,
                    file=(file_obj.name, file_obj, content_type),
                    response_format=response_format,
                    language="en",
                )
                text = self._extract_transcript_text(transcription)
                if text:
                    logger.info("STT success with model=%s (%d bytes)", model, len(audio_bytes))
                    return text
            except Exception as e:
                last_error = e
                logger.warning("STT model %s failed: %s", model, e)

        logger.exception("STT failed for all models: %s", last_error)
        raise last_error or RuntimeError("Transcription failed")

    @staticmethod
    def _extract_transcript_text(transcription: Any) -> str:
        if isinstance(transcription, str):
            return transcription.strip()
        if hasattr(transcription, "text"):
            return str(transcription.text).strip()
        return str(transcription).strip()

    async def reason(
        self,
        user_message: str,
        history: list[dict[str, str]],
        recent_tasks: list[dict],
        pending_delete: int | None,
        now_iso: str,
    ) -> AgentAction:
        """LLM structured reasoning for next action."""
        recent_str = json.dumps(recent_tasks, indent=2) if recent_tasks else "[]"
        history_str = "\n".join(f"{m['role']}: {m['content']}" for m in history[-12:])

        system = SYSTEM_PROMPT.format(
            now_iso=now_iso,
            recent_tasks=recent_str,
            pending_delete=pending_delete or "none",
            history=history_str or "(empty)",
        )

        models = [settings.llm_model, "gpt-4o-mini"]
        seen: set[str] = set()
        last_error: Exception | None = None

        for model in models:
            if model in seen:
                continue
            seen.add(model)
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "agent_action",
                            "strict": True,
                            "schema": AGENT_JSON_SCHEMA,
                        },
                    },
                    temperature=0.3,
                )
                raw = response.choices[0].message.content or "{}"
                data: dict[str, Any] = json.loads(raw)
                return AgentAction.model_validate(data)
            except Exception as e:
                last_error = e
                logger.warning("LLM model %s failed: %s", model, e)

        logger.exception("LLM reasoning failed for all models: %s", last_error)
        return AgentAction(
            action="clarify",
            response_text="I'm having a bit of trouble right now. Could you say that again?",
        )

    async def stream_tts(self, text: str) -> AsyncIterator[bytes]:
        """Stream TTS audio chunks with model fallback."""
        models = [settings.tts_model, "tts-1"]
        seen: set[str] = set()
        last_error: Exception | None = None

        for model in models:
            if model in seen:
                continue
            seen.add(model)
            try:
                async with self.client.audio.speech.with_streaming_response.create(
                    model=model,
                    voice=settings.tts_voice,
                    input=text,
                    response_format="mp3",
                ) as response:
                    async for chunk in response.iter_bytes(chunk_size=4096):
                        if chunk:
                            yield chunk
                    return
            except Exception as e:
                last_error = e
                logger.warning("TTS model %s failed: %s", model, e)

        logger.exception("TTS failed for all models: %s", last_error)
        raise last_error or RuntimeError("TTS failed")

    @staticmethod
    def encode_audio_chunk(data: bytes) -> str:
        return base64.b64encode(data).decode("utf-8")
