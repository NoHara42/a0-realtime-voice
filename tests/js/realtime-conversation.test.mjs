// Run with: node --test tests/js
import { test } from "node:test";
import assert from "node:assert/strict";

import { RealtimeConversation } from "../../webui/realtime-conversation.js";

const ACK = "say on it";

function setup({ delegate } = {}) {
  const sent = [];
  const errors = [];
  let resolveDelegate;
  const delegations = [];
  const conv = new RealtimeConversation({
    send: (e) => sent.push(e),
    delegate:
      delegate ||
      ((call) => {
        delegations.push(call);
        return new Promise((resolve) => (resolveDelegate = resolve));
      }),
    toolName: "delegate_to_agent",
    ackInstructions: ACK,
    onError: (m) => errors.push(m),
  });
  return { conv, sent, errors, delegations, finish: (r) => resolveDelegate(r) };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

const callDone = (callId, task, extra = []) => ({
  type: "response.done",
  response: {
    status: "completed",
    output: [...extra, { type: "function_call", status: "completed", name: "delegate_to_agent", call_id: callId, arguments: JSON.stringify({ task }) }],
  },
});

test("delegate call triggers task, immediate ack, then result report", async () => {
  const { conv, sent, delegations, finish } = setup();

  conv.handleServerEvent({ type: "response.created" });
  conv.handleServerEvent(callDone("c1", "run date"));
  await tick();

  assert.deepEqual(delegations, [{ callId: "c1", task: "run date" }]);
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0], {
    type: "response.create",
    response: { conversation: "none", input: [], instructions: ACK, tool_choice: "none" },
  });
  assert.equal(conv.runningTasks.length, 1);

  // ack response plays out
  conv.handleServerEvent({ type: "response.created" });
  conv.handleServerEvent({ type: "response.done", response: { status: "completed", output: [{ type: "message" }] } });

  finish({ status: "completed", output: "It is Tuesday." });
  await tick();

  assert.deepEqual(sent[1], {
    type: "conversation.item.create",
    item: {
      type: "function_call_output",
      call_id: "c1",
      output: JSON.stringify({ status: "completed", result: "It is Tuesday." }),
    },
  });
  assert.deepEqual(sent[2], { type: "response.create" });
  assert.equal(conv.runningTasks.length, 0);
  assert.equal(conv.tasks.get("c1").status, "done");
});

test("no extra ack when the model already spoke in the same response", async () => {
  const { conv, sent } = setup();
  conv.handleServerEvent(callDone("c1", "x", [{ type: "message" }]));
  await tick();
  assert.equal(sent.length, 0);
});

test("result waits while a response is active and while the user talks", async () => {
  const { conv, sent, finish } = setup();
  conv.handleServerEvent(callDone("c1", "job"));
  await tick();
  sent.length = 0;

  conv.handleServerEvent({ type: "response.created" }); // ack is playing
  finish({ status: "completed", output: "done" });
  await tick();
  assert.equal(sent.length, 0, "nothing sent during active response");

  conv.handleServerEvent({ type: "input_audio_buffer.speech_started" });
  conv.handleServerEvent({ type: "response.done", response: { status: "cancelled", output: [] } });
  // output is added so the user's upcoming turn sees it, but no response is forced
  assert.equal(sent.length, 1);
  assert.equal(sent[0].type, "conversation.item.create");

  conv.handleServerEvent({ type: "input_audio_buffer.speech_stopped" });
  // user finished talking: announce the result
  assert.deepEqual(sent[1], { type: "response.create" });
});

test("a VAD response after the result was added replaces the announcement", async () => {
  const { conv, sent, finish } = setup();
  conv.handleServerEvent(callDone("c1", "job"));
  await tick();
  conv.handleServerEvent({ type: "input_audio_buffer.speech_started" });
  sent.length = 0;
  conv.handleServerEvent({ type: "response.done", response: { status: "cancelled", output: [] } });
  finish({ status: "completed", output: "done" });
  await tick();
  assert.equal(sent.length, 1); // item added, response deferred
  conv.handleServerEvent({ type: "response.created" }); // auto response from VAD
  conv.handleServerEvent({ type: "input_audio_buffer.speech_stopped" });
  conv.handleServerEvent({ type: "response.done", response: { status: "completed", output: [{ type: "message" }] } });
  assert.equal(sent.length, 1, "no duplicate announcement");
});

test("delegate failure is reported to the model as an error result", async () => {
  const { conv, sent } = setup({ delegate: () => Promise.reject(new Error("offline")) });
  conv.handleServerEvent(callDone("c1", "job"));
  await tick();
  await tick();
  conv.handleServerEvent({ type: "response.created" });
  conv.handleServerEvent({ type: "response.done", response: { status: "completed", output: [] } });
  const item = sent.find((e) => e.type === "conversation.item.create");
  assert.ok(item);
  assert.match(item.item.output, /Could not reach Agent Zero/);
  assert.equal(conv.tasks.get("c1").status, "error");
});

