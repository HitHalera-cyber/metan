"""Заставки второго поколения (кадр 256x144, частицы, свет, камера).

  dawn      - «Рассвет на космодроме»
  teststand - «Огневые испытания»
  blueprint - «Чертёж оживает» (по данным реального расчёта)
  city      - «Ночной город»
"""

import json
import math
import os
import random

from PIL import Image, ImageDraw



def text(*a, **kw):
    from .splash import text as _t
    return _t(*a, **kw)


def text_w(*a, **kw):
    from .splash import text_w as _w
    return _w(*a, **kw)


W2, H2 = 256, 144
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets_data")

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def mix(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def gradient(img, stops, y0=0, y1=None, dither=True):
    """Вертикальный градиент по точкам [(доля, цвет), ...] с дизерингом."""
    y1 = H2 if y1 is None else y1
    px = img.load()
    for y in range(max(0, y0), min(H2, y1)):
        f = (y - y0) / max(1, (y1 - y0))
        for n in range(len(stops) - 1):
            if stops[n][0] <= f <= stops[n + 1][0]:
                a, b = stops[n], stops[n + 1]
                k = (f - a[0]) / max(1e-6, b[0] - a[0])
                break
        else:
            a = b = stops[-1]
            k = 0
        for x in range(W2):
            kk = k
            if dither:
                kk = k + (BAYER[y % 4][x % 4] / 16 - 0.5) * 0.18
            px[x, y] = mix(a[1], b[1], kk)


class Puffs:
    """Детерминированные частицы дыма/пара (позиция - функция времени)."""

    def __init__(self, n, seed, spawn, life, vx, vy, r0, growth, shades):
        r = random.Random(seed)
        self.p = []
        for _ in range(n):
            t0 = r.uniform(*spawn)
            self.p.append(dict(t0=t0, life=r.uniform(*life), vx=r.uniform(*vx),
                               vy=r.uniform(*vy), r0=r.uniform(*r0),
                               g=r.uniform(*growth), shade=r.choice(shades),
                               dx=r.uniform(-2, 2), dy=r.uniform(-1, 1)))

    def draw(self, d, t, x, y, drift=0.0, fade_to=None, light=None):
        for p in self.p:
            a = t - p["t0"]
            if a < 0 or a > p["life"]:
                continue
            k = a / p["life"]
            px = x + p["dx"] + p["vx"] * a * (1 - 0.35 * k) + drift * a
            py = y + p["dy"] + p["vy"] * a * (1 - 0.35 * k)
            rr = p["r0"] + p["g"] * a
            col = p["shade"]
            if light is not None:
                col = mix(col, light[0], light[1] * (1 - k))
            if fade_to is not None:
                col = mix(col, fade_to, k * k)
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=col)


SHADE = [0.5, 0.66, 0.8, 0.92, 1.0, 1.0, 0.94, 0.82, 0.68, 0.52]
HULL = (232, 238, 236)
TEAL = (45, 212, 191)
DARK = (22, 26, 28)


