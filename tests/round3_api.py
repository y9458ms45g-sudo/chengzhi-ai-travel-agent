"""第3轮：API 健壮性与商用体验"""
import requests, json
BASE = 'http://127.0.0.1:8000'

print("=== 3.1 API 非法输入不崩溃 ===")
tests = [
    ("POST /api/trip/stream 空body", lambda: requests.post(BASE+'/api/trip/stream', json={}, stream=True, timeout=30)),
    ("POST /api/feedback 非法rating", lambda: requests.post(BASE+'/api/feedback', json={'rating':'abc'}, timeout=10)),
    ("GET /api/history 无参", lambda: requests.get(BASE+'/api/history', timeout=10)),
    ("GET 不存在路由", lambda: requests.get(BASE+'/api/nope', timeout=10)),
]
for name, fn in tests:
    try:
        r = fn()
        body = r.text[:120].replace('\n',' ')
        print(f"[{r.status_code}] {name}: {body}")
    except Exception as e:
        print(f"[EXC] {name}: {e}")

print("\n=== 3.2 关键接口 ===")
for path in ['/api/health','/api/ip_map','/api/feedback/bad']:
    try:
        r = requests.get(BASE+path, timeout=10)
        print(f"[{r.status_code}] {path} -> {len(r.text)} bytes")
    except Exception as e:
        print(f"[EXC] {path}: {e}")

print("\n=== 3.3 看后端日志有无未捕获异常 ===")
import os
log = os.path.join(os.path.dirname(BASE), 'data','logs') if False else r'C:\Users\Administrator\wenlv-agent\data\logs'
import glob
latest = sorted(glob.glob(log+r'\*.log'))[-1]
errs = [l for l in open(latest, encoding='utf-8', errors='replace') if 'Traceback' in l or 'ERROR' in l]
print(f"日志: {os.path.basename(latest)}  异常行数: {len(errs)}")
for e in errs[-5:]: print("  ", e.strip()[:150])
