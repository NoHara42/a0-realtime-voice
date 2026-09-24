from agent import AgentContext
from helpers.api import ApiHandler, Request, Response
from usr.plugins.realtime_voice.helpers import config
from usr.plugins.realtime_voice.helpers.session import get_api_key


class Status(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if not isinstance(input, dict):
            return Response(status=400, response="Expected a JSON object")
        ctxid = str(input.get("ctxid") or "").strip()
        context = AgentContext.get(ctxid) if ctxid else None
        agent = context.agent0 if context else None

        return {
            "plugin": config.PLUGIN_NAME,
            "enabled": config.is_enabled(agent),
            "api_key_configured": bool(get_api_key()),
            "config": config.get_config(agent),
        }
