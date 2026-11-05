"""8-second ЦЕЛИ reel v2. Usage: celi2.py spec.json out.mp4
spec: layout HIGH|LOW|BAND, src, pieces [[s,d],..], flip, z, fx, fy (face centre, fractions), audio keep|mute,
      title [l1,l2], plates [6 short lines]"""
import json, math, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SP = json.load(open(sys.argv[1])); OUT = sys.argv[2]
W, H, FPS, DUR = 1080, 1920, 30, 8.0
NF = int(DUR * FPS)
D = "/usr/share/fonts/truetype/dejavu/"
def F(s): return ImageFont.truetype(D + "DejaVuSerifCondensed-Bold.ttf", s)
BLUE = (22, 86, 214); NAVY = (12, 34, 84); LIGHT = (228, 242, 255); WHITE = (255, 255, 255)
F_T = F(74); CX = W / 2
LAY = SP["layout"]
TITLE_Y = 172
if LAY == "LOW":   PL = (318, SP.get("pl1", 838)); CTA_Y = SP.get("cta_y", 975)
elif LAY == "HIGH": PL = (SP.get("pl0", 950), 1626); CTA_Y = 1752
else:               PL = (936, 1626); CTA_Y = 1752

def clamp(x): return max(0.0, min(1.0, x))
def ease_out(p): p = clamp(p); return 1 - (1 - p) ** 3
def ease_back(p):
    p = clamp(p); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2

