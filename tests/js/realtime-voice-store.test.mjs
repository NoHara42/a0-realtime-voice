import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { RealtimeConversation } from "../../webui/realtime-conversation.js";

// Run the production store with browser/framework imports supplied by the host.
// No microphone, live Agent Zero server, or OpenAI calls are needed.
const source = readFileSync(new URL("../../webui/realtime-voice-store.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "")
  .replace("export const store =", "globalThis.store =");

function setup(callJsonApi) {
  let context = "original-chat";
  let microphoneRequests = 0;
  const notifications = [];
  const service = { stop() {}, addEventListener() {}, removeEventListener() {} };
  const sandbox = {
    createStore: (_name, model) => model,
    callJsonApi,
    RealtimeConversation,
    sttService: service, ttsService: service,
    toastFrontendError: (...args) => notifications.push(args),
    window: { isSecureContext: true, addEventListener() {} },
    navigator: { mediaDevices: { getUserMedia() { microphoneRequests++; throw new Error("unexpected microphone request"); } } },
    getContext: () => context,
    setContext: (id) => { context = id; },
    clearInterval, clearTimeout,
  };
  vm.runInNewContext(source, sandbox, { filename: "realtime-voice-store.js" });
  return {
    store: sandbox.store, notifications,
    switchChat: (id) => { context = id; },
    getContext: () => context,
    microphoneRequests: () => microphoneRequests,
  };
}

test("provider/API error markup is escaped before the HTML notification sink", async () => {
  const { store, notifications } = setup(async () => {
    throw new Error('<img src=x onerror="alert(1)"> & \'quoted\'');
  });
  await store.start();
  assert.deepEqual(notifications, [["&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;quoted&#39;", "Realtime Voice"]]);
  assert.equal(store.active, false);
});

test("switching chats during creation aborts startup without switching back", async () => {
  let resolve;
  const h = setup(() => new Promise((r) => { resolve = r; }));
  const started = h.store.start();
  h.switchChat("another-chat");
  resolve({ ctxid: "original-chat" });
  await started;
  assert.equal(h.getContext(), "another-chat");
  assert.equal(h.microphoneRequests(), 0);
  assert.equal(h.store.active, false);
});

test("ending a call during chat creation prevents microphone acquisition", async () => {
  let resolve;
  const h = setup(() => new Promise((r) => { resolve = r; }));
  const started = h.store.start();
  h.store.stop();
  resolve({ ctxid: "original-chat" });
  await started;
  assert.equal(h.microphoneRequests(), 0);
  assert.equal(h.store.active, false);
});
