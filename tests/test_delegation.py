import asyncio
import concurrent.futures
import threading

import pytest

from agent import AgentContext
from initialize import initialize_agent
from usr.plugins.realtime_voice.helpers import delegation
from usr.plugins.realtime_voice.helpers.session import read_prompt


class FakeTask:
    """Stands in for the DeferredTask returned by AgentContext.communicate."""

    def __init__(self, result=None, exc=None, gate: asyncio.Event | None = None):
        self._future = concurrent.futures.Future()

        def finish():
            if isinstance(exc, concurrent.futures.CancelledError):
                self._future.cancel()
            elif exc:
                self._future.set_exception(exc)
            else:
                self._future.set_result(result)

        if gate:
            async def wait():
                await gate.wait()
                finish()
            asyncio.create_task(wait())
        else:
            finish()

    def is_alive(self):
        return not self._future.done()


@pytest.fixture
def context():
    ctx = AgentContext(config=initialize_agent())
    try:
        yield ctx
    finally:
        AgentContext.remove(ctx.id)


def _patch_communicate(monkeypatch, context, *tasks):
    sent = []
    queue = list(tasks)

    def communicate(msg, broadcast_level=1):
        sent.append(msg)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(context, "communicate", communicate)
    return sent


def _user_logs(context):
    return [item for item in context.log.logs if item.type == "user"]


@pytest.mark.asyncio
async def test_delegate_logs_user_message_and_returns_agent_answer(monkeypatch, context):
    sent = _patch_communicate(monkeypatch, context, FakeTask(result="The time is 10:42."))

    out = await delegation.delegate(context, "  What time is it?  ")

    assert out == {"status": delegation.STATUS_COMPLETED, "output": "The time is 10:42."}
    assert len(sent) == 1
    assert sent[0].message == "What time is it?"
    assert sent[0].system_message == [read_prompt("realtime_voice.agent_hint.md")]
    logged = _user_logs(context)
    assert logged and logged[-1].content == "What time is it?"
    assert logged[-1].id == sent[0].id  # chat row and history share the message id
    assert not delegation.voice_delegation_running(context.id)


@pytest.mark.asyncio
async def test_long_answers_are_trimmed_for_voice(monkeypatch, context):
    _patch_communicate(monkeypatch, context, FakeTask(result="word " * 1000))

    out = await delegation.delegate(context, "write an essay", max_result_chars=600)

    assert out["status"] == delegation.STATUS_COMPLETED
    assert len(out["output"]) <= 600
    assert out["output"].endswith(delegation.TRIM_NOTE)


@pytest.mark.asyncio
async def test_second_request_while_running_is_sent_as_update(monkeypatch, context):
    gate = asyncio.Event()
    running = FakeTask(result="Both done.", gate=gate)
    sent = _patch_communicate(monkeypatch, context, running)

    first = asyncio.create_task(delegation.delegate(context, "build the report"))
    await asyncio.sleep(0.05)
    assert delegation.voice_delegation_running(context.id)

    second = await delegation.delegate(context, "also add a chart")
    assert second["status"] == delegation.STATUS_UPDATED
    assert [m.message for m in sent] == ["build the report", "also add a chart"]

    gate.set()
    assert (await first) == {"status": delegation.STATUS_COMPLETED, "output": "Both done."}
    assert not delegation.voice_delegation_running(context.id)


@pytest.mark.asyncio
async def test_stopped_agent_is_reported(monkeypatch, context):
    _patch_communicate(
        monkeypatch, context, FakeTask(exc=concurrent.futures.CancelledError())
    )
    out = await delegation.delegate(context, "long job")
    assert out["status"] == delegation.STATUS_STOPPED


@pytest.mark.asyncio
async def test_finished_previous_task_does_not_swallow_new_result(monkeypatch, context):
    previous = FakeTask(result="old")
    delegation._inflight[context.id] = previous._future
    # The previous task can finish between selection and communicate(). A new
    # returned task must be awaited, not misreported as an intervention.
    _patch_communicate(monkeypatch, context, FakeTask(result="new result"))
    result = await delegation.delegate(context, "a new task")
    assert result == {"status": delegation.STATUS_COMPLETED, "output": "new result"}
    assert context.id not in delegation._inflight


