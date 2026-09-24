"""Hand a spoken request to the Agent Zero agent and return its final answer.

This follows the same path as the WebUI's ``/message`` endpoint: the request is
logged into the chat as a user message (so it is visible like a typed message),
passed to ``AgentContext.communicate`` and the final ``response`` is awaited.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import uuid
from typing import Any

from usr.plugins.realtime_voice.helpers.session import read_prompt

STATUS_COMPLETED = "completed"
STATUS_UPDATED = "added_to_running_task"
STATUS_STOPPED = "stopped"
STATUS_ERROR = "error"

TRIM_NOTE = "\n[Trimmed for voice. The full answer is in the chat.]"

# context id -> DeferredTask of the voice delegation currently being awaited
_inflight: dict[str, Any] = {}
_inflight_lock = threading.Lock()


def trim_result(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - len(TRIM_NOTE))].rstrip() + TRIM_NOTE


def voice_delegation_running(context_id: str) -> bool:
    with _inflight_lock:
        task = _inflight.get(context_id)
        return bool(task and task.is_alive())


async def delegate(context: Any, task_text: str, *, max_result_chars: int = 6000) -> dict[str, Any]:
    """Send ``task_text`` to the agent in ``context``.

    Returns ``{"status": ..., "output": ...}`` where ``output`` is what the voice
    model should relay to the user.
    """
    from agent import UserMessage
    from helpers import message_queue as mq

    text = (task_text or "").strip()
    if not text:
        return {"status": STATUS_ERROR, "output": "No task was given to the agent."}

    message_id = str(uuid.uuid4())
    # HTTP handlers can run on different threads. Select/deliver/register as one
    # operation, and compare task identity in case the prior run just finished.
    with _inflight_lock:
        previous = _inflight.get(context.id)
        mq.log_user_message(context, text, [], message_id=message_id, source=" (voice)")
        task = context.communicate(
            UserMessage(
                message=text,
                system_message=[read_prompt("realtime_voice.agent_hint.md")],
                id=message_id,
            )
        )
        already_delegating = previous is not None and task is previous
        if not already_delegating:
            _inflight[context.id] = task

    if already_delegating:
        # communicate() delivered the text as an intervention to the running
        # agent; the earlier delegate call will carry the combined result.
        return {
            "status": STATUS_UPDATED,
            "output": (
                "Passed to the agent as an update to the task it is already working on. "
                "The result will arrive with the earlier request."
            ),
        }

    try:
        result = await task.result()
    except (asyncio.CancelledError, concurrent.futures.CancelledError):
        if task.is_alive():
            raise  # this request itself was cancelled, not the agent
        return {"status": STATUS_STOPPED, "output": "The agent was stopped before it finished."}
    except Exception:  # Provider exceptions may contain credentials or private data.
        return {"status": STATUS_ERROR, "output": "The agent failed. Check the Agent Zero chat for details."}
    finally:
        with _inflight_lock:
            if _inflight.get(context.id) is task:
                del _inflight[context.id]

    answer = str(result or "").strip()
    if not answer:
        return {
            "status": STATUS_ERROR,
            "output": "The agent finished without a final answer. Details may be in the chat.",
        }
    return {"status": STATUS_COMPLETED, "output": trim_result(answer, max_result_chars)}
