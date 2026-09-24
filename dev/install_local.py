"""Run inside the target container via runpy, with /a0 as cwd.

Uses normal authenticated HTTP/CSRF and ZIP installer APIs. Never logs secrets.
Requires /tmp/realtime_voice.zip; refuses to overwrite an installed plugin.
"""
from pathlib import Path
import httpx
from helpers import dotenv

assert not Path('/a0/usr/plugins/realtime_voice').exists(), 'Plugin already exists; refusing overwrite'
dotenv.load_dotenv()
with httpx.Client(base_url='http://127.0.0.1:80', follow_redirects=True,
                  headers={'Origin':'http://127.0.0.1'}, timeout=120) as client:
    username = dotenv.get_dotenv_value('AUTH_LOGIN')
    password = dotenv.get_dotenv_value('AUTH_PASSWORD')
    if username and password:
        login = client.post('/login', data={'username':username, 'password':password})
        login.raise_for_status()
        assert '/login' not in str(login.url), 'Authentication failed'
    csrf = client.get('/api/csrf_token').json()
    assert csrf.get('ok'), 'CSRF setup failed'
    client.headers['X-CSRF-Token'] = csrf['token']
    with open('/tmp/realtime_voice.zip','rb') as archive:
        response = client.post('/api/plugins/_plugin_installer/plugin_install',
                               data={'action':'install_zip'},
                               files={'plugin_file':('realtime_voice.zip',archive,'application/zip')})
    response.raise_for_status()
    result = response.json()
    assert result.get('success'), result
    print('Installed:', result['plugin_name'])
    toggle = client.post('/api/plugins', json={'action':'toggle_plugin','plugin_name':'realtime_voice','enabled':True})
    toggle.raise_for_status()
    assert toggle.json().get('ok'), 'Enable failed'
    response = client.post('/api/plugins/realtime_voice/status', json={})
    response.raise_for_status()
    status = response.json()
    print('Enabled:',status['enabled'], 'OpenAI key configured:',status['api_key_configured'])
    print('Model:',status['config']['model'])