def shadowed(w, h, r, fill, outline=None, width=0, a=95):
    t = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", t.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((20, 27, 20 + w, 27 + h), r, fill=(5, 20, 60, a))
    t = Image.alpha_composite(t, sh.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(t).rounded_rectangle((20, 20, 20 + w, 20 + h), r, fill=fill, outline=outline, width=width)
    return t

def wrap(text, font, maxw):
    words, lines, cur = text.split(" "), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if cur and font.getlength(t) > maxw: lines.append(cur); cur = w_
        else: cur = t
    if cur: lines.append(cur)
    return lines

def plate(text, font):
    lines = wrap(text, font, 920); lh = int(font.size * 1.17); px, py = 30, 12
    w = int(max(font.getlength(l) for l in lines) + 2 * px); h = lh * len(lines) + 2 * py
    t = shadowed(w, h, 22, LIGHT + (243,)); d = ImageDraw.Draw(t)
    for k, l in enumerate(lines):
        d.text((20 + w / 2, 20 + py + lh * k + lh / 2), l, font=font, fill=NAVY, anchor="mm")
    return t

def title_tile(lines):
    lh = int(F_T.size * 1.1); pad = 30
    f = F_T
    while max(f.getlength(s) for s in lines) + 2 * pad > 1060: f = F(f.size - 2)
    lh = int(f.size * 1.1)
    bw = int(max(f.getlength(s) for s in lines)) + 2 * pad
    t = Image.new("RGBA", (bw, lh * len(lines) + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    for k, s in enumerate(lines):
        d.text((bw / 2, pad + lh * k + lh / 2), s, font=f, fill=BLUE, anchor="mm", stroke_width=7, stroke_fill=WHITE)
    g = t.filter(ImageFilter.GaussianBlur(14)); g.putalpha(g.getchannel("A").point(lambda a: int(a * 0.6)))
    return Image.alpha_composite(g, t)

def cta_tile():
    f1, f2, f3 = F(48), F(124), F(36)
    a, b, c, e = "Напишите слово", "ЦЕЛИ", "и получите бесплатное место на практикуме", "воплощения целей · старт 2 ноября, 5 дней"
    if SP.get("yt"): a, b, f2 = "Переходите по ссылке", "ПОД ЭТИМ ВИДЕО", F(82)
    w = int(max(f1.getlength(a), f2.getlength(b), f3.getlength(c), f3.getlength(e)) + 80); h = 268
    t = shadowed(w, h, 32, WHITE + (250,), outline=BLUE + (255,), width=6, a=130); d = ImageDraw.Draw(t)
    d.text((20 + w / 2, 20 + 46), a, font=f1, fill=NAVY, anchor="mm")
    d.text((20 + w / 2, 20 + 128), b, font=f2, fill=BLUE, anchor="mm")
    d.text((20 + w / 2, 20 + 204), c, font=f3, fill=NAVY, anchor="mm")
    d.text((20 + w / 2, 20 + 243), e, font=f3, fill=NAVY, anchor="mm")
    return t

def transform(tile, scale=1.0, opacity=1.0):
    if abs(scale - 1) > 1e-3:
        tile = tile.resize((max(1, int(tile.width * scale)), max(1, int(tile.height * scale))), Image.LANCZOS)
    if opacity < 0.999:
        tile = tile.copy(); tile.putalpha(tile.getchannel("A").point(lambda a: int(a * opacity)))
    return tile
def put(c, tile, cx, cy): c.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))

# fit plates into region
for size in range(46, 33, -1):
    fnt = F(size); T_PL = [plate(s, fnt) for s in SP["plates"]]
    hs = [t.height - 40 for t in T_PL]
    if sum(hs) + 8 * (len(hs) - 1) <= PL[1] - PL[0]: break
gap = min(22, (PL[1] - PL[0] - sum(hs)) // max(1, len(hs) - 1))
YS, y = [], PL[0]
for h in hs: YS.append(y + h / 2); y += h + gap
T_TITLE, T_CTA = title_tile(SP["title"]), cta_tile()
T0 = [0.3 + 0.5 * i for i in range(len(T_PL))]
TC = T0[-1] + 0.55
print("plate font", size, "cta at", round(TC, 2))

def overlay(t):
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    put(c, transform(T_TITLE, 0.92 + 0.08 * ease_back((t + 0.3) / 0.45)), CX, TITLE_Y)
    for i, tile in enumerate(T_PL):
        p = (t - T0[i]) / 0.3
        if p > 0:
            side = -1 if i % 2 == 0 else 1
            put(c, transform(tile, 0.8 + 0.2 * ease_back(p), clamp(0.25 + p * 2)), CX + side * 170 * (1 - ease_out(p)), YS[i])
    p = (t - TC) / 0.35
    if p > 0:
        pulse = 1 + 0.08 * math.sin(max(0, t - TC - 0.35) * 2 * math.pi / 0.85)
        put(c, transform(T_CTA, (0.55 + 0.45 * ease_back(p)) * pulse, clamp(p * 2)), CX, CTA_Y + 50 * (1 - ease_out(p)))
    return c

# ---------- base video ----------
src = SP["src"]; pieces = SP["pieces"]; flip = "hflip," if SP.get("flip") else ""
ins, fc, total = [], [], 0.0
for i, (s, d) in enumerate(pieces):
    if i == len(pieces) - 1: d = DUR - total
    total += d
    ins += ["-ss", f"{s:.3f}", "-t", f"{d + 0.15:.3f}", "-i", src]
    if LAY == "BAND":
        BY, BH = 300, 608
        fc.append(f"[{i}:v]trim=0:{d:.3f},setpts=PTS-STARTPTS,{flip}split[a{i}][b{i}];"
                  f"[a{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:3,eq=brightness=-0.20:saturation=0.75,drawbox=x=0:y=0:w=iw:h=ih:color=0x0a1e50@0.45:t=fill[bg{i}];"
                  f"[b{i}]scale={W}:{BH}:force_original_aspect_ratio=increase,crop={W}:{BH},unsharp=5:5:0.5[bd{i}];"
                  f"[bg{i}][bd{i}]overlay=0:{BY},fps={FPS},setsar=1[v{i}];")
    else:
        z = SP.get("z", 1.0) * (1.0 if i % 2 == 0 else 1.08)
        SW, SH = int(W * z) // 2 * 2, int(H * z) // 2 * 2
        tgt = 1450 if LAY == "LOW" else 640
        oy = max(0, min(SH - H, int(SP["fy"] * SH - tgt)))
        ox = max(0, min(SW - W, int(SP.get("fx", 0.5) * SW - W / 2)))
        fc.append(f"[{i}:v]trim=0:{d:.3f},setpts=PTS-STARTPTS,{flip}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"scale={SW}:{SH}:flags=lanczos,crop={W}:{H}:{ox}:{oy},unsharp=5:5:0.4,fps={FPS},setsar=1[v{i}];")
    if SP.get("audio", "keep") == "keep":
        fc.append(f"[{i}:a]atrim=0:{d:.3f},asetpts=PTS-STARTPTS,volume=0.35,afade=t=in:d=0.04,afade=t=out:st={max(0, d - 0.06):.3f}:d=0.06,aresample=48000[a{i}];")
    else:
        fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{d:.3f}[a{i}];")
n = len(pieces)
fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[bv0][ba];")
fc.append(f"[bv0]zoompan=z='1+0.0004*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={FPS}[bv];")
fc.append(f"[ba]afade=t=out:st={DUR - 0.3}:d=0.3[aout];")
fc.append(f"[bv][{n}:v]overlay=0:0:format=auto,format=yuv420p[v]")
cmd = ["ffmpeg", "-v", "error", "-y"] + ins + ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
       "-filter_complex", "".join(fc), "-map", "[v]", "-map", "[aout]", "-c:v", "libx264", "-crf", "19", "-preset", "veryfast",
       "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", str(DUR), OUT]
ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for k in range(NF): ff.stdin.write(overlay(k / FPS).tobytes())
ff.stdin.close(); ff.wait(); print("done", OUT, ff.returncode)
