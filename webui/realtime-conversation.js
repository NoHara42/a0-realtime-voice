/**
 * Transport-independent turn logic for a Realtime voice session.
 *
 * Feeds on Realtime server events and emits client events through `send`.
 * It owns the delegation flow:
 *   1. the model calls the delegate tool  -> start the Agent Zero task (async)
 *   2. right after that response finishes -> ask for a short spoken acknowledgement
 *   3. while the task runs                -> the conversation continues normally
 *   4. when the agent answers             -> add function_call_output and ask the
 *                                            model to report it, but only once no
 *                                            response is active and the user is
 *                                            not talking
 * No DOM or WebRTC here, so it can be unit tested with plain event objects.
 */

const MAX_CAPTIONS = 40;

export class RealtimeConversation {
  /**
   * @param {object} options
   * @param {(event: object) => void} options.send - send a client event to the Realtime session
   * @param {(call: {callId: string, task: string}) => Promise<{status: string, output: string}>} options.delegate
   * @param {string} [options.toolName]
   * @param {string} [options.ackInstructions]
   * @param {() => void} [options.onChange] - called after any state change
   * @param {(message: string) => void} [options.onError]
   */
  constructor({ send, delegate, toolName = "delegate_to_agent", ackInstructions = "", onChange, onError }) {
    this.send = send;
    this.delegate = delegate;
    this.toolName = toolName;
    this.ackInstructions = ackInstructions;
    this.onChange = onChange || (() => {});
    this.onError = onError || (() => {});

    this.responseActive = false;
    this.userSpeaking = false;
    this.assistantSpeaking = false;
    this.ackNeeded = false;
    this.announceNeeded = false;
    this.pendingOutputs = [];
    this.awaitingCreated = false;
    this.closed = false;

    /** @type {Map<string, {callId: string, task: string, status: string, output: string, startedAt: number, finishedAt: number}>} */
    this.tasks = new Map();
    /** @type {{key: string, role: string, text: string, final: boolean}[]} */
    this.captions = [];
  }

  get phase() {
    if (this.userSpeaking) return "user_speaking";
    if (this.assistantSpeaking) return "speaking";
    if (this.responseActive) return "thinking";
    return "listening";
  }

  get runningTasks() {
    return [...this.tasks.values()].filter((t) => t.status === "running");
  }

  close() {
    this.closed = true;
  }

  handleServerEvent(event) {
    if (!event || typeof event.type !== "string" || this.closed) return;

    switch (event.type) {
      case "input_audio_buffer.speech_started":
        this.userSpeaking = true;
        break;

      case "input_audio_buffer.speech_stopped":
        this.userSpeaking = false;
        this.flush();
        break;

      case "response.created":
        this.responseActive = true;
        this.awaitingCreated = false;
        // Any new response already sees results added to the conversation.
        this.announceNeeded = false;
        break;

      case "response.done":
        this.responseActive = false;
        this.handleResponseDone(event.response || {});
        this.flush();
        break;

      case "output_audio_buffer.started":
        this.assistantSpeaking = true;
        break;

      case "output_audio_buffer.stopped":
      case "output_audio_buffer.cleared":
        this.assistantSpeaking = false;
        this.flush();
        break;

      case "conversation.item.input_audio_transcription.delta":
        this.caption(event.item_id, "user", event.delta || "", { append: true });
        break;

      case "conversation.item.input_audio_transcription.completed":
        this.caption(event.item_id, "user", event.transcript || "", { final: true });
        break;

      case "response.output_audio_transcript.delta":
        this.caption(event.item_id, "assistant", event.delta || "", { append: true });
        break;

      case "response.output_audio_transcript.done":
        this.caption(event.item_id, "assistant", event.transcript || "", { final: true });
        break;

      case "error":
        this.handleError(event.error || {});
        break;

      default:
        return;
    }
    this.onChange();
  }

  handleResponseDone(response) {
    const output = Array.isArray(response.output) ? response.output : [];
    const calls = output.filter((item) => item && item.type === "function_call");
    const spoke = output.some((item) => item && item.type === "message");

    if (response.status === "failed") {
      const message = response.status_details?.error?.message || "The voice model failed to respond.";
      this.onError(message);
    }

    this.batchingCalls = true;
    for (const call of calls) this.startCall(call);
    this.batchingCalls = false;

    // Acknowledge a hand-off unless the model already said something itself.
    if (calls.some((call) => call.name === this.toolName) && !spoke) {
      this.ackNeeded = true;
    }
  }

