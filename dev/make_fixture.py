"""Run in the disposable framework container. Creates a synthetic mic fixture."""
import io
import wave
from pathlib import Path
import httpx
from usr.plugins.realtime_voice.helpers.session import get_api_key

out = Path('/a0/usr/plugins/realtime_voice/dev/out')
out.mkdir(exist_ok=True)
response = httpx.post('https://api.openai.com/v1/audio/speech', headers={
    'Authorization': f'Bearer {get_api_key()}'
}, json={'model': 'tts-1', 'voice': 'alloy', 'response_format': 'wav',
         'input': 'Please use the terminal to calculate seventeen times twenty three. Tell me the answer.'}, timeout=60)
response.raise_for_status()
with wave.open(io.BytesIO(response.content), 'rb') as source:
    params = source.getparams()
    speech = source.readframes(source.getnframes())
    params = params._replace(nframes=len(speech) // (params.nchannels * params.sampwidth))
with wave.open(str(out / 'request.wav'), 'wb') as dest:
    dest.setparams(params)
    dest.writeframes(speech)
with wave.open(str(out / 'microphone.wav'), 'wb') as dest:
    dest.setparams(params)
    silence = bytes(params.framerate * params.nchannels * params.sampwidth)
    dest.writeframes(silence * 12 + speech + silence * 120)
print('Synthetic speech fixtures created.')
