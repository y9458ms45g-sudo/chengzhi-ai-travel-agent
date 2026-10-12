import requests, json, sys

url = 'http://127.0.0.1:8000/api/trip/stream'
text = sys.argv[1] if len(sys.argv) > 1 else '3天2晚成都带老人中等预算怎么安排'
sid = sys.argv[2] if len(sys.argv) > 2 else 'eval_plan_test'
body = {'user_input': text, 'session_id': sid, 'current_ip': 'sichuan'}
r = requests.post(url, json=body, stream=True, timeout=180)
types = {}
plan_evt = None
sys_evts = []
tokens = []
for raw in r.iter_lines(decode_unicode=True):
    if not raw or not raw.startswith('data: '):
        continue
    ev = json.loads(raw[6:])
    t = ev.get('type')
    types[t] = types.get(t, 0) + 1
    if t == 'plan':
        plan_evt = ev
    if t == 'sys':
        sys_evts.append(ev.get('text', ''))
    if t == 'token':
        tokens.append(ev.get('text', ''))

print('EVENT COUNTS:', types)
print('PLAN:', json.dumps(plan_evt, ensure_ascii=False)[:600] if plan_evt else None)
print('SYS:', sys_evts)
full = ''.join(tokens)
print('---ANSWER HEAD---')
print(full[:700])
print('---ANSWER TAIL---')
print(full[-300:])
print('LEN:', len(full))