def big_rocket(d, cx, base, flame=0.0, t=0.0, stage=1, flame_len=40):
    """Ракета 10x62 пикселя; cx - центр, base - низ корпуса (сопла)."""
    x0 = cx - 5
    if stage == 1:
        # пламя первой ступени
        if flame > 0:
            L = int(flame_len * flame + 3 * math.sin(t * 37))
            for i in range(L):
                k = i / max(1, L)
                w = 2 + int(5 * k ** 0.6) + (1 if (i + int(t * 30)) % 5 == 0 else 0)
                col = mix((255, 255, 240), (255, 214, 90), k * 2) if k < 0.5 else \
                    mix((255, 170, 60), (200, 70, 30), (k - 0.5) * 2)
                d.line((cx - w, base + 3 + i, cx + w, base + 3 + i), fill=col)
        # двигатели
        for ex in (-3, 0, 3):
            d.rectangle((cx + ex - 1, base, cx + ex + 1, base + 2), fill=(90, 96, 100))
        # первая ступень
        for i, s in enumerate(SHADE):
            d.line((x0 + i, base - 40, x0 + i, base - 1), fill=mix((0, 0, 0), HULL, s))
        d.rectangle((x0, base - 30, x0 + 9, base - 29), fill=DARK)
        for i in range(3):
            text(d, "MET"[i], x0 + 3, base - 25 + i * 6, (40, 60, 64))
        # решётчатые рули
        d.rectangle((x0 - 2, base - 38, x0 - 1, base - 35), fill=(110, 116, 120))
        d.rectangle((x0 + 10, base - 38, x0 + 11, base - 35), fill=(110, 116, 120))
        top = base - 40
        d.rectangle((x0, top - 3, x0 + 9, top - 1), fill=DARK)    # межступенчатый отсек
    else:
        top = base
        if flame > 0:
            L = int(14 * flame + 2 * math.sin(t * 41))
            for i in range(L):
                k = i / max(1, L)
                w = 1 + int(3 * k)
                d.line((cx - w, top + 1 + i, cx + w, top + 1 + i),
                       fill=mix((210, 240, 255), (80, 150, 255), k))
        d.rectangle((cx - 1, top - 1, cx + 1, top), fill=(90, 96, 100))
        top -= 2
    # вторая ступень и обтекатель
    for i, s in enumerate(SHADE):
        d.line((x0 + i, top - 14, x0 + i, top - 1), fill=mix((0, 0, 0), HULL, s))
    d.rectangle((x0, top - 8, x0 + 9, top - 7), fill=mix((0, 0, 0), TEAL, 0.9))
    for row in range(9):
        half = int(5 * (1 - (row / 9) ** 1.6))
        for i in range(-half, half):
            s = SHADE[min(9, max(0, i + 5))]
            d.point((cx + i, top - 15 - row), fill=mix((0, 0, 0), HULL, s))