test("unknown tool and bad arguments get immediate error outputs", async () => {
  const { conv, sent, delegations } = setup();
  conv.handleServerEvent({
    type: "response.done",
    response: {
      status: "completed",
      output: [
        { type: "function_call", status: "completed", name: "other_tool", call_id: "u1", arguments: "{}" },
        { type: "function_call", status: "completed", name: "delegate_to_agent", call_id: "u2", arguments: "not json" },
      ],
    },
  });
  await tick();
  assert.equal(delegations.length, 0);
  const outputs = sent.filter((e) => e.type === "conversation.item.create").map((e) => e.item.call_id);
  assert.deepEqual(outputs, ["u1", "u2"]);
  assert.deepEqual(sent.at(-1), { type: "response.create" });
});

test("rejected response.create does not block the session", async () => {
  const { conv, sent, errors, finish } = setup();
  conv.handleServerEvent(callDone("c1", "job"));
  await tick();
  assert.equal(conv.responseActive, true); // waiting for the ack response
  conv.handleServerEvent({ type: "error", error: { code: "invalid_value", message: "bad" } });
  assert.equal(conv.responseActive, false);
  assert.deepEqual(errors, ["bad"]);
  finish({ status: "completed", output: "ok" });
  await tick();
  assert.deepEqual(sent.at(-1), { type: "response.create" });
});

test("race with an existing response is retried after it finishes", async () => {
  const { conv, sent, errors, finish } = setup();
  conv.handleServerEvent(callDone("c1", "job"));
  await tick();
  conv.handleServerEvent({ type: "error", error: { code: "conversation_already_has_active_response", message: "busy" } });
  assert.deepEqual(errors, []);
  assert.equal(conv.responseActive, true);
  conv.handleServerEvent({ type: "response.done", response: { status: "completed", output: [] } });
  finish({ status: "completed", output: "ok" });
  await tick();
  assert.equal(sent.at(-2).type, "conversation.item.create");
});

test("captions accumulate deltas per item and cap the list", () => {
  const { conv } = setup();
  conv.handleServerEvent({ type: "conversation.item.input_audio_transcription.delta", item_id: "i1", delta: "Hel" });
  conv.handleServerEvent({ type: "conversation.item.input_audio_transcription.delta", item_id: "i1", delta: "lo" });
  conv.handleServerEvent({ type: "response.output_audio_transcript.delta", item_id: "a1", delta: "Hi" });
  conv.handleServerEvent({ type: "conversation.item.input_audio_transcription.completed", item_id: "i1", transcript: "Hello." });
  assert.deepEqual(
    conv.captions.map((c) => [c.role, c.text, c.final]),
    [["user", "Hello.", true], ["assistant", "Hi", false]],
  );
  for (let i = 0; i < 60; i++) conv.caption(`x${i}`, "assistant", "t", { final: true });
  assert.equal(conv.captions.length, 40);
});

test("phase follows speaking state and interrupt cancels speech", () => {
  const { conv, sent } = setup();
  assert.equal(conv.phase, "listening");
  conv.handleServerEvent({ type: "response.created" });
  assert.equal(conv.phase, "thinking");
  conv.handleServerEvent({ type: "output_audio_buffer.started" });
  assert.equal(conv.phase, "speaking");
  conv.interrupt();
  assert.deepEqual(sent, [{ type: "response.cancel" }, { type: "output_audio_buffer.clear" }]);
  conv.handleServerEvent({ type: "input_audio_buffer.speech_started" });
  assert.equal(conv.phase, "user_speaking");
});

test("closed conversation ignores late results", async () => {
  const { conv, sent, finish } = setup();
  conv.handleServerEvent(callDone("c1", "job"));
  await tick();
  conv.handleServerEvent({ type: "response.done", response: { status: "completed", output: [] } });
  sent.length = 0;
  conv.close();
  finish({ status: "completed", output: "late" });
  await tick();
  assert.equal(sent.length, 0);
});

for (const status of ["cancelled", "failed", "incomplete"]) {
  test(`${status} responses cannot dispatch agent work`, async () => {
    const { conv, sent, delegations } = setup();
    const event = callDone("c1", "run a command");
    event.response.status = status;
    conv.handleServerEvent(event);
    await tick();
    assert.equal(delegations.length, 0);
    assert.equal(sent.length, 0);
  });
}

test("unfinished function items cannot dispatch agent work", async () => {
  const { conv, delegations } = setup();
  const event = callDone("c1", "run a command");
  event.response.output[0].status = "incomplete";
  conv.handleServerEvent(event);
  await tick();
  assert.equal(delegations.length, 0);
});

test("closing before queued dispatch prevents new agent work", async () => {
  const { conv, delegations } = setup();
  conv.handleServerEvent(callDone("c1", "run a command"));
  conv.close();
  await tick();
  assert.equal(delegations.length, 0);
});

test("delegate HTTP errors are not forwarded into the voice session", async () => {
  const { conv, sent } = setup({ delegate: () => Promise.reject(new Error("private backend traceback")) });
  conv.handleServerEvent(callDone("c1", "job"));
  await tick();
  conv.handleServerEvent({ type: "response.done", response: { status: "completed", output: [] } });
  const item = sent.find((e) => e.type === "conversation.item.create");
  assert.ok(item);
  assert.doesNotMatch(item.item.output, /private backend traceback/);
});
