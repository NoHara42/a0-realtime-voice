import httpx
from agent import AgentContext
from helpers.api import ApiHandler, Request, Response
from helpers.print_style import PrintStyle
from usr.plugins.realtime_voice.helpers import config
from usr.plugins.realtime_voice.helpers.session import (
    ACK_INSTRUCTIONS,
    DELEGATE_TOOL_NAME,
    RealtimeApiError,
    build_instructions,
    build_session_config,
    chat_history_lines,
    create_webrtc_call,
    get_api_key,
)


class Session(ApiHandler):
    """Create a Realtime WebRTC call: forwards the browser's SDP offer to OpenAI."""

    async def process(self, input: dict, request: Request) -> dict | Response:
        if not isinstance(input, dict):
            return Response(status=400, response="Expected a JSON object")
        offer_sdp = input.get("sdp", "")
        if not isinstance(offer_sdp, str) or len(offer_sdp) > 131072:
            return Response(status=400, response="SDP must be a string of at most 128 KiB")
        if not offer_sdp.strip().startswith("v="):
            return Response(status=400, response="Missing or invalid SDP offer")

        ctxid = str(input.get("ctxid") or "").strip()
        context = AgentContext.get(ctxid) if ctxid else None
        if ctxid and context is None:
            return Response(status=404, response="Chat no longer exists. Start a new voice call.")
        agent = context.agent0 if context else None

        if not config.is_enabled(agent):
            return Response(status=409, response="Realtime Voice plugin is disabled")

        api_key = get_api_key()
        if not api_key:
            return Response(
                status=400,
                response="No OpenAI API key. Add it in Settings > API Keys > OpenAI.",
            )

        cfg = config.get_config(agent)
        history = chat_history_lines(context, int(cfg["history_messages"]))
        session = build_session_config(cfg, build_instructions(cfg, history))

        try:
            answer_sdp, call_id = await create_webrtc_call(offer_sdp, session, api_key)
        except RealtimeApiError as e:
            # Provider errors can echo credentials or request data. Never relay
            # their raw text into browser notifications or application logs.
            messages = {
                400: "OpenAI rejected the session settings. Check the model, voice and caption model.",
                401: "OpenAI rejected the API key. Check Settings > API Keys > OpenAI.",
                403: "OpenAI denied access. Check your project's model permissions.",
                404: "The requested OpenAI Realtime model is unavailable.",
                429: "OpenAI usage or rate limit reached. Check billing and try again later.",
            }
            message = messages.get(e.status, "OpenAI Realtime is unavailable. Try again later.")
            PrintStyle.error(f"Realtime Voice: OpenAI rejected the call (HTTP {e.status})")
            # Always 502 so OpenAI auth errors are not mistaken for Agent Zero auth errors.
            return Response(status=502, response=message)
        except httpx.RequestError:
            return Response(status=502, response="Could not connect to OpenAI Realtime. Check network access and try again.")

        return {
            "sdp": answer_sdp,
            "call_id": call_id,
            "model": session["model"],
            "voice": cfg["voice"],
            "tool_name": DELEGATE_TOOL_NAME,
            "ack_instructions": ACK_INSTRUCTIONS,
            "captions": bool(cfg["transcription_model"]),
        }
