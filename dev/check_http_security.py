"""Run inside the authenticated local instance with /a0 as cwd. No writes or live API calls."""
import httpx
from helpers import dotenv

dotenv.load_dotenv()
base = 'http://127.0.0.1:80'
paths = ['session','delegate','status']
with httpx.Client(base_url=base, follow_redirects=False, timeout=15) as anonymous:
    for path in paths:
        response=anonymous.post('/api/plugins/realtime_voice/'+path,json={})
        assert response.status_code==302 and '/login' in response.headers.get('location',''), path
print('PASS: all three endpoints reject unauthenticated requests')
with httpx.Client(base_url=base, follow_redirects=False, timeout=15,
                  headers={'Origin':base}) as client:
    response=client.post('/login', data={
        'username':dotenv.get_dotenv_value('AUTH_LOGIN'),
        'password':dotenv.get_dotenv_value('AUTH_PASSWORD'),
    })
    assert response.status_code==302, 'Login failed'
    for path in paths:
        response=client.post('/api/plugins/realtime_voice/'+path,json={})
        assert response.status_code==403, path
    token=client.get('/api/csrf_token').json()['token']
    client.headers['X-CSRF-Token']=token
    response=client.post('/api/plugins/realtime_voice/status',json={})
    assert response.status_code==200
    payload=response.json()
    assert 'api_key' not in payload and isinstance(payload['api_key_configured'],bool)
print('PASS: CSRF enforced on all endpoints; authenticated status exposes no credential field')