# ======================================================================
class DawnStory:
    title = "Рассвет на космодроме"
    length = 11.0
    size = (W2, H2)

    def __init__(self):
        self.vent = Puffs(40, 1, (0, 3.6), (1.5, 2.5), (-6, -2), (-3, -1), (0.6, 1.2),
                          (1.0, 2.0), [(220, 222, 226), (200, 204, 210)])
        self.smoke = Puffs(160, 2, (3.6, 6.5), (2.5, 4.5), (-38, 38), (-6, -1),
                           (2, 4), (3, 7), [(206, 196, 190), (176, 168, 166),
                                            (232, 220, 210), (150, 144, 146)])
        r = random.Random(5)
        self.stars = [(r.randrange(W2), r.randrange(H2 * 3), r.random() * 6) for _ in range(140)]
        r = random.Random(9)
        self.hills = [(i, 108 - int(10 * abs(math.sin(i * 0.031)) + 6 * math.sin(i * 0.11)))
                      for i in range(W2)]

    def frame(self, t):
        img = Image.new("RGB", (W2, H2))
        h = 0.0 if t < 4.2 else 11 * (t - 4.2) ** 2
        cam = max(0.0, h - 12)          # камера держит ракету в кадре
        k_space = ease(cam / 420)
        dawn = [(0, (34, 46, 98)), (0.55, (136, 92, 140)), (0.8, (250, 150, 110)),
                (1, (255, 206, 140))]
        space = [(0, (4, 6, 16)), (0.6, (10, 16, 40)), (1, (30, 46, 96))]
        stops = [(dawn[i][0], mix(dawn[i][1], space[min(i, 2)][1], k_space))
                 for i in range(4)]
        gradient(img, stops)
        d = ImageDraw.Draw(img)
        sb = 0.15 + 0.85 * k_space
        for sx, sy, ph in self.stars:
            y = int(sy - 2 * H2 + cam * 0.6)
            if 0 <= y < H2 and (y < 70 or k_space > 0.3):
                c = int(255 * sb * (0.6 + 0.4 * math.sin(t * 2 + ph)))
                d.point((sx, y), fill=(c, c, c))
        gy = int(116 + cam)
        # солнце
        sy = int(122 - t * 2.2 + cam)
        if sy < H2 + 20:
            for rr, col in ((22, (255, 190, 130)), (15, (255, 214, 150)), (10, (255, 236, 190))):
                d.ellipse((58 - rr, sy - rr, 58 + rr, sy + rr), fill=mix(col, stops[-1][1], 0.35 if rr == 22 else 0))
        if gy < H2 + 30:
            for x, hy in self.hills:
                d.line((x, hy + cam, x, gy), fill=(70, 52, 84))
            d.rectangle((0, gy, W2, gy + 40), fill=(38, 34, 52))
            d.line((0, gy, W2, gy), fill=(90, 70, 96))
            # подсветка земли пламенем
            if 3.6 < t < 7.5:
                glow = ease((t - 3.6) * 2) * (1 - ease((t - 6) / 1.5))
                d.ellipse((128 - 70, gy - 6, 128 + 70, gy + 10),
                          fill=mix((38, 34, 52), (180, 110, 70), 0.6 * glow))
            # стартовый стол и башня
            d.rectangle((110, gy - 4, 146, gy), fill=(60, 60, 70))
            tx = 146
            for yy in range(gy - 78, gy - 4, 5):
                d.line((tx, yy, tx + 8, yy + 5), fill=(84, 86, 98))
                d.line((tx + 8, yy, tx, yy + 5), fill=(84, 86, 98))
            d.line((tx, gy - 80, tx, gy - 4), fill=(96, 98, 110))
            d.line((tx + 8, gy - 80, tx + 8, gy - 4), fill=(96, 98, 110))
            arm = ease((t - 3.0) / 0.8)
            ax = int(134 + 10 * arm)
            d.rectangle((ax, gy - 58, tx, gy - 56), fill=(96, 98, 110))
            if int(t * 2) % 2:
                d.point((tx + 4, gy - 82), fill=(255, 60, 60))
        # дым и пар
        self.vent.draw(d, t, 132, gy - 46, fade_to=stops[1][1])
        self.smoke.draw(d, t, 128, gy - 4, light=((255, 170, 90), 0.5),
                        fade_to=mix((150, 140, 150), stops[-1][1], 0.3))
        # ракета
        base = int(gy - 7 - h)
        sep = t > 8.4
        if not sep:
            flame = 0.0 if t < 3.6 else ease((t - 3.6) * 2)
            big_rocket(d, 128, base, flame, t, 1, 34 + 14 * k_space)
        else:
            a = t - 8.4
            # отработавшая первая ступень уходит вниз
            bb = int(base + 18 * a * a + 30 * a)
            for i, s in enumerate(SHADE):
                d.line((123 + i - int(4 * a), bb - 40, 123 + i - int(4 * a), bb - 1),
                       fill=mix((0, 0, 0), HULL, s * 0.8))
            if a < 0.4:
                d.ellipse((120, base - 46, 136, base - 36), fill=(240, 240, 240))
            big_rocket(d, 128, base - 43, ease(a * 3), t, 2)
        # изгиб Земли
        if k_space > 0.55:
            e = ease((k_space - 0.55) / 0.45)
            ey = int(H2 + 30 - 52 * e)
            d.ellipse((-200, ey, W2 + 200, ey + 600), fill=(18, 48, 90))
            d.arc((-200, ey, W2 + 200, ey + 600), 180, 360, fill=(120, 200, 255), width=2)
            d.arc((-200, ey - 3, W2 + 200, ey + 597), 200, 340, fill=(40, 90, 160), width=1)
        # хронометраж в углу
        if t < 4.2:
            s = "T-00:0%d" % max(0, int(4.2 - t))
        else:
            s = "T+00:%02d" % int(t - 4.2)
        text(d, s, 8, 8, (255, 255, 255))
        text(d, "ALT %05d" % int(h * 12), 8, 16, (190, 200, 210))
        if t > 9.4:
            k = ease((t - 9.4) / 0.8)
            col = mix((10, 16, 40), TEAL, k)
            text(d, "METAN", W2 // 2 - text_w("METAN", 4) // 2, 78, col, 4)
            s = "CH4 + O2"
            text(d, s, W2 // 2 - text_w(s) // 2, 102, mix((10, 16, 40), (200, 210, 220), k))
        return img


# ======================================================================
class TestStandStory:
    title = "Огневые испытания"
    length = 9.0
    size = (W2, H2)

    def __init__(self):
        self.frost = Puffs(50, 3, (0, 9), (1.2, 2.2), (-4, 4), (-6, -3), (0.5, 1.0),
                           (0.6, 1.2), [(230, 236, 244), (214, 222, 234)])
        self.exhaust = Puffs(220, 4, (2.6, 9), (1.2, 2.2), (60, 110), (-24, -6),
                             (2, 4), (4, 9), [(196, 190, 186), (170, 164, 162),
                                              (226, 218, 210), (140, 136, 140)])

    def frame(self, t):
        shake = 0
        if t > 2.6:
            shake = int(math.sin(t * 90) > 0.6) - int(math.sin(t * 77) > 0.7)
        img = Image.new("RGB", (W2, H2))
        gradient(img, [(0, (14, 18, 30)), (0.7, (34, 40, 58)), (1, (52, 56, 70))])
        d = ImageDraw.Draw(img)
        gy = 118 + shake
        fire = 0.0 if t < 2.6 else ease((t - 2.6) * 3)
        d.rectangle((0, gy, W2, H2), fill=(44, 42, 46))
        if fire:
            for i in range(140):
                k = 1 - abs(i - 60) / 80
                d.line((110 + i, gy, 110 + i, gy + 2),
                       fill=mix((44, 42, 46), (190, 130, 90), 0.55 * fire * max(0, k)))
        # стенд
        d.rectangle((10, 52 + shake, 74, gy), fill=(84, 84, 90))
        d.rectangle((10, 52 + shake, 74, 55 + shake), fill=(110, 110, 118))
        for yy in range(60, gy, 10):
            d.line((14, yy + shake, 70, yy + shake), fill=(70, 70, 76))
        # обмёрзшие баки
        for bx, col in ((22, (226, 232, 238)), (48, (212, 224, 236))):
            d.rectangle((bx, 14 + shake, bx + 18, 52 + shake), fill=col)
            d.ellipse((bx, 8 + shake, bx + 18, 20 + shake), fill=col)
            for fy in range(20, 50, 4):
                d.point((bx + 3 + (fy * 7) % 12, fy + shake), fill=(255, 255, 255))
        text(d, "CH4", 25, 30 + shake, (60, 70, 90))
        text(d, "O2", 53, 30 + shake, (60, 70, 90))
        self.frost.draw(d, t, 40, 12 + shake)
        # двигатель (горизонтально): камера, горло, раструб
        ey = 84 + shake
        d.rectangle((74, ey - 7, 92, ey + 7), fill=(120, 118, 124))
        d.polygon([(92, ey - 7), (98, ey - 3), (98, ey + 3), (92, ey + 7)], fill=(110, 108, 114))
        d.polygon([(98, ey - 3), (116, ey - 12), (116, ey + 12), (98, ey + 3)], fill=(150, 120, 100))
        d.line((98, ey - 3, 116, ey - 12), fill=(190, 150, 120))
        if fire:
            d.polygon([(99, ey - 2), (115, ey - 10), (115, ey + 10), (99, ey + 2)],
                      fill=mix((150, 120, 100), (255, 170, 80), fire))
        # струя с ромбами
        if fire:
            L = int(130 * fire)
            for i in range(L):
                k = i / 130
                w = int(9 + 22 * k + math.sin(i * 0.5 + t * 30))
                col = mix((140, 200, 255), (40, 70, 140), k * 1.2)
                d.line((116 + i, ey - w // 2, 116 + i, ey + w // 2), fill=col)
            for j in range(6):
                dx = 120 + j * 17
                if dx > 116 + L - 6:
                    break
                sz = 6 - j // 2 + int(math.sin(t * 25 + j))
                d.polygon([(dx, ey), (dx + sz, ey - sz), (dx + 2 * sz, ey), (dx + sz, ey + sz)],
                          fill=(255, 250, 230))
                d.line((dx + 2, ey, dx + 2 * sz - 2, ey), fill=(255, 220, 160))
            self.exhaust.draw(d, t, 160, ey + 4, light=((255, 170, 100), 0.4),
                              fade_to=(34, 40, 58))
        # пульт
        px, py = 168, 8
        d.rectangle((px, py, px + 80, py + 44), fill=(8, 12, 14))
        d.rectangle((px, py, px + 80, py + 44), outline=TEAL)
        if t < 2.6:
            s = "T-%d" % max(1, int(2.6 - t) + 1)
            text(d, "READY", px + 6, py + 6, TEAL)
            text(d, s, px + 6, py + 16, (255, 212, 59), 2)
        else:
            k = ease((t - 2.6) / 2.5)
            vals = [("P", "%5.1f BAR" % (10.0 * k)), ("T", "%5d K" % int(3383 * k)),
                    ("FKOMP", "%.3f" % (0.983 * k))]
            for n, (a, b) in enumerate(vals):
                text(d, a, px + 6, py + 6 + n * 9, (150, 170, 170))
                text(d, b, px + 76 - text_w(b), py + 6 + n * 9, (255, 212, 59))
            # бегущий график
            for i in range(60):
                v = 0.5 + 0.35 * math.sin(i * 0.4 - t * 6) * k
                d.point((px + 10 + i, py + 40 - int(8 * v)), fill=TEAL)
        if fire > 0.5:
            text(d, "METAN", 8, 128, TEAL, 2)
        return img


# ======================================================================
class BlueprintStory:
    title = "Чертёж оживает"
    length = 10.5
    size = (W2, H2)
    # палитра температуры (как inferno), 9 ступеней
    PAL = [(12, 8, 40), (52, 12, 92), (106, 26, 110), (160, 44, 96), (206, 74, 66),
           (236, 118, 34), (250, 168, 30), (248, 220, 80), (252, 252, 180)]

    def __init__(self):
        with open(os.path.join(HERE, "splash_blueprint.json")) as fh:
            self.data = json.load(fh)
        self.T = Image.open(os.path.join(HERE, "splash_T.png")).load()
        self.Tsize = Image.open(os.path.join(HERE, "splash_T.png")).size
        pts = self.data["outline"]
        self.segs = []
        total = 0.0
        for a, b in zip(pts, pts[1:] + pts[:1]):
            L = math.dist(a, b)
            self.segs.append((a, b, total, L))
            total += L
        self.total = total
        self.lines = self.data["lines"]

    def _poly_part(self, d, frac, col):
        upto = frac * self.total
        head = None
        for a, b, s0, L in self.segs:
            if s0 >= upto:
                break
            k = min(1.0, (upto - s0) / L) if L > 0 else 1.0
            e = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            d.line((a[0], a[1], e[0], e[1]), fill=col)
            head = e
        return head

    def frame(self, t):
        img = Image.new("RGB", (W2, H2), (18, 52, 112))
        d = ImageDraw.Draw(img)
        for x in range(0, W2, 8):
            d.line((x, 0, x, H2), fill=(28, 66, 132) if x % 40 else (40, 84, 156))
        for y in range(0, H2, 8):
            d.line((0, y, W2, y), fill=(28, 66, 132) if y % 40 else (40, 84, 156))
        # заливка температурой (развёртка слева направо)
        if t > 5.8:
            sweep = ease((t - 5.8) / 2.6)
            ox, oy = self.data["T_origin"]
            tw, th = self.Tsize
            px = img.load()
            xmax = int(tw * sweep)
            for j in range(th):
                for i in range(xmax):
                    v = self.T[i, j]
                    if v:
                        f = (v - 1) / 254 * (len(self.PAL) - 1)
                        f += (BAYER[j % 4][i % 4] / 16 - 0.5)
                        idx = int(max(0, min(len(self.PAL) - 1, round(f))))
                        X, Y = ox + i, oy + j
                        if 0 <= X < W2 and 0 <= Y < H2:
                            px[X, Y] = self.PAL[idx]
        white = (236, 244, 255)
        # линии тока
        if t > 3.6:
            k = ease((t - 3.6) / 2.2)
            col = mix((18, 52, 112), (150, 220, 255), 1.0 if t < 6 else 0.75)
            for ln in self.lines:
                n = max(2, int(len(ln) * k))
                d.line([tuple(p) for p in ln[:n]], fill=col)
        # контур
        head = self._poly_part(d, ease(t / 2.4), white)
        if head and t < 2.6 and int(t * 8) % 2:
            d.rectangle((head[0] - 1, head[1] - 1, head[0] + 1, head[1] + 1), fill=(255, 255, 160))
        # размеры
        if t > 2.4:
            k = ease((t - 2.4) / 0.8)
            col = mix((18, 52, 112), (255, 220, 140), k)
            dm = self.data["dims"]
            cy, pxmm = self.data["cy"], self.data["px_mm"]
            for key, (xx, rmm) in (("DKS", dm["Dks"]), ("DKR", dm["Dkr"])):
                x = int(xx) + (6 if key == "DKS" else -2)
                r = rmm * pxmm
                d.line((x, cy - r, x, cy + r), fill=col)
                for s in (-1, 1):
                    yy = cy + s * r
                    d.line((x - 2, yy - s * 2, x, yy), fill=col)
                    d.line((x + 2, yy - s * 2, x, yy), fill=col)
                lab = "%s %d" % (key, round(2 * rmm))
                text(d, lab, x + 3, int(cy - r) - 7 if key == "DKS" else int(cy + r) + 3, col)
            x0 = self.data["x0"]
            lp = dm["Lprk"] * pxmm
            yb = int(cy + 14 * pxmm)
            d.line((x0, yb, x0 + lp, yb), fill=col)
            text(d, "LPRK %d" % round(dm["Lprk"]), int(x0 + 2), yb + 3, col)
        # штамп
        if t > 8.3:
            k = ease((t - 8.3) / 0.7)
            col = mix((18, 52, 112), white, k)
            bx, by = 168, 112
            d.rectangle((bx, by, bx + 82, by + 28), outline=col)
            d.line((bx, by + 14, bx + 82, by + 14), fill=col)
            d.line((bx + 40, by + 14, bx + 40, by + 28), fill=col)
            text(d, "METAN", bx + 4, by + 3, mix((18, 52, 112), TEAL, k), 2)
            text(d, "MET21", bx + 4, by + 18, col)
            text(d, "%.3f" % self.data["fkomp"], bx + 44, by + 18, mix((18, 52, 112), (255, 220, 140), k))
        text(d, "SHEET 1", 8, 8, (150, 190, 240))
        return img


# ======================================================================
class CityStory:
    """Город у реки и старт ракеты. mode="dark" - ночь, "light" - день."""
    title = "Ночной город"
    length = 11.0
    size = (W2, H2)
    RIVER = 108

    NIGHT = dict(sky=[(0, (6, 8, 26)), (0.5, (22, 22, 60)), (0.75, (64, 40, 86)),
                      (1, (70, 44, 90))],
                 hills=(24, 22, 46), bld=[(14, 14, 30)], win_on=0.45,
                 win=[(255, 214, 120), (150, 220, 255)], water=(8, 10, 24),
                 refl=0.55, bridge=(40, 40, 66), car=((255, 250, 220), (255, 70, 60)),
                 text=TEAL, sub=(180, 190, 210), tower=(30, 30, 50))
    DAY = dict(sky=[(0, (92, 156, 222)), (0.55, (150, 196, 236)), (0.85, (206, 226, 242)),
                    (1, (232, 238, 238))],
               hills=(150, 176, 172),
               bld=[(112, 130, 140), (132, 148, 156), (96, 116, 128), (150, 162, 166)],
               win_on=0.25, win=[(206, 230, 246), (236, 246, 252)], water=(120, 166, 200),
               refl=0.45, bridge=(104, 114, 124), car=((40, 44, 50), (200, 60, 50)),
               text=(14, 124, 107), sub=(60, 80, 90), tower=(100, 112, 124))

    def __init__(self, mode="dark"):
        self.mode = mode
        self.c = self.DAY if mode == "light" else self.NIGHT
        if mode == "light":
            self.title = "Город днём"
        r = random.Random(11)
        self.buildings = []
        x = -4
        while x < W2:
            w = r.randint(8, 22)
            h = r.randint(14, 52)
            self.buildings.append((x, w, h, r.random(), r.randrange(4)))
            x += w + r.randint(0, 3)
        self.windows = [(r.random(), r.random()) for _ in range(2000)]
        self.stars = [(r.randrange(W2), r.randrange(70), r.random() * 6) for _ in range(90)]
        self.clouds = [(r.uniform(0, W2 + 80), r.uniform(10, 60), r.uniform(8, 18),
                        r.uniform(2, 6)) for _ in range(7)]

    def path(self, s):
        """Траектория ракеты (s от 0 до 1): старт за городом справа, разворот влево."""
        x = 214 - 150 * s ** 1.6
        y = 92 - 92 * (1 - (1 - s) ** 1.8)
        return x, y

    def _sky(self, img, d, t):
        c = self.c
        gradient(img, c["sky"], 0, self.RIVER)
        if self.mode == "light":
            # солнце с ореолом
            for rr, col in ((16, (236, 240, 230)), (11, (255, 246, 214)), (7, (255, 252, 236))):
                d.ellipse((40 - rr, 26 - rr, 40 + rr, 26 + rr), fill=col)
            # облака плывут
            for cx, cy, cw, sp in self.clouds:
                x = (cx + t * sp) % (W2 + 80) - 40
                for k in range(4):
                    rr = cw * (0.45 + 0.15 * ((k * 7) % 3))
                    px = x + k * cw * 0.45
                    d.ellipse((px - rr, cy - rr * 0.6, px + rr, cy + rr * 0.6),
                              fill=(248, 250, 252))
                d.line((x - cw * 0.3, cy + cw * 0.3, x + cw * 1.6, cy + cw * 0.3),
                       fill=(226, 234, 242))
        else:
            for sx, sy, ph in self.stars:
                v = int(200 * (0.5 + 0.5 * math.sin(t * 2 + ph)))
                d.point((sx, sy), fill=(v, v, v))
            d.ellipse((30, 16, 44, 30), fill=(236, 232, 214))
            d.ellipse((34, 14, 48, 28), fill=(22, 22, 60))

    def _rocket(self, d, t):
        launch = 1.8
        if t <= launch:
            return
        s_now = min(1.0, (t - launch) / 6.0)
        n = int(s_now * 160)
        light = self.mode == "light"
        prev = None
        for i in range(n + 1):
            s = i / 160
            x, y = self.path(s)
            age = s_now - s
            if light:
                # белый дымный след, расплывается со временем
                rr = 0.8 + age * 9
                sh = int(255 - 30 * min(1, age * 1.5))
                col = mix((sh, sh, sh), self.c["sky"][1][1], min(1, age * 1.1))
                if i % 2 == 0:
                    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col)
            else:
                if s < 0.62:
                    col = mix((255, 200, 120), (64, 40, 86), min(1, age * 1.4))
                else:
                    col = mix((150, 200, 255), (30, 30, 70), min(1, age * 1.6))
                if prev:
                    d.line((prev[0], prev[1], x, y), fill=col, width=2 if age < 0.08 else 1)
            prev = (x, y)
        x, y = self.path(s_now)
        if light:
            d.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(60, 64, 70))
            d.ellipse((x - 1, y + 1, x + 2, y + 3), fill=(255, 150, 60))
        else:
            glow = (255, 240, 200) if s_now < 0.62 else (200, 230, 255)
            d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=glow)
        if 0.6 < s_now < 0.68:
            for a in range(8):
                ang = a * 0.785
                q = (s_now - 0.6) * 4
                d.point((x + 40 * math.cos(ang) * q, y + 40 * math.sin(ang) * q),
                        fill=(255, 255, 255) if not light else (255, 170, 80))

    def frame(self, t):
        c = self.c
        img = Image.new("RGB", (W2, H2))
        d = ImageDraw.Draw(img)
        self._sky(img, d, t)
        d = ImageDraw.Draw(img)
        self._rocket(d, t)
        # холмы и город
        for x in range(W2):
            hy = 82 + int(6 * math.sin(x * 0.03) + 3 * math.sin(x * 0.11))
            d.line((x, hy, x, self.RIVER), fill=c["hills"])
        wi = 0
        for bx, bw, bh, ph, tone in self.buildings:
            top = self.RIVER - bh
            col = c["bld"][tone % len(c["bld"])]
            d.rectangle((bx, top, bx + bw - 1, self.RIVER - 1), fill=col)
            if self.mode == "light":
                d.line((bx, top, bx, self.RIVER - 1), fill=mix(col, (255, 255, 255), 0.25))
                d.line((bx + bw - 1, top, bx + bw - 1, self.RIVER - 1), fill=mix(col, (0, 0, 0), 0.2))
            for yy in range(top + 3, self.RIVER - 3, 4):
                for xx in range(bx + 2, bx + bw - 2, 3):
                    a, b = self.windows[wi % len(self.windows)]
                    wi += 1
                    if self.mode == "light":
                        # блики стёкол; иногда «пробегает» отражение солнца
                        glint = math.sin(t * 2 - xx * 0.08 + b * 3) > 0.92
                        wc = (255, 255, 240) if glint else (c["win"][0] if a > c["win_on"]
                                                            else mix(col, (40, 60, 80), 0.4))
                        d.point((xx, yy), fill=wc)
                    else:
                        on = a > c["win_on"] or (a > 0.3 and math.sin(t * 1.5 + b * 20) > 0.6)
                        if on:
                            d.point((xx, yy), fill=c["win"][0] if b > 0.3 else c["win"][1])
        # телебашня
        d.line((120, self.RIVER - 70, 120, self.RIVER - 1), fill=c["tower"])
        d.rectangle((117, self.RIVER - 50, 123, self.RIVER - 46), fill=c["tower"])
        if int(t * 2) % 2:
            d.point((120, self.RIVER - 71), fill=(255, 60, 60))
        # мост и машины
        d.line((0, self.RIVER - 4, W2, self.RIVER - 4), fill=c["bridge"])
        for i in range(10):
            x = (i * 37 + t * 40) % (W2 + 20) - 10
            d.point((x, self.RIVER - 5), fill=c["car"][0])
            x2 = W2 - ((i * 53 + t * 34) % (W2 + 20)) + 10
            d.point((x2, self.RIVER - 6), fill=c["car"][1])
        # отражение в реке
        px = img.load()
        for y in range(self.RIVER, H2):
            dy = y - self.RIVER
            src = self.RIVER - 1 - dy
            off = int(2 * math.sin(y * 0.7 + t * 4))
            for x in range(W2):
                sx = min(W2 - 1, max(0, x + off))
                col = px[sx, max(0, src)]
                px[x, y] = mix(c["water"], col, c["refl"] - dy * 0.012)
        if self.mode == "light":
            for i in range(12):
                gx = int((i * 41 + t * 12) % W2)
                gy = self.RIVER + 4 + (i * 7) % 30
                d.line((gx, gy, gx + 3, gy), fill=(236, 244, 250))
        text(d, "METAN", 8, 128, c["text"], 2)
        if t > 8.5:
            s = "CH4 + O2"
            text(d, s, W2 - text_w(s) - 8, 132, c["sub"])
        return img


STORIES2 = {
    "city": ("Ночной город", CityStory),
    "dawn": ("Рассвет на космодроме", DawnStory),
    "teststand": ("Огневые испытания", TestStandStory),
    "blueprint": ("Чертёж оживает", BlueprintStory),
}
