// PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node dev/browser-live.mjs
// Uses synthetic speech only; requires a configured dev server on localhost:50090.
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { readFile } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, args: [
  '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
  `--use-file-for-fake-audio-capture=${resolve('dev/out/microphone.wav')}%noloop`,
  '--autoplay-policy=no-user-gesture-required',
] });
const page = await browser.newPage();
const errors = [];
const delegateResults = [];
page.on('response', async response => {
  if (response.url().endsWith('/realtime_voice/delegate')) {
    delegateResults.push(await response.json());
  }
});
page.on('pageerror', e => errors.push(e.message));
await page.addInitScript(() => {
  window.testPeers = [];
    window.testEvents = [];
    window.testSent = [];
  const Peer = window.RTCPeerConnection;
  window.RTCPeerConnection = class extends Peer {
    constructor(...args) { super(...args); window.testPeers.push(this); }
    createDataChannel(...args) {
      const channel = super.createDataChannel(...args);
      channel.addEventListener('message', e => window.testEvents.push(JSON.parse(e.data)));
      window.testChannel = channel;
      const send = channel.send.bind(channel);
      channel.send = (data) => { window.testSent.push(JSON.parse(data)); send(data); };
      return channel;
    }
  };
});
try {
  await page.goto(process.env.A0_URL || 'http://localhost:50090');
  await page.locator('#realtime-voice-button').waitFor({ timeout: 30000 });
  await page.locator('#realtime-voice-button').click();
  await page.waitForFunction(() => Alpine.store('realtimeVoice').connected, null, { timeout: 60000 });
  console.log('PASS: actual UI established WebRTC session');
  await page.waitForFunction(() => window.testEvents.some(e => e.type === 'response.done' && e.response?.output?.some(i => i.type === 'function_call')), null, { timeout: 60000 });
  console.log('PASS: synthetic microphone audio caused a tool call');
  const deadline = Date.now() + 180000;
  while (!delegateResults.length && Date.now() < deadline) await new Promise(r => setTimeout(r, 500));
  assert.equal(delegateResults[0]?.status, 'completed', JSON.stringify(delegateResults));
  assert.match(delegateResults[0].output, /391/);
  await page.waitForFunction(() => window.testSent.some(e => e.type === 'conversation.item.create' && e.item.type === 'function_call_output') && window.testEvents.filter(e => e.type === 'response.done').length >= 3, null, {timeout: 60000});
  await page.waitForFunction(() => Alpine.store('realtimeVoice').captions.some(c => c.role === 'assistant' && /391|three hundred (and )?ninety.one/i.test(c.text)), null, { timeout: 180000 });
  const report = await page.evaluate(async () => {
    const stats = [...(await window.testPeers[0].getStats()).values()];
    return {
      captions: Alpine.store('realtimeVoice').captions,
      inboundBytes: stats.filter(s => s.type === 'inbound-rtp' && s.kind === 'audio').reduce((n,s)=>n+(s.bytesReceived||0),0),
      errors: window.testEvents.filter(e => e.type === 'error'),
      ctxid: getContext(),
      responses: window.testEvents.filter(e => e.type === 'response.done').map(e => e.response.output),
    };
  });
  assert.ok(report.inboundBytes > 0, 'received actual speech audio');
  assert.equal(report.errors.length, 0, JSON.stringify(report.errors));
  const acknowledgement = report.responses[1].flatMap(item => item.content || []).map(c => c.transcript || '').join('');
  assert.ok(acknowledgement.length > 0, 'spoken acknowledgement present');
  assert.doesNotMatch(acknowledgement, /391|three hundred|ninety/i, 'acknowledgement must not guess the result');
  // Exercise real playback cancellation, then actual incoming RTP speech/VAD.
  await page.evaluate(() => {
    window.testEvents = [];
    testChannel.send(JSON.stringify({type:'conversation.item.create',item:{type:'message',role:'user',content:[{type:'input_text',text:'Tell me a long imaginary story about a friendly dragon. Speak for at least a minute.'}]}}));
    testChannel.send(JSON.stringify({type:'response.create'}));
  });
  await page.waitForFunction(() => testEvents.some(e=>e.type==='output_audio_buffer.started'), null, {timeout:30000});
  await page.getByRole('button', {name:'Interrupt',exact:true}).click();
  await page.waitForFunction(() => testEvents.some(e=>e.type==='output_audio_buffer.cleared'), null, {timeout:10000});
  await page.evaluate(() => {
    window.testEvents = [];
    testChannel.send(JSON.stringify({type:'response.create',response:{instructions:'Tell a long imaginary story about a friendly dragon. Speak for at least a minute.',tool_choice:'none'}}));
  });
  await page.waitForFunction(() => testEvents.some(e=>e.type==='output_audio_buffer.started'), null, {timeout:30000});
  const wav = (await readFile('dev/out/request.wav')).toString('base64');
  await page.evaluate(async base64 => {
    const ctx = new AudioContext();
    window.testAudioContext = ctx;
    const source = ctx.createBufferSource();
    source.buffer = await ctx.decodeAudioData(Uint8Array.from(atob(base64),c=>c.charCodeAt(0)).buffer);
    const dest = ctx.createMediaStreamDestination();
    source.connect(dest);
    await testPeers[0].getSenders()[0].replaceTrack(dest.stream.getAudioTracks()[0]);
    await ctx.resume();
    source.start();
  }, wav);
  await page.waitForFunction(() => testEvents.some(e=>e.type==='input_audio_buffer.speech_started') && testEvents.some(e=>e.type==='output_audio_buffer.cleared'), null, {timeout:15000});
  console.log('PASS: manual interrupt and real incoming audio barge-in cleared playback');
  // Restore the original microphone track for mute verification.
  await page.evaluate(async () => {
    await testAudioContext.close();
    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    window.extraTestStream = stream;
    await testPeers[0].getSenders()[0].replaceTrack(stream.getAudioTracks()[0]);
  });
  await page.getByRole('button', {name: 'Mute', exact: true}).click();
  assert.equal(await page.evaluate(() => Alpine.store('realtimeVoice').muted), true);
  await page.getByRole('button', {name: 'Unmute', exact: true}).click();
  await page.getByRole('button', {name: 'End call', exact: true}).click();
  await page.evaluate(() => extraTestStream.getTracks().forEach(t=>t.stop()));
  assert.equal(await page.evaluate(() => window.testPeers[0].connectionState), 'closed');
  assert.equal(await page.evaluate(() => Alpine.store('realtimeVoice').active), false);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({...report, delegateResults}, null, 2));
  console.log('PASS: delegation, spoken result, mute, and cleanup');
} catch (error) {
  console.log(await page.evaluate(() => ({phase: window.Alpine?.store('realtimeVoice')?.phase, events: window.testEvents?.slice(-12), text: document.body.innerText.slice(-3000)})));
  throw error;
} finally { await browser.close(); }
