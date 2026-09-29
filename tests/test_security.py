import threading
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from usr.plugins.realtime_voice.api import session as session_api
from usr.plugins.realtime_voice.api.delegate import Delegate
from usr.plugins.realtime_voice.api.status import Status


@pytest.mark.asyncio
@pytest.mark.parametrize('handler_type', [session_api.Session, Delegate, Status])
async def test_non_object_json_rejected(handler_type):
    handler = handler_type(None, threading.RLock())
    assert handler.requires_auth() and handler.requires_csrf()
    for invalid in ([], 'text', None, 42):
        response = await handler.process(invalid, None)
        assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize('sdp', [{}, ['v=0'], 'v=' + 'a' * 131072])
async def test_invalid_or_large_sdp_never_contacts_provider(monkeypatch, sdp):
    create = AsyncMock()
    monkeypatch.setattr(session_api, 'create_webrtc_call', create)
    response = await session_api.Session(None, threading.RLock()).process({'sdp': sdp}, None)
    assert response.status_code == 400
    create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('task', [{}, ['run code'], 'x' * 20001])
async def test_invalid_or_large_task_rejected_before_context_lookup(task):
    response = await Delegate(None, threading.RLock()).process({'task':task}, None)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_provider_error_cannot_echo_secrets_or_html(monkeypatch):
    secret = 'sensitive-provider-credential'
    raw = secret + ' <img src=x onerror=alert(1)>'
    monkeypatch.setattr(session_api.config, 'is_enabled', lambda agent: True)
    monkeypatch.setattr(session_api, 'get_api_key', lambda: secret)
    monkeypatch.setattr(session_api, 'create_webrtc_call', AsyncMock(
        side_effect=session_api.RealtimeApiError(401, raw)))
    logs = []
    monkeypatch.setattr(session_api.PrintStyle, 'error', logs.append)
    response = await session_api.Session(None, threading.RLock()).process({'sdp':'v=0'}, None)
    assert response.status_code == 502
    assert secret not in response.get_data(as_text=True) + str(logs)
    assert '<img' not in response.get_data(as_text=True) + str(logs)


@pytest.mark.asyncio
async def test_deleted_session_context_does_not_fall_back_to_global(monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(session_api, 'create_webrtc_call', create)
    response = await session_api.Session(None, threading.RLock()).process(
        {'ctxid':'security-test-deleted-context','sdp':'v=0'}, None)
    assert response.status_code == 404
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_delegate_endpoint_sanitizes_extension_error(monkeypatch):
    from usr.plugins.realtime_voice.api import delegate as api
    context = SimpleNamespace(id='test-context', agent0=object())
    monkeypatch.setattr(api.AgentContext, 'get', lambda ctxid: context)
    monkeypatch.setattr(api.config, 'is_enabled', lambda agent: True)
    monkeypatch.setattr(api.config, 'get_config', lambda agent: {'max_result_chars':6000})
    monkeypatch.setattr(api.delegation, 'delegate', AsyncMock(return_value={
        'status':'error','output':'private-provider-error-details'}))
    result = await Delegate(None, threading.RLock()).process({'task':'test','ctxid':context.id}, None)
    assert result['status'] == 'error'
    assert 'private-provider-error-details' not in str(result)


@pytest.mark.asyncio
async def test_delegate_submission_exception_cannot_escape_api(monkeypatch):
    from usr.plugins.realtime_voice.api import delegate as api
    context = SimpleNamespace(id='test-context', agent0=object())
    monkeypatch.setattr(api.AgentContext, 'get', lambda ctxid: context)
    monkeypatch.setattr(api.config, 'is_enabled', lambda agent: True)
    monkeypatch.setattr(api.config, 'get_config', lambda agent: {'max_result_chars': 6000})
    monkeypatch.setattr(api.delegation, 'delegate', AsyncMock(
        side_effect=RuntimeError('private submission hook details')))
    result = await Delegate(None, threading.RLock()).process(
        {'task': 'test', 'ctxid': context.id}, None)
    assert result['status'] == 'error'
    assert 'private submission hook details' not in str(result)
    assert 'Check the Agent Zero chat' in result['output']
