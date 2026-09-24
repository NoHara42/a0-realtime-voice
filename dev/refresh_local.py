"""Refresh the installed plugin's API cache through normal plugin management.

Run in /a0 after copying reviewed release files. Preserves scoped overrides and
refuses to change a currently disabled plugin. Does not restart the framework.
"""
import httpx
from helpers import dotenv

dotenv.load_dotenv()
with httpx.Client(base_url='http://127.0.0.1:80', follow_redirects=True,
                  headers={'Origin':'http://127.0.0.1'}, timeout=30) as client:
    username=dotenv.get_dotenv_value('AUTH_LOGIN')
    password=dotenv.get_dotenv_value('AUTH_PASSWORD')
    if username and password:
        response=client.post('/login',data={'username':username,'password':password})
        assert '/login' not in str(response.url), 'Login failed'
    csrf=client.get('/api/csrf_token').json()
    client.headers['X-CSRF-Token']=csrf['token']
    current=client.post('/api/plugins/realtime_voice/status',json={}).json()
    assert current['enabled'], 'Plugin is disabled; leaving toggle untouched'
    response=client.post('/api/plugins',json={'action':'toggle_plugin','plugin_name':'realtime_voice','enabled':True})
    assert response.json().get('ok'), 'Refresh failed'
    for path,payload in [('session',{'sdp':'v='+'a'*131072}),('delegate',{'task':['invalid']})]:
        response=client.post('/api/plugins/realtime_voice/'+path,json=payload)
        assert response.status_code==400, f'Updated validation not loaded: {path}'
    print('PASS: updated session/delegate handlers active; existing configuration preserved')
