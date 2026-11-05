"""Рисует top.png: рамка, тень, скругление и подпись окна спикера ОДНОЙ картинкой (накладывается в (1508,0)).
Окно камеры 344x258 в точке (1548,28) кадра 1920x1080. Фон картинки = цвет страницы слайда #FAFBFE.
Запуск: python3 make_top.py ["Имя на плашке"]"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
NAME = sys.argv[1] if len(sys.argv) > 1 else "Константин Браво"
CX, CY, CW, CH, R = 1548, 28, 344, 258, 22
x0, y0, x1, y1 = CX - 40, 0, 1920, CY + CH + 50
img = Image.new("RGBA", (1920, 1080), (250, 251, 254, 255))
sh = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle((CX, CY + 10, CX + CW, CY + CH + 10), R, fill=(10, 30, 80, 110))
img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(14)))
m = Image.new("L", (CW * 4, CH * 4), 0)
ImageDraw.Draw(m).rounded_rectangle((0, 0, CW * 4 - 1, CH * 4 - 1), R * 4, fill=255)
m = m.resize((CW, CH), Image.LANCZOS)
a = img.getchannel("A"); a.paste(Image.eval(m, lambda v: 255 - v), (CX, CY)); img.putalpha(a)
d = ImageDraw.Draw(img)
d.rounded_rectangle((CX - 3, CY - 3, CX + CW + 2, CY + CH + 2), R + 3, outline=(30, 95, 220, 255), width=4)
f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 22)
tw = d.textlength(NAME, font=f); bx = CX + CW / 2 - tw / 2 - 16; by = CY + CH - 40
d.rounded_rectangle((bx, by, bx + tw + 32, by + 32), 16, fill=(12, 34, 84, 225))
d.text((bx + 16, by + 4), NAME, font=f, fill=(255, 255, 255))
img.crop((x0, y0, x1, y1)).save("top.png"); print("top.png готов")
