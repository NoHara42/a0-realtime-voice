from agent import AgentContext
from helpers.api import ApiHandler, Request, Response
from usr.plugins.realtime_voice.helpers import config, delegation


class Delegate(ApiHandler):
    """Run a task spoken to the voice model through the Agent Zero agent and return its answer.

    Blocks until the agent finishes, like the core /message endpoint.
    """

    async def process(self, input: dict, request: Request) -> dict | Response:
        if not isinstance(input, dict):
            return Response(status=400, response="Expected a JSON object")
        task = input.get("task", "")
        if not isinstance(task, str) or len(task) > 20000:
            return Response(status=400, response="Task must be a string of at most 20000 characters")
        task = task.strip()
        if not task:
            return Response(status=400, response="Missing task")

        context = AgentContext.get(str(input.get("ctxid") or "").strip())
        if context is None:
            return Response(status=404, response="Chat no longer exists. Start a new voice call.")
        agent = context.agent0

        if not config.is_enabled(agent):
            return Response(status=409, response="Realtime Voice plugin is disabled")

        cfg = config.get_config(agent)
        result = await delegation.delegate(
            context, task, max_result_chars=int(cfg["max_result_chars"])
        )
        if result.get("status") == delegation.STATUS_ERROR:
            # Keep this boundary safe even if an agent extension returns a raw
            # exception message instead of the helper's normal safe summary.
            result = {"status": delegation.STATUS_ERROR,
                      "output": "The agent failed. Check the Agent Zero chat for details."}
        return {**result, "context_id": context.id, "call_id": str(input.get("call_id") or "")}
