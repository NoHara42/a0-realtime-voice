"""Server-side Realtime session setup.

The browser never talks to OpenAI with a credential. It sends its WebRTC SDP
offer to Agent Zero, which forwards it together with the session config to
OpenAI's unified ``/v1/realtime/calls`` endpoint using the stored OpenAI API
key, and returns the SDP answer. Media then flows browser <-> OpenAI directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

OPENAI_BASE_URL = "https://api.openai.com/v1"
CALLS_URL = f"{OPENAI_BASE_URL}/realtime/calls"
WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"

DELEGATE_TOOL_NAME = "delegate_to_agent"

# Per-response instructions the client sends right after a delegate call so the
# user hears an acknowledgement instead of silence while the agent works.
ACK_INSTRUCTIONS = (
    "You just handed the user's request to Agent Zero, which is now working on it. "
    "Acknowledge that in a few words, like a colleague saying 'on it'. "
    "Do not guess, promise or describe the result, and do not ask a question."
)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

HISTORY_ENTRY_MAX_CHARS = 600


class RealtimeApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def get_api_key() -> str:
    """The OpenAI key from Agent Zero's normal API key settings (API_KEY_OPENAI)."""
    import models

    key = (models.get_api_key("openai") or "").strip()
    return "" if key in ("", "None") else key


def delegate_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "name": DELEGATE_TOOL_NAME,
        "description": (
            "Hand a request to Agent Zero, the autonomous agent that does the real work: "
            "running code and terminal commands, web search and browsing, reading and "
            "editing files, memory, and multi-step tasks. Returns the agent's final answer. "
            "Call it immediately, without speaking first. Tasks can take minutes; you may keep "
            "talking with the user while it runs. Calling it again while a task runs passes "
            "the new text to the running agent as an update."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "Complete, self-contained instruction for the agent, including every "
                        "relevant detail from the conversation. The agent cannot hear the call."
                    ),
                }
            },
            "required": ["task"],
            "additionalProperties": False,
        },
    }


def chat_history_lines(context: Any, limit: int) -> list[str]:
    """Recent user/agent messages of an Agent Zero chat, oldest first."""
    if not context or limit <= 0:
        return []
    log = getattr(context, "log", None)
    if log is None:
        return []
    lock = getattr(log, "_lock", None)
    if lock is not None:
        with lock:
            items = list(log.logs)
    else:
        items = list(getattr(log, "logs", []))

    lines: list[str] = []
    for item in reversed(items):
        kind = getattr(item, "type", "")
        if kind not in ("user", "response"):
            continue
        content = " ".join(str(getattr(item, "content", "") or "").split())
        if not content:
            continue
        if len(content) > HISTORY_ENTRY_MAX_CHARS:
            content = content[: HISTORY_ENTRY_MAX_CHARS - 3] + "..."
        speaker = "User" if kind == "user" else "Agent Zero"
        lines.append(f"{speaker}: {content}")
        if len(lines) >= limit:
            break
    lines.reverse()
    return lines


def build_instructions(config: dict[str, Any], history: list[str] | None = None) -> str:
    extra = str(config.get("extra_instructions") or "").strip()
    extra_block = f"\n## Additional instructions\n{extra}\n" if extra else ""
    history_block = ""
    if history:
        history_block = (
            "\n## Recent messages in the current Agent Zero chat (for context)\n"
            + "\n".join(history)
            + "\n"
        )
    return (
        read_prompt("realtime_voice.system.md")
        .replace("{{extra_instructions}}", extra_block)
        .replace("{{chat_history}}", history_block)
        .strip()
    )


def build_session_config(
    config: dict[str, Any],
    instructions: str,
    *,
    transport: str = "webrtc",
) -> dict[str, Any]:
    """Session object for /v1/realtime/calls (WebRTC) or session.update (WebSocket)."""
    if config.get("turn_detection") == "server_vad":
        turn_detection: dict[str, Any] = {
            "type": "server_vad",
            "create_response": True,
            "interrupt_response": True,
        }
    else:
        turn_detection = {
            "type": "semantic_vad",
            "eagerness": config.get("vad_eagerness") or "auto",
            "create_response": True,
            "interrupt_response": True,
        }

    audio_input: dict[str, Any] = {"turn_detection": turn_detection}
    audio_output: dict[str, Any] = {"voice": config.get("voice") or "marin"}

    transcription_model = str(config.get("transcription_model") or "").strip()
    if transcription_model:
        transcription: dict[str, Any] = {"model": transcription_model}
        language = str(config.get("transcription_language") or "").strip()
        if language:
            transcription["language"] = language
        audio_input["transcription"] = transcription

    if transport == "websocket":
        # WebRTC negotiates codecs itself; over WebSocket we exchange raw PCM16 @ 24 kHz.
        pcm = {"type": "audio/pcm", "rate": 24000}
        audio_input["format"] = dict(pcm)
        audio_output["format"] = dict(pcm)

    return {
        "type": "realtime",
        "model": config.get("model") or "gpt-realtime-2.1",
        "instructions": instructions,
        "output_modalities": ["audio"],
        "audio": {"input": audio_input, "output": audio_output},
        "tools": [delegate_tool()],
        "tool_choice": "auto",
    }


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    except Exception:
        pass
    text = (response.text or "").strip()
    return text[:500] or f"HTTP {response.status_code}"


def call_id_from_location(location: str | None) -> str:
    """`Location: /v1/realtime/calls/rtc_...` -> `rtc_...`"""
    if not location:
        return ""
    return location.rstrip("/").rsplit("/", 1)[-1]


async def create_webrtc_call(
    offer_sdp: str,
    session: dict[str, Any],
    api_key: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
) -> tuple[str, str]:
    """Forward the browser's SDP offer to OpenAI. Returns (answer_sdp, call_id)."""
    files = {
        "sdp": (None, offer_sdp),
        "session": (None, json.dumps(session)),
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout)
    try:
        response = await http.post(CALLS_URL, files=files, headers=headers)
    finally:
        if owns_client:
            await http.aclose()

    if response.status_code >= 400:
        raise RealtimeApiError(response.status_code, _error_message(response))

    answer = response.text
    if not answer.strip().startswith("v="):
        raise RealtimeApiError(502, "OpenAI did not return an SDP answer")
    return answer, call_id_from_location(response.headers.get("location"))
