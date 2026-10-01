import urllib.request
import urllib.error
import json
import time

key = 'sk_live_6acv8fHhGrQTPQfVePKOYn_Yy1Wx8I3pRE75a4AwhF0'
headers = {
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json'
}

print("1. Testing POST /api/v1/session/start...")
t0 = time.time()
req = urllib.request.Request('http://localhost:8085/api/v1/session/start', data=b'{}', headers=headers, method='POST')
res = urllib.request.urlopen(req)
start_data = json.loads(res.read())
print(f"   Start took {round(time.time() - t0, 2)}s, status: {res.status}")
session_id = start_data['session_id']
print(f"   Got session_id: {session_id}, captcha len: {len(start_data.get('captcha_b64', ''))}")

print("2. Testing POST /api/v1/session/login with test credentials...")
t1 = time.time()
login_payload = json.dumps({
    'session_id': session_id,
    'username': 'P99999',
    'password': 'badpassword123',
    'captcha': '12345'
}).encode()

req2 = urllib.request.Request('http://localhost:8085/api/v1/session/login', data=login_payload, headers=headers, method='POST')
try:
    res2 = urllib.request.urlopen(req2)
    print("   Login succeeded:", res2.status)
except urllib.error.HTTPError as e:
    resp_body = e.read().decode()
    print(f"   Login took {round(time.time() - t1, 2)}s, status: {e.code}")
    print(f"   Body: {resp_body}")

urllib.request.urlopen(urllib.request.Request('http://localhost:8085/api/v1/session/close', data=json.dumps({'session_id': session_id}).encode(), headers=headers, method='POST'))
print("3. Closed session cleanly.")
