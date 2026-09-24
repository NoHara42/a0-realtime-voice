import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { sttService } from "/js/stt-service.js";
import { ttsService } from "/js/tts-service.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";
import { RealtimeConversation } from "./realtime-conversation.js";

// Native media objects stay outside Alpine's reactive proxies.
let runtime = null;
const endpoint = (name) => `/plugins/realtime_voice/${name}`;
const fail = (error) => toastFrontendError(error?.message || String(error), "Realtime Voice");

export const store = createStore("realtimeVoice", {
  active: false,
  connected: false,
  muted: false,
  phase: "idle",
  captions: [],
  tasks: [],
  model: "",
  async openConfig() {
    const { store: settings } = await import("/components/plugins/plugin-settings-store.js");
    await settings.openConfig("realtime_voice");
  },
  toggle() { if (this.active) this.stop(); else void this.start(); },
  async start() {
    if (runtime) return;
    const rt = { pc: null, stream: null, audio: null, dc: null, conversation: null };
    runtime = rt;
    this.active = true;
    this.phase = "connecting";
    this.captions = [];
    this.tasks = [];
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        throw new Error("Microphone access needs HTTPS or localhost. Open Agent Zero using one of those addresses.");
      }
      sttService.stop();
      ttsService.stop();
      rt.quietTts = () => { if (ttsService.isSpeaking()) ttsService.stop(); };
      rt.quietStt = () => { if (sttService.getStatus() !== "inactive") sttService.stop(); };
      ttsService.addEventListener("statechange", rt.quietTts);
      sttService.addEventListener("statuschange", rt.quietStt);
      rt.ctxid = globalThis.getContext?.();
      // Use the framework's chat creation path, including project/profile setup.
      const chat = await callJsonApi("/chat_create", rt.ctxid ? { new_context: rt.ctxid } : {});
      if (runtime !== rt) return;
      rt.ctxid = chat.ctxid;
      globalThis.setContext?.(rt.ctxid);
      rt.watch = setInterval(() => {
        if (globalThis.getContext?.() !== rt.ctxid) this.stop();
      }, 250);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (runtime !== rt) { stream.getTracks().forEach((t) => t.stop()); return; }
      rt.stream = stream;
      rt.audio = new Audio();
      rt.audio.autoplay = true;
      rt.pc = new RTCPeerConnection();
      for (const track of stream.getTracks()) {
        rt.pc.addTrack(track, stream);
        track.addEventListener("ended", () => { if (runtime === rt) this.stop(); });
      }
      rt.pc.ontrack = ({ streams, track }) => {
        rt.audio.srcObject = streams[0] || new MediaStream([track]);
        rt.audio.play().catch(() => fail(new Error("Audio playback was blocked. End the call and start it again using the voice button.")));
      };
      rt.pc.onconnectionstatechange = () => {
        if (["failed", "closed"].includes(rt.pc.connectionState) && runtime === rt) {
          this.stop();
          fail(new Error("Voice connection ended. Start a new call to reconnect."));
        }
      };
      rt.dc = rt.pc.createDataChannel("oai-events");
      rt.dc.onclose = () => { if (runtime === rt) this.stop(); };
      rt.dc.onmessage = ({ data }) => {
        if (runtime !== rt) return;
        try { rt.conversation?.handleServerEvent(JSON.parse(data)); } catch (error) { fail(error); }
      };
      rt.dc.onopen = () => {
        if (runtime !== rt) return;
        clearTimeout(rt.timeout);
        this.connected = true;
        this.phase = "listening";
      };
      rt.timeout = setTimeout(() => {
        if (runtime === rt) { this.stop(); fail(new Error("Voice connection timed out. Check your network and OpenAI settings.")); }
      }, 45000);
      const offer = await rt.pc.createOffer();
      await rt.pc.setLocalDescription(offer);
      const session = await callJsonApi(endpoint("session"), { ctxid: rt.ctxid, sdp: offer.sdp });
      if (runtime !== rt) return;
      this.model = session.model;
      rt.conversation = new RealtimeConversation({
        toolName: session.tool_name,
        ackInstructions: session.ack_instructions,
        send: (event) => { if (rt.dc.readyState === "open") rt.dc.send(JSON.stringify(event)); },
        delegate: ({ callId, task }) => callJsonApi(endpoint("delegate"), { ctxid: rt.ctxid, call_id: callId, task }),
        onError: fail,
        onChange: () => {
          if (runtime !== rt) return;
          this.phase = rt.conversation.phase;
          this.captions = rt.conversation.captions.map((c) => ({ ...c }));
          this.tasks = rt.conversation.runningTasks.map((t) => ({ ...t }));
        },
      });
      await rt.pc.setRemoteDescription({ type: "answer", sdp: session.sdp });
    } catch (error) {
      if (runtime === rt) { this.stop(); fail(error); }
    }
  },
  stop() {
    const rt = runtime;
    runtime = null;
    if (rt) {
      rt.conversation?.close();
      clearTimeout(rt.timeout);
      clearInterval(rt.watch);
      ttsService.removeEventListener("statechange", rt.quietTts);
      sttService.removeEventListener("statuschange", rt.quietStt);
      rt.dc?.close();
      rt.pc?.close();
      rt.stream?.getTracks().forEach((track) => track.stop());
      if (rt.audio) { rt.audio.pause(); rt.audio.srcObject = null; }
    }
    this.active = false;
    this.connected = false;
    this.muted = false;
    this.phase = "idle";
    this.tasks = [];
  },
  mute() {
    this.muted = !this.muted;
    runtime?.stream?.getAudioTracks().forEach((track) => { track.enabled = !this.muted; });
  },
  interrupt() { runtime?.conversation?.interrupt(); },
});

window.addEventListener("pagehide", () => store.stop());
