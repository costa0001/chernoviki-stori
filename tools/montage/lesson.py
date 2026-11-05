"""Монтаж урока (запись экрана PDF + окно Zoom) одним проходом.

Шаг 1 (фоном):  python3 fast_asr.py src.mp4 ph.jsonl     -> a16.wav, sil.txt, ph.jsonl
Шаг 2:          python3 lesson.py src.mp4 "Имя_файла.mp4" --drop 62.9,197.4 --cut 1333.90-1335.05
    --drop  время начала фраз из ph.jsonl, которые выкинуть целиком (шум, [музыка], смешок, «эм»)
    --cut   произвольные интервалы источника a-b (оговорка внутри фразы, найденная по громкости)
    --head  сколько секунд срезать в начале (чёрный кадр), по умолчанию 3.0
    --dry   только посчитать длительность, без рендера
Раскладка рассчитана на исходник 1920x1030 (браузер с PDF, камера Zoom справа сверху).
Если исходник другой — поменять CROP_SLIDE / CROP_CAM (см. документ, раздел «Раскладка»).
"""
import sys, re, json, subprocess, argparse, os

CROP_SLIDE = "1536:862:181:158"   # w:h:x:y белой страницы PDF в исходнике
CROP_CAM = "208:156:1652:0"       # камера без плашки имени Zoom
FPS = 25

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--drop", default=""); ap.add_argument("--cut", default="")
ap.add_argument("--head", type=float, default=3.0); ap.add_argument("--dry", action="store_true")
A = ap.parse_args()
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "top.png")

dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", A.src]))
P = [json.loads(l) for l in open("ph.jsonl")]
drop = [float(x) for x in A.drop.split(",") if x.strip()]
cuts = [(0, A.head)]
for p in P:
    if any(abs(p["s"] - w) < 0.06 for w in drop): cuts.append((p["s"] - 0.05, p["e"] + 0.05))
for c in A.cut.split(","):
    if c.strip(): a, b = c.split("-"); cuts.append((float(a), float(b)))

ev = re.findall(r"silence_(start|end): ([0-9.]+)", open("sil.txt").read())
sp, prev = [], 0.0
for k, v in ev:
    v = float(v)
    if k == "start":
        if v - prev > 0.15: sp.append([prev, v])
    else: prev = v
if dur - prev > 0.15: sp.append([prev, dur])
m = []
for s, e in sp:                       # запас: −0,08 с до речи, +0,16 с после
    s = max(0, s - 0.08); e = min(dur, e + 0.16)
    if m and s <= m[-1][1] + 0.02: m[-1][1] = max(m[-1][1], e)
    else: m.append([s, e])
out = []
for s, e in m:
    segs = [[s, e]]
    for a, b in cuts:
        n = []
        for x, y in segs:
            if b <= x or a >= y: n.append([x, y])
            else:
                if x < a: n.append([x, a])
                if b < y: n.append([b, y])
        segs = n
    out += [x for x in segs if x[1] - x[0] > 0.12]
q = lambda t: round(t * FPS) / FPS     # ВАЖНО: границы по сетке кадров, иначе звук уплывает
out = [[q(s), q(e)] for s, e in out]; out = [x for x in out if x[1] > x[0]]
json.dump(out, open("keep.json", "w"))
total = sum(e - s for s, e in out)
print(f"кусков {len(out)}, исходник {dur/60:.1f} мин, урок {total/60:.2f} мин")
if A.dry: sys.exit()

S = "+".join(f"between(t,{s:.2f},{e-0.001:.3f})" for s, e in out)
open("fgv.txt", "w").write(
    f"[0:v]select='{S}',setpts=N/{FPS}/TB,split[a][b];"
    f"[a]crop={CROP_SLIDE},drawbox=x=0:y=0:w=iw:h=34:color=0xFAFBFE:t=fill,scale=1920:1080:flags=bicubic,setsar=1[s];"
    f"[b]crop={CROP_CAM},scale=344:258:flags=lanczos[c];[s][c]overlay=1548:28[t1];[t1][1:v]overlay=1508:0,format=yuv420p[v]")
open("fga.txt", "w").write(f"[0:a]aselect='{S}',asetpts=N/SR/TB,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[au]")
pa = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-i", A.src, "-filter_complex_script", "fga.txt", "-map", "[au]",
                       "-c:a", "aac", "-b:a", "160k", "aud.m4a"])
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", A.src, "-i", TOP, "-filter_complex_script", "fgv.txt", "-map", "[v]",
                "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-tune", "stillimage",
                "-progress", "prog.txt", "vid.mp4"], check=True)
pa.wait()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "vid.mp4", "-i", "aud.m4a", "-map", "0:v", "-map", "1:a", "-c", "copy",
                "-movflags", "+faststart", "-shortest", A.out], check=True)
for t in [1, total * 0.3, total * 0.6, total - 20]:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.1f}", "-i", A.out, "-frames:v", "1", "-vf", "scale=640:-2", f"q{int(t)}.jpg"])
print("ГОТОВО", A.out)
