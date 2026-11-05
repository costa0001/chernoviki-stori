import sys, json, base64, re, subprocess, time
import numpy as np, onnxruntime as ort

MD = '/home/claude/asr/sherpa-onnx-whisper-small/'
SR = 16000

def mel_filters(sr=16000, n_fft=400, n_mels=80):
    def hz2mel(f):
        f = np.asarray(f, float); m = f / (200.0 / 3)
        lin = f >= 1000.0
        return np.where(lin, 15.0 + np.log(np.maximum(f, 1e-9) / 1000.0) / (np.log(6.4) / 27.0), m)
    def mel2hz(m):
        m = np.asarray(m, float); f = m * (200.0 / 3)
        lin = m >= 15.0
        return np.where(lin, 1000.0 * np.exp((np.log(6.4) / 27.0) * (m - 15.0)), f)
    fftfreqs = np.linspace(0, sr / 2, n_fft // 2 + 1)
    mels = mel2hz(np.linspace(hz2mel(0), hz2mel(sr / 2), n_mels + 2))
    fdiff = np.diff(mels); ramps = mels[:, None] - fftfreqs[None, :]
    w = np.zeros((n_mels, len(fftfreqs)))
    for i in range(n_mels):
        lo = -ramps[i] / fdiff[i]; up = ramps[i + 2] / fdiff[i + 1]
        w[i] = np.maximum(0, np.minimum(lo, up))
    enorm = 2.0 / (mels[2:n_mels + 2] - mels[:n_mels]); w *= enorm[:, None]
    return w.astype(np.float32)

FB = mel_filters()
WIN = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(400) / 400)).astype(np.float32)

def logmel(x):
    x = np.concatenate([x, np.zeros(SR * 30 - len(x), np.float32)]) if len(x) < SR * 30 else x[:SR * 30]
    xp = np.pad(x, 200, mode='reflect')
    n = 1 + (len(xp) - 400) // 160
    idx = np.arange(400)[None, :] + 160 * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(xp[idx] * WIN, axis=1)) ** 2
    spec = spec[:-1]
    m = FB @ spec.T
    lg = np.log10(np.maximum(m, 1e-10)); lg = np.maximum(lg, lg.max() - 8.0)
    return ((lg + 4.0) / 4.0).astype(np.float32)[None]

so = ort.SessionOptions(); so.intra_op_num_threads = 2
enc = ort.InferenceSession(MD + 'small-encoder.int8.onnx', so, providers=['CPUExecutionProvider'])
dec = ort.InferenceSession(MD + 'small-decoder.int8.onnx', so, providers=['CPUExecutionProvider'])
meta = enc.get_modelmeta().custom_metadata_map
codes = meta['all_language_codes'].split(','); ltoks = [int(t) for t in meta['all_language_tokens'].split(',')]
RU = ltoks[codes.index('ru')]
SOT = [int(meta['sot']), RU, int(meta['transcribe']), int(meta['no_timestamps'])]
EOT = int(meta['eot'])
vocab = {}
for line in open(MD + 'small-tokens.txt', encoding='utf-8'):
    p = line.rstrip('\n').split(' ')
    if len(p) == 2: vocab[int(p[1])] = base64.b64decode(p[0])

def transcribe(x):
    k, v = enc.run(None, {'mel': logmel(x)})
    sk = np.zeros((12, 1, 448, 768), np.float32); sv = np.zeros_like(sk)
    toks = SOT[:]; out = []
    logits, sk, sv = dec.run(None, {'tokens': np.array([toks], np.int64), 'in_n_layer_self_k_cache': sk,
        'in_n_layer_self_v_cache': sv, 'n_layer_cross_k': k, 'n_layer_cross_v': v, 'offset': np.array([0], np.int64)})
    off = len(toks)
    max_new = int(len(x) / SR * 7) + 20
    for _ in range(min(max_new, 440 - off)):
        lg = logits[0, -1].copy(); lg[EOT + 1:] = -1e9
        t = int(lg.argmax())
        if t == EOT: break
        out.append(t)
        if len(out) > 30 and out[-10:] == out[-20:-10] == out[-30:-20]: out = out[:-20]; break
        logits, sk, sv = dec.run(None, {'tokens': np.array([[t]], np.int64), 'in_n_layer_self_k_cache': sk,
            'in_n_layer_self_v_cache': sv, 'n_layer_cross_k': k, 'n_layer_cross_v': v, 'offset': np.array([off], np.int64)})
        off += 1
    return b''.join(vocab.get(t, b'') for t in out).decode('utf-8', 'replace').strip()