  handleError(error) {
    if (error.code === "conversation_already_has_active_response") {
      // Our response.create raced a VAD response; it runs anyway and sees the
      // added results, and anything still queued is flushed after it finishes.
      this.awaitingCreated = false;
      this.responseActive = true;
      return;
    }
    if (error.code === "response_cancel_not_active") return;
    if (this.awaitingCreated) {
      // Our response.create was rejected; don't stay blocked waiting for it.
      this.awaitingCreated = false;
      this.responseActive = false;
    }
    this.onError(error.message || "Realtime session error");
  }

  startCall(call) {
    const callId = call.call_id;
    if (!callId || this.tasks.has(callId)) return;

    if (call.name !== this.toolName) {
      this.queueOutput(callId, { status: "error", output: `Unknown tool: ${call.name}` });
      return;
    }

    let task = "";
    try {
      task = String(JSON.parse(call.arguments || "{}").task || "").trim();
    } catch (_error) {
      task = "";
    }
    if (!task) {
      this.queueOutput(callId, { status: "error", output: "No task text was given." });
      return;
    }

    const entry = { callId, task, status: "running", output: "", startedAt: Date.now(), finishedAt: 0 };
    this.tasks.set(callId, entry);
    this.caption(`task-${callId}`, "agent", task, { final: true });

    Promise.resolve()
      .then(() => this.delegate({ callId, task }))
      .catch((error) => ({
        status: "error",
        output: `Could not reach Agent Zero: ${error?.message || error}`,
      }))
      .then((result) => {
        entry.status = result?.status === "completed" ? "done" : result?.status || "error";
        entry.output = String(result?.output || "");
        entry.finishedAt = Date.now();
        this.queueOutput(callId, result);
        this.onChange();
      });
  }

  queueOutput(callId, result) {
    if (this.closed) return;
    this.pendingOutputs.push({
      callId,
      output: JSON.stringify({ status: result?.status || "error", result: String(result?.output || "") }),
    });
    this.flush();
  }

  /** Send whatever is waiting, respecting active responses and the user's turn. */
  flush() {
    if (this.closed || this.responseActive || this.batchingCalls) return;

    if (this.pendingOutputs.length) {
      for (const pending of this.pendingOutputs) {
        this.send({
          type: "conversation.item.create",
          item: { type: "function_call_output", call_id: pending.callId, output: pending.output },
        });
      }
      this.pendingOutputs = [];
      this.ackNeeded = false; // the result itself is better than "on it"
      this.announceNeeded = true;
    }

    if (this.userSpeaking || this.assistantSpeaking) return;

    if (this.announceNeeded) {
      this.announceNeeded = false;
      this.requestResponse({ type: "response.create" });
    } else if (this.ackNeeded) {
      this.ackNeeded = false;
      this.requestResponse({
        type: "response.create",
        // Isolate the acknowledgement from the task: otherwise the model can
        // answer an easy task from memory while its real tool is still pending.
        response: { conversation: "none", input: [], instructions: this.ackInstructions, tool_choice: "none" },
      });
    }
  }

  requestResponse(event) {
    this.responseActive = true; // optimistic, until response.created / error arrives
    this.awaitingCreated = true;
    this.send(event);
  }

  /** Stop the model mid-sentence (manual barge-in). */
  interrupt() {
    if (this.responseActive) this.send({ type: "response.cancel" });
    if (this.assistantSpeaking) this.send({ type: "output_audio_buffer.clear" });
  }

  caption(itemId, role, text, { append = false, final = false } = {}) {
    const key = String(itemId || `${role}-${this.captions.length}`);
    let entry = this.captions.find((c) => c.key === key);
    if (!entry) {
      if (!text) return;
      entry = { key, role, text: "", final: false };
      this.captions.push(entry);
      if (this.captions.length > MAX_CAPTIONS) this.captions.splice(0, this.captions.length - MAX_CAPTIONS);
    }
    entry.text = append ? entry.text + text : text || entry.text;
    entry.final = final || entry.final;
  }
}
