import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from usr.plugins.realtime_voice.helpers import session as rt
from usr.plugins.realtime_voice.helpers.config import normalize_config

OFFER = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\n"
ANSWER = "v=0\r\no=- 3 4 IN IP4 127.0.0.1\r\ns=answer\r\n"


def test_session_config_webrtc_defaults():
    session = rt.build_session_config(normalize_config({}), "be nice")
    assert session["type"] == "realtime"
    assert session["model"] == "gpt-realtime-2.1"
    assert session["instructions"] == "be nice"
    assert session["output_modalities"] == ["audio"]
    audio_in = session["audio"]["input"]
    assert audio_in["turn_detection"] == {
        "type": "semantic_vad",
        "eagerness": "auto",
        "create_response": True,
        "interrupt_response": True,
    }
    assert audio_in["transcription"] == {"model": "gpt-transcribe"}
    assert "format" not in audio_in  # WebRTC negotiates codecs itself
    assert session["audio"]["output"] == {"voice": "marin"}
    assert [t["name"] for t in session["tools"]] == [rt.DELEGATE_TOOL_NAME]
    assert session["tools"][0]["parameters"]["required"] == ["task"]
    assert session["tool_choice"] == "auto"


def test_session_config_websocket_server_vad_without_captions():
    cfg = normalize_config(
        {"turn_detection": "server_vad", "transcription_model": "", "voice": "cedar"}
    )
    session = rt.build_session_config(cfg, "x", transport="websocket")
    audio_in = session["audio"]["input"]
    assert audio_in["turn_detection"]["type"] == "server_vad"
    assert "eagerness" not in audio_in["turn_detection"]
    assert "transcription" not in audio_in
    assert audio_in["format"] == {"type": "audio/pcm", "rate": 24000}
    assert session["audio"]["output"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert session["audio"]["output"]["voice"] == "cedar"


def test_transcription_language_is_forwarded():
    cfg = normalize_config({"transcription_language": "de"})
    session = rt.build_session_config(cfg, "x")
    assert session["audio"]["input"]["transcription"] == {"model": "gpt-transcribe", "language": "de"}


def test_instructions_include_extra_and_history_and_no_placeholders():
    text = rt.build_instructions(
        normalize_config({"extra_instructions": "Call me Captain."}),
        ["User: hi", "Agent Zero: hello"],
    )
    assert "delegate_to_agent" in text
    assert "Call me Captain." in text
    assert "User: hi\nAgent Zero: hello" in text
    assert "{{" not in text

    plain = rt.build_instructions(normalize_config({}), [])
    assert "{{" not in plain
    assert "Additional instructions" not in plain
    assert "Recent messages" not in plain


def _log(*items):
    logs = [SimpleNamespace(type=t, content=c) for t, c in items]
    return SimpleNamespace(log=SimpleNamespace(logs=logs, _lock=threading.Lock()))


def test_chat_history_lines_picks_recent_user_and_response_messages():
    context = _log(
        ("user", "first question"),
        ("agent", "thinking..."),
        ("response", "first answer"),
        ("tool", "ls"),
        ("user", "second   question\nwith newline"),
        ("response", "x" * 1000),
    )
    lines = rt.chat_history_lines(context, 3)
    assert lines[0] == "Agent Zero: first answer"
    assert lines[1] == "User: second question with newline"
    assert lines[2].startswith("Agent Zero: xxx") and lines[2].endswith("...")
    assert len(lines[2]) <= len("Agent Zero: ") + rt.HISTORY_ENTRY_MAX_CHARS
    assert rt.chat_history_lines(context, 0) == []
    assert rt.chat_history_lines(None, 5) == []


def test_call_id_from_location():
    assert rt.call_id_from_location("/v1/realtime/calls/rtc_abc123") == "rtc_abc123"
    assert rt.call_id_from_location(None) == ""


@pytest.mark.asyncio
async def test_create_webrtc_call_posts_multipart_offer_and_session():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["content_type"] = request.headers.get("content-type")
        seen["body"] = request.read().decode()
        return httpx.Response(
            201, text=ANSWER, headers={"Location": "/v1/realtime/calls/rtc_xyz"}
        )

    session = rt.build_session_config(normalize_config({}), "hello")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        answer, call_id = await rt.create_webrtc_call(OFFER, session, "sk-test", client=client)

    assert answer == ANSWER
    assert call_id == "rtc_xyz"
    assert seen["url"] == "https://api.openai.com/v1/realtime/calls"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["content_type"].startswith("multipart/form-data")
    assert 'name="sdp"' in seen["body"] and OFFER in seen["body"]
    assert 'name="session"' in seen["body"]
    assert json.dumps(session) in seen["body"]


@pytest.mark.asyncio
async def test_create_webrtc_call_surfaces_openai_error_message():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "Incorrect API key provided"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(rt.RealtimeApiError) as err:
            await rt.create_webrtc_call(OFFER, {}, "bad", client=client)
    assert err.value.status == 401
    assert "Incorrect API key" in err.value.message


@pytest.mark.asyncio
async def test_create_webrtc_call_rejects_non_sdp_answer():
    def handler(request):
        return httpx.Response(200, text="<html>proxy page</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(rt.RealtimeApiError):
            await rt.create_webrtc_call(OFFER, {}, "sk", client=client)


# --- API handler -----------------------------------------------------------------

def _session_handler():
    from usr.plugins.realtime_voice.api.session import Session

    return Session(app=None, thread_lock=threading.RLock())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_session_api_returns_answer_and_keeps_key_server_side(monkeypatch):
    import usr.plugins.realtime_voice.api.session as api_session

    captured = {}

    async def fake_create(offer, session, api_key):
        captured.update(offer=offer, session=session, api_key=api_key)
        return ANSWER, "rtc_1"

    monkeypatch.setattr(api_session, "get_api_key", lambda: "sk-secret")
    monkeypatch.setattr(api_session, "create_webrtc_call", fake_create)
    monkeypatch.setattr(api_session.config, "is_enabled", lambda agent=None: True)

    out = await _session_handler().process({"sdp": OFFER}, request=None)  # type: ignore[arg-type]

    assert out["sdp"] == ANSWER
    assert out["call_id"] == "rtc_1"
    assert out["tool_name"] == rt.DELEGATE_TOOL_NAME
    assert out["ack_instructions"] == rt.ACK_INSTRUCTIONS
    assert "sk-secret" not in json.dumps(out)
    assert captured["api_key"] == "sk-secret"
    assert captured["offer"] == OFFER
    assert captured["session"]["tools"][0]["name"] == rt.DELEGATE_TOOL_NAME


@pytest.mark.asyncio
async def test_session_api_requires_key_and_valid_offer(monkeypatch):
    import usr.plugins.realtime_voice.api.session as api_session

    monkeypatch.setattr(api_session.config, "is_enabled", lambda agent=None: True)
    monkeypatch.setattr(api_session, "get_api_key", lambda: "")

    bad = await _session_handler().process({"sdp": "hello"}, request=None)  # type: ignore[arg-type]
    assert bad.status_code == 400

    no_key = await _session_handler().process({"sdp": OFFER}, request=None)  # type: ignore[arg-type]
    assert no_key.status_code == 400
    assert b"OpenAI" in no_key.get_data()


@pytest.mark.asyncio
async def test_session_api_maps_openai_errors_to_502(monkeypatch):
    import usr.plugins.realtime_voice.api.session as api_session

    async def failing(offer, session, api_key):
        raise rt.RealtimeApiError(401, "Incorrect API key provided")

    monkeypatch.setattr(api_session.config, "is_enabled", lambda agent=None: True)
    monkeypatch.setattr(api_session, "get_api_key", lambda: "sk")
    monkeypatch.setattr(api_session, "create_webrtc_call", failing)

    out = await _session_handler().process({"sdp": OFFER}, request=None)  # type: ignore[arg-type]
    assert out.status_code == 502
    assert b"OpenAI rejected the API key" in out.get_data()


@pytest.mark.asyncio
async def test_session_api_refuses_when_plugin_disabled(monkeypatch):
    import usr.plugins.realtime_voice.api.session as api_session

    monkeypatch.setattr(api_session.config, "is_enabled", lambda agent=None: False)
    out = await _session_handler().process({"sdp": OFFER}, request=None)  # type: ignore[arg-type]
    assert out.status_code == 409
