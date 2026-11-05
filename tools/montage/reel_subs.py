"""Burn large subtitles above the hands. Usage: subs.py in.mp4 subs.json out.mp4"""
import sys, json, subprocess, re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
IN, SJ, OUT = sys.argv[1:4]
W, H, FPS = 1080, 1920, 30
F = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf", 78)
NAVY = (10, 30, 80); WHITE = (255, 255, 255); ACC = (120, 200, 255)
CY = 1455
KEY = {"богатого", "щедрого", "три", "принципа", "щедрость", "себе", "стоишь", "принимать", "отказ", "радостью",
       "благодарностью", "денежное", "состояние", "страх", "копейку", "изобилия", "блок", "действие", "ДЕНЬГИ", "тест", "две", "минуты", "Первый", "Второе", "Третье"}
MAXW = 900

def chunks(text):
    words = text.split(); out, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if cur and (len(test) > 30 or (len(cur) >= 5)):
            out.append(" ".join(cur)); cur = [w]
        else: cur.append(w)
    if cur: out.append(" ".join(cur))
    # merge tiny tail
    if len(out) > 1 and len(out[-1]) < 8:
        last = out.pop(); out[-1] += " " + last
    return out

def lines_of(c):
    if F.getlength(c) <= MAXW: return [c]
    ws = c.split(); best = None
    for k in range(1, len(ws)):
        a, b = " ".join(ws[:k]), " ".join(ws[k:]); m = max(F.getlength(a), F.getlength(b))
        if best is None or m < best[0]: best = (m, [a, b])
    return best[1]

def tile(c):
    ls = lines_of(c); lh = 96; pad_x, pad_y = 34, 20
    w = int(max(F.getlength(l) for l in ls)) + 2 * pad_x; h = lh * len(ls) + 2 * pad_y
    t = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    sh = Image.new("RGBA", t.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((30, 38, 30 + w, 38 + h), 28, fill=(0, 0, 0, 120))
    t = Image.alpha_composite(t, sh.filter(ImageFilter.GaussianBlur(12))); d = ImageDraw.Draw(t)
    d.rounded_rectangle((30, 30, 30 + w, 30 + h), 28, fill=NAVY + (215,), outline=(70, 130, 230, 255), width=4)
    for k, l in enumerate(ls):
        x = 30 + (w - F.getlength(l)) / 2; y = 30 + pad_y + lh * k + lh / 2
        for wd in l.split(" "):
            core = re.sub(r"[^\wЁё]", "", wd)
            col = ACC if core in KEY else WHITE
            d.text((x, y), wd, font=F, fill=col, anchor="lm", stroke_width=3, stroke_fill=NAVY)
            x += F.getlength(wd + " ")
    return t

subs = json.load(open(SJ)); ev = []
for s, e, txt in subs:
    cs = chunks(txt); tot = sum(len(c) + 2 for c in cs); t = s
    for c in cs:
        d = (e - s) * (len(c) + 2) / tot; ev.append([t, t + d, c]); t += d
for i in range(len(ev) - 1):   # hold until next caption if gap is small
    if ev[i + 1][0] - ev[i][1] < 0.6: ev[i][1] = ev[i + 1][0]
ev[0][0] = 0.0
tiles = [tile(c) for _, _, c in ev]
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", IN]))
NF = int(dur * FPS)
ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-i", IN, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
    "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]", "-map", "0:a",
    "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-c:a", "copy", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
blank = Image.new("RGBA", (W, H), (0, 0, 0, 0)); cache = {}
j = 0
for n in range(NF):
    t = n / FPS
    while j < len(ev) - 1 and t >= ev[j + 1][0]: j += 1
    s, e, _ = ev[j]
    if not (s <= t < e + 0.05): ff.stdin.write(blank.tobytes()); continue
    p = min(1, (t - s) / 0.14); sc = round(0.86 + 0.14 * (1 - (1 - p) ** 3), 2)
    key = (j, sc)
    if key not in cache:
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); tl = tiles[j]
        if sc < 1: tl = tl.resize((int(tl.width * sc), int(tl.height * sc)), Image.LANCZOS)
        c.alpha_composite(tl, (int(W / 2 - tl.width / 2), int(CY - tl.height / 2)))
        cache = {k: v for k, v in cache.items() if k[0] == j}; cache[key] = c.tobytes()
    ff.stdin.write(cache[key])
ff.stdin.close(); ff.wait(); print("done", len(ev), "captions")
