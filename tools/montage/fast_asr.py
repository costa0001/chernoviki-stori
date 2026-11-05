import sys, json, subprocess, re, numpy as np, time
sys.argv, args = [sys.argv[0]], sys.argv[1:]
import asr
src, out = args
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-ac', '1', '-ar', '16000', 'a16.wav'], check=True)
log = subprocess.run(['ffmpeg', '-i', 'a16.wav', '-af', 'silencedetect=noise=-35dB:d=0.35', '-f', 'null', '-'], capture_output=True, text=True).stderr
open('sil.txt', 'w').write(log)
ev = re.findall(r'silence_(start|end): ([0-9.]+)', log)
audio = np.fromfile('a16.wav', dtype=np.int16, offset=44).astype(np.float32) / 32768.0
dur = len(audio) / 16000
ph = []; prev = 0.0
for k, v in ev:
    v = float(v)
    if k == 'start':
        if v - prev > 0.15: ph.append([prev, v])
    else: prev = v
if dur - prev > 0.15: ph.append([prev, dur])
U = []
for s, e in ph:
    while e - s > 9: U.append([s, s + 9]); s += 9
    if U and s - U[-1][1] < 0.45 and e - U[-1][0] <= 9: U[-1][1] = e
    else: U.append([s, e])
orig = asr.logmel
def short(x):
    m = orig(x); n = min(3000, int(len(x) / 160) + 400); n += n % 2
    return m[:, :, :n]
asr.logmel = short
t0 = time.time()
with open(out, 'w') as f:
    for i, (s, e) in enumerate(U):
        f.write(json.dumps({'s': round(s, 2), 'e': round(e, 2), 't': asr.transcribe(audio[int(s*16000):int(e*16000)])}, ensure_ascii=False) + '\n'); f.flush()
        if i % 20 == 0: print(i, len(U), round(time.time() - t0), flush=True)
print('ASRDONE', flush=True)
