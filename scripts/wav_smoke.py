"""Live WAV -> Realtime -> normal Agent Zero delegation -> WAV smoke test.

Run from /a0 with the framework interpreter, as a module:
  /opt/venv-a0/bin/python -m usr.plugins.realtime_voice.scripts.wav_smoke input.wav --output /tmp/reply.wav
Input: mono PCM16 24 kHz WAV. Makes billable OpenAI calls and may execute the
spoken request through Agent Zero. Use only a trusted, harmless test recording.
"""
import argparse
import asyncio
import base64
import json
import wave
from pathlib import Path
from urllib.parse import urlencode

import websockets
from agent import AgentContext
from initialize import initialize_agent
from helpers import runtime
from usr.plugins.realtime_voice.helpers.config import get_config
from usr.plugins.realtime_voice.helpers.delegation import delegate
from usr.plugins.realtime_voice.helpers.session import (
    ACK_INSTRUCTIONS, WEBSOCKET_URL, build_instructions, build_session_config, get_api_key,
)


async def run(args):
    # Standalone processes do not receive the server's --dockerized argument.
    runtime.initialize()
    if Path('/.dockerenv').exists():
        runtime.args['dockerized'] = True
    with wave.open(args.wav, 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 24000):
            raise ValueError('Input must be mono PCM16 at 24000 Hz')
        pcm = source.readframes(source.getnframes())
    context = AgentContext(config=initialize_agent())
    cfg = get_config(context.agent0)
    session = build_session_config(cfg, build_instructions(cfg), transport='websocket')
    session['audio']['input']['turn_detection'] = None
    pending = set()
    audio = bytearray()
    active = False
    finished = False
    failed = False
    outputs = asyncio.Queue()
    async def work(call):
        try:
            task = json.loads(call['arguments'])['task']
            result = await delegate(context, task)
        except Exception as error:
            result = {'status': 'error', 'output': str(error)}
        await outputs.put((call['call_id'], result))
    try:
        async with websockets.connect(WEBSOCKET_URL + '?' + urlencode({'model': cfg['model']}),
                                      additional_headers={'Authorization': f'Bearer {get_api_key()}'}, max_size=8*1024*1024) as ws:
            async def send(event):
                await ws.send(json.dumps(event))
            await send({'type': 'session.update', 'session': session})
            # Wait for config acceptance before sending audio.
            while True:
                event = json.loads(await ws.recv())
                if event['type'] == 'error': raise RuntimeError(event['error']['message'])
                if event['type'] == 'session.updated': break
            for start in range(0, len(pcm), 24000):
                await send({'type':'input_audio_buffer.append', 'audio':base64.b64encode(pcm[start:start+24000]).decode()})
            await send({'type':'input_audio_buffer.commit'})
            await send({'type':'response.create'})
            active = True
            deadline = asyncio.get_running_loop().time() + args.timeout
            while asyncio.get_running_loop().time() < deadline:
                if not active and not outputs.empty():
                    while not outputs.empty():
                        call_id, result = await outputs.get()
                        print('Agent result:', result['status'], result['output'])
                        failed = failed or result['status'] == 'error'
                        await send({'type':'conversation.item.create', 'item':{'type':'function_call_output','call_id':call_id,'output':json.dumps(result)}})
                    await send({'type':'response.create'})
                    active = True
                    finished = True
                try:
                    event = json.loads(await asyncio.wait_for(ws.recv(), timeout=.25))
                except asyncio.TimeoutError:
                    continue
                kind = event['type']
                if kind == 'error': raise RuntimeError(event['error']['message'])
                if kind == 'response.output_audio.delta': audio.extend(base64.b64decode(event['delta']))
                if kind == 'response.output_audio_transcript.done': print('Voice:', event['transcript'])
                if kind == 'response.created': active = True
                if kind == 'response.done':
                    active = False
                    response = event['response']
                    if response.get('status') == 'failed': raise RuntimeError(str(response.get('status_details')))
                    calls = [i for i in response.get('output',[]) if i.get('type') == 'function_call']
                    for call in calls:
                        job = asyncio.create_task(work(call)); pending.add(job); job.add_done_callback(pending.discard)
                    if calls:
                        await send({'type':'response.create','response':{'conversation':'none','input':[], 'instructions':ACK_INSTRUCTIONS,'tool_choice':'none'}})
                        active = True
                    elif finished or (not pending and outputs.empty()):
                        break
            else: raise TimeoutError('Live smoke test timed out')
        if not audio: raise RuntimeError('No response audio received')
        with wave.open(args.output,'wb') as dest:
            dest.setnchannels(1); dest.setsampwidth(2); dest.setframerate(24000); dest.writeframes(audio)
        print('Saved response audio:', args.output)
        if failed: raise RuntimeError('Agent delegation failed; see result above')
    finally:
        for job in pending: job.cancel()
        AgentContext.remove(context.id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav')
    parser.add_argument('--output', default='/tmp/realtime-reply.wav')
    parser.add_argument('--timeout', type=int, default=180)
    asyncio.run(run(parser.parse_args()))