@pytest.mark.asyncio
async def test_agent_failure_and_empty_answer_are_reported(monkeypatch, context):
    _patch_communicate(monkeypatch, context, FakeTask(exc=RuntimeError("model offline")))
    failed = await delegation.delegate(context, "job")
    assert failed["status"] == delegation.STATUS_ERROR
    assert "Check the Agent Zero chat" in failed["output"]
    assert "model offline" not in failed["output"]

    _patch_communicate(monkeypatch, context, FakeTask(result=None))
    empty = await delegation.delegate(context, "job")
    assert empty["status"] == delegation.STATUS_ERROR


@pytest.mark.asyncio
async def test_empty_task_is_rejected_without_contacting_agent(monkeypatch, context):
    sent = _patch_communicate(monkeypatch, context, FakeTask(result="x"))
    out = await delegation.delegate(context, "   ")
    assert out["status"] == delegation.STATUS_ERROR
    assert sent == []


@pytest.mark.asyncio
async def test_delegate_api_routes_task_to_requested_chat(monkeypatch, context):
    from usr.plugins.realtime_voice.api.delegate import Delegate
    import usr.plugins.realtime_voice.api.delegate as api_delegate

    monkeypatch.setattr(api_delegate.config, "is_enabled", lambda agent=None: True)
    _patch_communicate(monkeypatch, context, FakeTask(result="Listed 3 files."))

    handler = Delegate(app=None, thread_lock=threading.RLock())  # type: ignore[arg-type]
    out = await handler.process(
        {"ctxid": context.id, "task": "list files", "call_id": "call_1"},
        request=None,  # type: ignore[arg-type]
    )

    assert out == {
        "status": delegation.STATUS_COMPLETED,
        "output": "Listed 3 files.",
        "context_id": context.id,
        "call_id": "call_1",
    }

    missing = await handler.process({"ctxid": context.id}, request=None)  # type: ignore[arg-type]
    assert missing.status_code == 400


@pytest.mark.asyncio
async def test_reused_deferred_task_keeps_each_execution_and_cleanup(monkeypatch, context):
    from helpers.defer import DeferredTask

    # Use the framework wrapper with controlled execution futures. Complete the
    # first execution but leave its HTTP waiter pending while communicate starts
    # the next execution on the SAME wrapper.
    task = DeferredTask.__new__(DeferredTask)
    task.children = []
    first_future = concurrent.futures.Future()
    second_future = concurrent.futures.Future()
    executions = iter((first_future, second_future))

    def communicate(msg):
        task._future = next(executions)
        return task

    monkeypatch.setattr(context, "communicate", communicate)
    first = asyncio.create_task(delegation.delegate(context, "first"))
    await asyncio.sleep(0)
    first_future.set_result("first result")
    second = asyncio.create_task(delegation.delegate(context, "second"))
    await asyncio.sleep(0)
    assert task._future is second_future
    assert await first == {"status": "completed", "output": "first result"}
    assert delegation.voice_delegation_running(context.id)
    assert delegation._inflight[context.id] is second_future
    second_future.set_result("second result")
    assert await second == {"status": "completed", "output": "second result"}
    assert not delegation.voice_delegation_running(context.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_after_disconnect", [False, True])
async def test_cancelled_http_waiter_does_not_cancel_agent_execution(monkeypatch, context, fail_after_disconnect):
    import gc

    loop = asyncio.get_running_loop()
    errors = []
    old_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda loop, error: errors.append(error))
    task = FakeTask.__new__(FakeTask)
    task._future = concurrent.futures.Future()
    _patch_communicate(monkeypatch, context, task)
    waiter = asyncio.create_task(delegation.delegate(context, "keep working"))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert not task._future.cancelled()
    try:
        if fail_after_disconnect:
            task._future.set_exception(RuntimeError("private detached agent failure"))
        else:
            task._future.set_result("finished independently")
        # Drain wrap_future and its callbacks, then collect detached references.
        for _ in range(4):
            await asyncio.sleep(0)
        gc.collect()
        assert errors == []
        assert context.id not in delegation._inflight
    finally:
        loop.set_exception_handler(old_handler)
