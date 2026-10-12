"""第1轮：政务/商用高标准 —— 事实正确性与合规性"""
import requests, json, time
URL = 'http://127.0.0.1:8000/api/trip/stream'

def ask(text, sid):
    t0 = time.time()
    r = requests.post(URL, json={'user_input': text, 'session_id': sid, 'current_ip': 'sichuan'}, stream=True, timeout=120)
    toks = []; tools = 0
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith('data: '): continue
        ev = json.loads(raw[6:]); t = ev.get('type')
        if t == 'tool_start': tools += 1
        if t == 'token': toks.append(ev.get('text',''))
    return ''.join(toks), tools, round(time.time()-t0,1)

cases = [
    ("重庆2天1晚人均预算大概多少", "r1_budget", ["人均", "元"], []),
    ("哈尔滨冰雪大世界现在门票多少钱", "r1_ice", ["门票", "元"], ["我不知道", "无法回答"]),
    ("沈阳故宫和北京故宫是一个吗", "r1_sy", ["沈阳"], ["你已被转接至京京"]),
    ("洛阳老君山雨天怎么玩", "r1_ly", [], []),
]
for text, sid, must, forbidden in cases:
    out, tools, dt = ask(text, sid)
    ok = all(m in out for m in must) and not any(f in out for f in forbidden)
    print(f"[{'PASS' if ok else 'FAIL'}] {text}  ({dt}s,{tools}工具)")
    print("   答:", out[:200].replace('\n',' '))
    if must: print("   必含:", [m for m in must if m not in out] or "无缺失")
    print()
