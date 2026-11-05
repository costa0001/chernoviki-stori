"""Whisper (sherpa-onnx export) via onnxruntime + numpy mel. Usage: asr.py wav segs.json out.json"""
import sys, json, base64, wave, numpy as np, onnxruntime as ort
M = "/home/claude/asr/sherpa-onnx-whisper-medium/medium-"
so = ort.SessionOptions(); so.intra_op_num_threads = 2
enc = ort.InferenceSession(M + "encoder.int8.onnx", so, providers=["CPUExecutionProvider"])
dec = ort.InferenceSession(M + "decoder.int8.onnx", so, providers=["CPUExecutionProvider"])
meta = enc.get_modelmeta().custom_metadata_map
L, CTX, ST = int(meta["n_text_layer"]), int(meta["n_text_ctx"]), int(meta["n_text_state"])
NM = int(meta["n_mels"])
sot_seq = list(map(int, meta["sot_sequence"].split(",")))
codes = meta["all_language_codes"].split(","); ltoks = list(map(int, meta["all_language_tokens"].split(",")))
sot_seq[1] = dict(zip(codes, ltoks))["ru"]
EOT, NOTS, SOT, NOSP, TR, BL = (int(meta[k]) for k in ["eot", "no_timestamps", "sot", "no_speech", "translate", "blank_id"])
tok = {}
for line in open(M + "tokens.txt"):
    t, i = line.split(); tok[int(i)] = t

def hz2mel(f):
    f = np.asarray(f, float); m = 3 * f / 200.0
    lg = f >= 1000; m[lg] = 15 + np.log(f[lg] / 1000) / (np.log(6.4) / 27); return m
def mel2hz(m):
    m = np.asarray(m, float); f = 200.0 * m / 3
    lg = m >= 15; f[lg] = 1000 * np.exp((np.log(6.4) / 27) * (m[lg] - 15)); return f
def melfb(sr=16000, n_fft=400, n=80):
    fft_f = np.linspace(0, sr / 2, n_fft // 2 + 1)
    mpts = mel2hz(np.linspace(hz2mel([0])[0], hz2mel([sr / 2])[0], n + 2))
    fd = np.diff(mpts); ramps = mpts[:, None] - fft_f[None, :]
    W = np.zeros((n, len(fft_f)))
    for i in range(n):
        lo = -ramps[i] / fd[i]; hi = ramps[i + 2] / fd[i + 1]
        W[i] = np.maximum(0, np.minimum(lo, hi))
    W *= (2.0 / (mpts[2:n + 2] - mpts[:n]))[:, None]; return W
FB = melfb(n=NM)
WIN = np.hanning(401)[:-1]
def logmel(x):
    x = np.pad(x, 200, mode="reflect")
    nfr = 1 + (len(x) - 400) // 160
    fr = np.lib.stride_tricks.as_strided(x, (nfr, 400), (x.strides[0] * 160, x.strides[0]))
    S = np.abs(np.fft.rfft(fr * WIN, axis=1)) ** 2
    S = S[:-1]
    m = FB @ S.T
    lg = np.log10(np.maximum(m, 1e-10)); lg = np.maximum(lg, lg.max() - 8.0)
    return ((lg + 4.0) / 4.0).astype(np.float32)

def transcribe(x):
    mel = logmel(x)
    mel = np.pad(mel, ((0, 0), (0, min(3000, mel.shape[1] + 1000) - mel.shape[1])))[None]
    ck, cv = enc.run(None, {enc.get_inputs()[0].name: mel})
    sk = np.zeros((L, 1, CTX, ST), np.float32); sv = np.zeros_like(sk)
    names = [i.name for i in dec.get_inputs()]; outs = [o.name for o in dec.get_outputs()][:3]
    def step(tks, sk, sv, off):
        return dec.run(outs, dict(zip(names, [np.array([tks], np.int64), sk, sv, ck, cv, np.array([off], np.int64)])))
    lg, sk, sv = step(sot_seq, sk, sv, 0); off = len(sot_seq)
    res = []
    for k in range(200):
        l = lg[0, -1].copy()
        l[[NOTS, SOT, NOSP, TR]] = -np.inf
        if k == 0: l[[EOT, BL]] = -np.inf
        t = int(l.argmax())
        if t == EOT: break
        res.append(t)
        if len(res) > 8 and res[-4:] == res[-8:-4]: break
        lg, sk, sv = step([t], sk, sv, off); off += 1
    return b"".join(base64.b64decode(tok[i]) for i in res if i in tok).decode("utf-8", "ignore").strip()

w = wave.open(sys.argv[1]); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
segs = json.load(open(sys.argv[2])); out = []
for s, e in segs:
    x = a[int(max(0, s - 0.15) * 16000):int((e + 0.15) * 16000)]
    txt = transcribe(x); out.append([s, e, txt]); print(f"{s:7.2f}-{e:7.2f} {txt}", flush=True)
json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=0)
