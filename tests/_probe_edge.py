import requests, json, sys
url = 'http://127.0.0.1:8000/api/trip/stream'
def ask(text, sid):
    r = requests.post(url, json={'user_input': text, 'session_id': sid, 'current_ip': 'sichuan'}, stream=True, timeout=120)
    types = {}; toks=[]; sys_ev=[]
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith('data: '): continue
        ev=json.loads(raw[6:]); t=ev.get('type'); types[t]=types.get(t,0)+1
        if t=='token': toks.append(ev.get('text',''))
        if t=='sys': sys_ev.append(ev.get('text',''))
    return types, sys_ev, ''.join(toks)

for label, text in [
    ("闲聊/无关话题", "今天A股行情怎么样"),
    ("模糊短输入", "推荐一下"),
]:
    print(f"\n===== {label}: {text} =====")
    types, sys_ev, out = ask(text, f"probe_{abs(hash(text))%10000}")
    print("events:", types)
    print("sys:", sys_ev)
    print("answer:", out[:400])
