"""Генерация значков программы (запуск: python tools/make_icons.py).

Создаёт metan/app/assets_data/metan.ico и .png (основной значок) и варианты
icon_*.png для выбора."""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), "..", "metan", "app", "assets_data")
BG = (13, 19, 18, 255)
TEAL = (45, 212, 191, 255)
TEAL_D = (14, 124, 107, 255)
HULL = (227, 236, 234, 255)
HULL_S = (176, 192, 189, 255)
BLUE = (116, 192, 252, 255)
ORANGE = (255, 146, 43, 255)
YELLOW = (255, 212, 59, 255)
S = 1024


def base():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((32, 32, S - 32, S - 32), radius=220, fill=BG)
    return im, d


def stars(d, seed=3, n=26):
    import random
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.randint(110, S - 110), rnd.randint(110, S - 110)
        r = rnd.choice([4, 5, 7])
        d.ellipse((x - r, y - r, x + r, y + r), fill=(227, 236, 234, rnd.choice([120, 180, 255])))


def flat_rocket():
    im, d = base()
    stars(d)
    # орбита
    d.ellipse((150, 300, 880, 760), outline=(45, 212, 191, 110), width=14)
    lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(lay)
    cx = S // 2
    # пламя: внешнее оранжевое, внутреннее голубое (метан + O2 горит синим)
    g.polygon([(cx - 70, 660), (cx + 70, 660), (cx + 40, 820), (cx, 940),
               (cx - 40, 820)], fill=ORANGE)
    g.polygon([(cx - 42, 660), (cx + 42, 660), (cx + 20, 790), (cx, 880),
               (cx - 20, 790)], fill=BLUE)
    g.polygon([(cx - 18, 660), (cx + 18, 660), (cx, 790)], fill=(235, 248, 255, 255))
    # стабилизаторы
    g.polygon([(cx - 95, 520), (cx - 200, 660), (cx - 200, 720), (cx - 95, 650)], fill=TEAL)
    g.polygon([(cx + 95, 520), (cx + 200, 660), (cx + 200, 720), (cx + 95, 650)], fill=TEAL)
    # корпус
    g.polygon([(cx, 120), (cx + 70, 220), (cx + 105, 360), (cx + 105, 660),
               (cx - 105, 660), (cx - 105, 360), (cx - 70, 220)], fill=HULL)
    g.polygon([(cx + 30, 160), (cx + 70, 220), (cx + 105, 360), (cx + 105, 660),
               (cx + 40, 660), (cx + 40, 330)], fill=HULL_S)
    # носовой обтекатель
    g.polygon([(cx, 120), (cx + 70, 220), (cx - 70, 220)], fill=TEAL)
    # иллюминатор
    g.ellipse((cx - 55, 330, cx + 55, 440), fill=TEAL_D, outline=BG, width=16)
    g.ellipse((cx - 30, 352, cx + 8, 390), fill=(160, 240, 228, 255))
    # сопло
    g.polygon([(cx - 70, 650), (cx + 70, 650), (cx + 85, 690), (cx - 85, 690)], fill=HULL_S)
    g.rectangle((cx - 105, 590, cx + 105, 612), fill=TEAL)
    lay = lay.rotate(-35, resample=Image.BICUBIC, center=(cx, S // 2 + 40))
    im.alpha_composite(lay, (0, -20))
    return im


PIXEL = [
    "................................",
    "...............##...............",
    "..............#TT#..............",
    ".............#TTTT#.............",
    "............#HHHHHH#............",
    "............#HHHHHS#............",
    "............#HHHHHS#............",
    "............#HHTTHS#............",
    "............#HTLLTS#............",
    "............#HTLLTS#............",
    "............#HHTTHS#............",
    "............#HHHHHS#............",
    "............#HHHHHS#............",
    "...........##HHHHHS##...........",
    "..........#T#HHHHHS#T#..........",
    ".........#TT#HHHHHS#TT#.........",
    "........#TTT#TTTTTT#TTT#........",
    "........#TT#.#SSSS#.#TT#........",
    "........###...####...###........",
    "..............OBBO..............",
    ".............OOBBOO.............",
    ".............OBWWBO.............",
    "..............OBBO..............",
    "...............OO...............",
    "..............Y..Y..............",
    "...............YY...............",
]
PCOL = {"#": (6, 10, 10, 255), "T": TEAL, "H": HULL, "S": HULL_S, "L": (160, 240, 228, 255),
        "O": ORANGE, "B": BLUE, "W": (235, 248, 255, 255), "Y": YELLOW}


def pixel_rocket():
    im, d = base()
    stars(d, seed=7, n=18)
    cell = 24
    ox = (S - 32 * cell) // 2
    oy = 150
    for r, row in enumerate(PIXEL):
        for col, ch in enumerate(row):
            if ch in PCOL:
                d.rectangle((ox + col * cell, oy + r * cell,
                             ox + (col + 1) * cell - 1, oy + (r + 1) * cell - 1),
                            fill=PCOL[ch])
    return im


def nozzle():
    im, d = base()
    cx = S // 2
    # камера и сопло (сечение)
    d.polygon([(cx - 150, 140), (cx + 150, 140), (cx + 150, 330), (cx + 60, 450),
               (cx + 60, 470), (cx + 190, 640), (cx - 190, 640), (cx - 60, 470),
               (cx - 60, 450), (cx - 150, 330)], fill=HULL_S)
    d.polygon([(cx - 110, 170), (cx + 110, 170), (cx + 110, 320), (cx + 35, 440),
               (cx + 35, 480), (cx + 150, 625), (cx - 150, 625), (cx - 35, 480),
               (cx - 35, 440), (cx - 110, 320)], fill=(24, 33, 31, 255))
    d.rectangle((cx - 150, 140, cx + 150, 165), fill=TEAL)
    # голубое пламя внутри
    d.polygon([(cx - 80, 190), (cx + 80, 190), (cx + 80, 310), (cx + 28, 440),
               (cx - 28, 440), (cx - 80, 310)], fill=(116, 192, 252, 200))
    # струя с ромбами
    d.polygon([(cx - 140, 640), (cx + 140, 640), (cx + 60, 900), (cx - 60, 900)],
              fill=(45, 212, 191, 120))
    for y0, h in ((660, 90), (760, 70), (840, 50)):
        w = 70 - (y0 - 660) // 5
        d.polygon([(cx, y0), (cx + w, y0 + h // 2), (cx, y0 + h), (cx - w, y0 + h // 2)],
                  fill=(235, 248, 255, 230))
    return im


def save_ico(im, path):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    im.save(path, sizes=[(s, s) for s in sizes])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    variants = {"rocket": flat_rocket(), "pixel": pixel_rocket(), "nozzle": nozzle()}
    for k, im in variants.items():
        im.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "icon_%s.png" % k))
        save_ico(im.resize((256, 256), Image.LANCZOS), os.path.join(OUT, "icon_%s.ico" % k))
    main = sys.argv[1] if len(sys.argv) > 1 else "rocket"
    im = variants[main]
    save_ico(im.resize((256, 256), Image.LANCZOS), os.path.join(OUT, "metan.ico"))
    im.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "metan.png"))
    # превью трёх вариантов на светлом и тёмном фоне
    prev = Image.new("RGBA", (3 * 300 + 40, 2 * 300 + 40), (238, 241, 240, 255))
    dk = Image.new("RGBA", (prev.width, 340), (30, 30, 30, 255))
    prev.paste(dk, (0, 320))
    for n, im in enumerate(variants.values()):
        sm = im.resize((256, 256), Image.LANCZOS)
        prev.alpha_composite(sm, (20 + n * 300, 30))
        for m, s in enumerate((16, 32, 48)):
            ic = im.resize((s, s), Image.LANCZOS)
            prev.alpha_composite(ic, (40 + n * 300 + m * 70, 400))
            prev.alpha_composite(ic.resize((s, s)), (40 + n * 300 + m * 70, 520))
    prev.save(os.path.join(OUT, "..", "..", "..", "docs", "icons_preview.png"))
    print("ok")
