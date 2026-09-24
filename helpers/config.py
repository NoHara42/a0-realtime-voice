from __future__ import annotations

from typing import Any

PLUGIN_NAME = "realtime_voice"

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "gpt-realtime-2.1",
    "voice": "marin",
    "turn_detection": "semantic_vad",
    "vad_eagerness": "auto",
    "transcription_model": "gpt-transcribe",
    "transcription_language": "",
    "extra_instructions": "",
    "history_messages": 6,
    "max_result_chars": 6000,
}

VOICES = (
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
)
TURN_DETECTION_TYPES = ("semantic_vad", "server_vad")
VAD_EAGERNESS = ("low", "medium", "high", "auto")


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, low), high)


def normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Return a complete, validated config; unknown or invalid values fall back to defaults."""
    normalized = dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        return normalized

    model = str(config.get("model") or "").strip()
    if model:
        normalized["model"] = model

    voice = str(config.get("voice") or "").strip().lower()
    if voice in VOICES:
        normalized["voice"] = voice

    turn_detection = str(config.get("turn_detection") or "").strip().lower()
    if turn_detection in TURN_DETECTION_TYPES:
        normalized["turn_detection"] = turn_detection

    eagerness = str(config.get("vad_eagerness") or "").strip().lower()
    if eagerness in VAD_EAGERNESS:
        normalized["vad_eagerness"] = eagerness

    # An explicit empty transcription model disables captions.
    if "transcription_model" in config:
        normalized["transcription_model"] = str(
            config.get("transcription_model") or ""
        ).strip()

    language = str(config.get("transcription_language") or "").strip().lower()
    normalized["transcription_language"] = language if language != "auto" else ""

    normalized["extra_instructions"] = str(config.get("extra_instructions") or "").strip()

    normalized["history_messages"] = _clamp_int(
        config.get("history_messages"), DEFAULT_CONFIG["history_messages"], 0, 50
    )
    normalized["max_result_chars"] = _clamp_int(
        config.get("max_result_chars"), DEFAULT_CONFIG["max_result_chars"], 500, 50000
    )

    return normalized


def get_config(agent=None) -> dict[str, Any]:
    """Effective config for the agent's project/profile scope (or the global scope)."""
    from helpers import plugins

    return normalize_config(plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {})


def is_enabled(agent=None) -> bool:
    from helpers import plugins

    return PLUGIN_NAME in plugins.get_enabled_plugins(agent)
