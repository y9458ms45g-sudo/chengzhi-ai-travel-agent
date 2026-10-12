import requests, json, time
URL='http://127.0.0.1:8000/api/trip/stream'
def ask(text, sid):
    t0=time.time(); r=requests.post(URL, json={'user_input':text,'session_id':sid,'current_ip':'sichuan'}, stream=True, timeout=60)
    tools=0; toks=[]
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith('data: '): continue
        ev=json.loads(raw[6:])
        if ev.get('type')=='tool_start': tools+=1
        if ev.get('type')=='token': toks.append(ev.get('text',''))
    return ''.join(toks), tools, round(time.time()-t0,1)

for text, sid in [("旅游"*50, "verify_rep"), ("啊", "verify_huh"), ("重庆火锅推荐", "verify_real")]:
    out, tools, dt = ask(text, sid)
    print(f"输入[{text[:12]}...] -> {dt}s, {tools}工具, {len(out)}字")
    print("  ", out[:90].replace('\n',' '))
