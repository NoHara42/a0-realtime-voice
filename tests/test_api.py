import threading
from unittest.mock import AsyncMock

import httpx
import pytest

from usr.plugins.realtime_voice.api import session as session_api
from usr.plugins.realtime_voice.api.delegate import Delegate


@pytest.fixture
def handler(monkeypatch):
    monkeypatch.setattr(session_api.config, 'is_enabled', lambda agent: True)
    monkeypatch.setattr(session_api, 'get_api_key', lambda: 'test-secret-never-return')
    return session_api.Session(None, threading.RLock())


@pytest.mark.asyncio
async def test_session_rejects_bad_sdp_and_missing_key(handler, monkeypatch):
    assert (await handler.process({'sdp':'invalid'}, None)).status_code == 400
    monkeypatch.setattr(session_api, 'get_api_key', lambda: '')
    assert (await handler.process({'sdp':'v=0'}, None)).status_code == 400


@pytest.mark.asyncio
async def test_session_disabled_before_openai_call(handler, monkeypatch):
    monkeypatch.setattr(session_api.config, 'is_enabled', lambda agent: False)
    assert (await handler.process({'sdp':'v=0'}, None)).status_code == 409


@pytest.mark.asyncio
async def test_session_returns_sdp_without_credentials(handler, monkeypatch):
    create = AsyncMock(return_value=('v=0\r\nanswer', 'rtc_test'))
    monkeypatch.setattr(session_api, 'create_webrtc_call', create)
    result = await handler.process({'sdp':'v=0\r\noffer'}, None)
    assert result['sdp'] == 'v=0\r\nanswer'
    assert result['call_id'] == 'rtc_test'
    assert 'test-secret' not in str(result)
    assert create.call_args.args[2] == 'test-secret-never-return'
    assert handler.requires_auth() and handler.requires_csrf()


@pytest.mark.asyncio
async def test_network_error_is_actionable_gateway_error(handler, monkeypatch):
    monkeypatch.setattr(session_api, 'create_webrtc_call', AsyncMock(side_effect=httpx.ConnectError('unreachable')))
    result = await handler.process({'sdp':'v=0'}, None)
    assert result.status_code == 502
    assert 'Check network' in result.get_data(as_text=True)


@pytest.mark.asyncio
async def test_deleted_chat_is_not_recreated():
    result = await Delegate(None, threading.RLock()).process({'ctxid':'deleted-voice-test','task':'run code'}, None)
    assert result.status_code == 404
