"""Анимированная пиксельная заставка при запуске.

Пока она показывается, в фоне загружаются библиотеки и компилируется
вычислительное ядро (поэтому первый расчёт потом идёт без задержки).

Четыре истории (выбор: Меню → Заставка при запуске):
  rocket  - «Старт ракеты»: отсчёт, зажигание, взлёт, выход в космос;
  chamber - «Камера сгорания»: подача CH4 и O2, поджиг, фронт пламени, струя;
  planet  - «Полёт к планете»: перелёт среди звёзд и выход на орбиту;
  fortran - «Из Фортрана в Питон»: перфокарты, старый терминал, питон и ракета.
"""

import math
import random
import threading
import time

from PIL import Image, ImageDraw

W, H = 192, 108          # логическое разрешение (пиксели истории)
SCALE = 4                # увеличение на экране
FPS = 15

# Палитра в цветах программы
SKY = (8, 12, 20)
SKY2 = (14, 24, 38)
STAR = (227, 236, 234)
TEAL = (45, 212, 191)
TEAL_D = (14, 124, 107)
HULL = (227, 236, 234)
HULL_S = (150, 165, 162)
GREY = (70, 82, 80)
GREY_D = (38, 46, 45)
ORANGE = (255, 146, 43)
YELLOW = (255, 212, 59)
WHITE = (250, 250, 245)
BLUE = (116, 192, 252)
BLUE_D = (40, 90, 170)
RED = (240, 80, 70)
GREEN = (80, 220, 120)
SMOKE = (150, 158, 160)

# --- пиксельный шрифт 3x5 -------------------------------------------------
FONT = {
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
    "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001001001001", "8": "111101111101111",
    "9": "111101111001111", "M": "1000111011101011000110001", "E": "111100110100111",
    "T": "111010010010010", "A": "010101111101101",
    "N": "1000111001101011001110001", "Q": "010101101110011",
    "W": "1000110001101011101110001",
    "R": "110101110101101", "O": "111101101101111", "G": "111100101101111",
    "P": "111101111100100", "I": "111010010010111", "D": "110101101101110",
    "K": "101101110101101", "S": "111100111001111", "L": "100100100100111",
    "C": "111100100100111", "U": "101101101101111", "Y": "101101010010010",
    "H": "101101111101101", "F": "111100110100100", "B": "110101110101110",
    "=": "000111000111000", ",": "000000000010100", ".": "000000000000010",
    ">": "100010001010100", " ": "000000000000000", "!": "010010010000010",
    "(": "001010010010001", ")": "100010010010100", "_": "000000000000111",
    "+": "000010111010000", "-": "000000111000000",
}


def _gw(g):
    return 5 if len(g) == 25 else 3


def text(d, s, x, y, col, scale=1):
    for ch in s.upper():
        g = FONT.get(ch)
        if g:
            gw = _gw(g)
            for n, bit in enumerate(g):
                if bit == "1":
                    px, py = x + (n % gw) * scale, y + (n // gw) * scale
                    d.rectangle((px, py, px + scale - 1, py + scale - 1), fill=col)
            x += (gw + 1) * scale
        else:
            x += 4 * scale


def text_w(s, scale=1):
    w = sum((_gw(FONT[ch]) + 1) if ch in FONT else 4 for ch in s.upper())
    return w * scale - scale


# --- общие элементы --------------------------------------------------------
_rnd = random.Random(42)
STARS = [(_rnd.randrange(W), _rnd.randrange(H), _rnd.random() * 6.28,
          _rnd.choice((1, 1, 1, 2))) for _ in range(90)]


def starfield(d, t, dx=0.0, dy=0.0, bright=1.0):
    for x0, y0, ph, layer in STARS:
        x = int((x0 + dx * layer) % W)
        y = int((y0 + dy * layer) % H)
        k = 0.55 + 0.45 * math.sin(t * 3 + ph)
        k *= bright
        col = tuple(int(c * k) for c in STAR)
        d.point((x, y), fill=col)
        if layer == 2 and k > 0.8:
            d.point((x + 1, y), fill=col)


def sky(img, top=SKY, bottom=SKY2):
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line((0, y, W, y), fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)))
    return d


def rocket(d, x, y, flame=0.0, t=0.0, small=False):
    """Ракета (вертикально), x - центр, y - низ корпуса."""
    if small:
        d.rectangle((x - 1, y - 7, x + 1, y), fill=HULL)
        d.point((x, y - 8), fill=TEAL)
        if flame > 0:
            d.rectangle((x - 1, y + 1, x + 1, y + 2 + int(2 * flame)), fill=ORANGE)
        return
    # пламя
    if flame > 0:
        L = int(6 + 10 * flame + 2 * math.sin(t * 40))
        for i in range(L):
            w = max(0, 3 - i // 4)
            col = WHITE if i < 2 else (BLUE if i < L * 0.45 else
                                       (ORANGE if i < L * 0.8 else YELLOW))
            d.line((x - w, y + 1 + i, x + w, y + 1 + i), fill=col)
    # стабилизаторы
    d.polygon([(x - 4, y - 6), (x - 7, y - 1), (x - 7, y), (x - 4, y)], fill=TEAL)
    d.polygon([(x + 4, y - 6), (x + 7, y - 1), (x + 7, y), (x + 4, y)], fill=TEAL)
    # корпус
    d.rectangle((x - 4, y - 20, x + 4, y), fill=HULL)
    d.rectangle((x + 2, y - 20, x + 4, y), fill=HULL_S)
    d.polygon([(x - 4, y - 20), (x, y - 27), (x + 4, y - 20)], fill=TEAL)
    d.rectangle((x - 4, y - 4, x + 4, y - 3), fill=TEAL)
    d.ellipse((x - 2, y - 15, x + 2, y - 11), fill=TEAL_D, outline=GREY_D)
    d.rectangle((x - 3, y + 1, x + 3, y + 1), fill=HULL_S)


def puff(d, x, y, r, col):
    d.ellipse((x - r, y - r, x + r, y + r), fill=col)


# --- история 1: старт ракеты ----------------------------------------------
class RocketStory:
    title = "Старт ракеты"
    length = 9.0

    def frame(self, t):
        img = Image.new("RGB", (W, H))
        d = sky(img)
        # подъём камеры после взлёта
        lift = 0.0
        if t > 3.2:
            tt = t - 3.2
            lift = 6 * tt * tt            # высота ракеты над площадкой
        cam = max(0.0, lift - 30)          # камера начинает следовать
        starfield(d, t, dy=cam * 0.15, bright=min(1.0, 0.6 + cam / 200))
        # луна
        mx, my = 160, int(18 + cam * 0.05)
        d.ellipse((mx - 9, my - 9, mx + 9, my + 9), fill=(220, 226, 214))
        d.ellipse((mx - 4, my - 6, mx, my - 2), fill=(196, 202, 190))
        d.ellipse((mx + 2, my + 2, mx + 5, my + 5), fill=(196, 202, 190))
        gy = int(92 + cam)                 # уровень земли на экране
        if gy < H + 40:
            # земля и площадка
            d.rectangle((0, gy, W, gy + 40), fill=(20, 32, 30))
            d.rectangle((0, gy, W, gy + 1), fill=TEAL_D)
            for hx in range(0, W, 23):
                d.polygon([(hx, gy), (hx + 12, gy - 6), (hx + 24, gy)], fill=(16, 26, 25))
            # башня обслуживания
            tx = 112
            for yy in range(gy - 44, gy, 4):
                d.line((tx, yy, tx + 6, yy + 4), fill=GREY)
                d.line((tx + 6, yy, tx, yy + 4), fill=GREY)
            d.rectangle((tx, gy - 44, tx, gy), fill=GREY)
            d.rectangle((tx + 6, gy - 44, tx + 6, gy), fill=GREY)
            arm = 0 if t < 2.6 else min(1, (t - 2.6) * 2)
            d.rectangle((tx - 12 + int(10 * arm), gy - 34, tx, gy - 33), fill=GREY)
            d.point((tx + 3, gy - 46), fill=RED if int(t * 2) % 2 else (80, 20, 20))
            d.rectangle((86, gy - 2, 106, gy), fill=GREY)
        # дым у площадки
        if t > 2.4:
            k = min(1.0, (t - 2.4) / 1.5)
            for i in range(14):
                ang = i / 14 * math.pi
                rr = 4 + 18 * k * (0.5 + 0.5 * math.sin(i * 7.1))
                px = 96 + math.cos(ang) * (8 + 34 * k) * (1 if i % 2 else -1)
                py = gy - 2 - abs(math.sin(ang)) * 6 * k
                puff(d, int(px), int(py), int(rr * 0.5) + 2,
                     tuple(int(c * (0.7 + 0.3 * math.sin(i))) for c in SMOKE))
        # ракета
        ry = int(gy - 2 - lift)
        ry_screen = ry
        flame = 0.0 if t < 2.4 else min(1.0, (t - 2.4) * 1.5)
        if lift > 60:
            ry_screen = int(gy - 2 - 30 - (lift - 30)) + int(cam)
        if t > 6.5:
            ry_screen = int(62 - (t - 6.5) * 30)
        # инверсионный след
        if t > 3.4:
            for i in range(30):
                yy = ry_screen + 6 + i * 2
                if yy < H:
                    puff(d, 96 + int(math.sin(i * 1.7 + t * 5)), yy, 1 + i // 8,
                         tuple(int(c * (1 - i / 34)) for c in SMOKE))
        rocket(d, 96, ry_screen, flame, t)
        # отсчёт
        if t < 2.4:
            n = 3 - int(t / 0.8)
            s = str(max(1, n))
            text(d, s, 96 - text_w(s, 4) // 2, 22, YELLOW, 4)
        elif t < 3.4:
            text(d, "GO!", 96 - text_w("GO!", 3) // 2, 24, TEAL, 3)
        if t > 7.4:
            text(d, "METAN", 96 - text_w("METAN", 3) // 2, 40, TEAL, 3)
        return img


# --- история 2: камера сгорания -------------------------------------------
class ChamberStory:
    title = "Камера сгорания"
    length = 7.0

    def __init__(self):
        r = random.Random(1)
        self.parts = [(r.random(), r.random(), r.choice("ofo"), r.random())
                      for _ in range(140)]

    LEN = 135

    @staticmethod
    def wall_r(x):
        """Радиус камеры (в пикселях от оси) по координате x."""
        if x < 34:
            return 14
        if x < 84:
            return 30
        if x < 124:
            return 30 - (x - 84) * 20 / 40
        return 10

    @staticmethod
    def noise(x, y, t):
        return (math.sin(x * 1.7 + t * 7) * math.sin(y * 2.3 - t * 5)
                + math.sin((x + y) * 0.9 + t * 11)) * 0.06

    def frame(self, t):
        img = Image.new("RGB", (W, H))
        d = sky(img, (10, 14, 16), (14, 22, 24))
        cy = 54
        x0 = 8
        ign = 1.5
        front = 0 if t < ign else min(170, (t - ign) * 100)
        # поле внутри камеры
        for x in range(0, self.LEN):
            r = int(self.wall_r(x))
            for y in range(-r, r + 1):
                X = x0 + x
                hot = 0.0
                if t > ign:
                    dist = x - abs(y) * 0.6
                    hot = max(0.0, min(1.0, (front - dist) / 30))
                    # горячее всего в слое смешения струй, холоднее у стенок
                    edge = abs(y) / max(1, r)
                    hot *= 1.0 - 0.35 * edge ** 3
                    hot += 0.6 * self.noise(x, y, t) * (hot > 0.05)
                    if x < 34 and abs(y) > 8:
                        hot *= 0.35
                if hot <= 0.02:
                    col = (22, 30, 34)
                elif hot < 0.4:
                    col = (int(120 * hot / 0.4), int(30 * hot / 0.4), 40)
                elif hot < 0.75:
                    k = (hot - 0.4) / 0.35
                    col = (120 + int(135 * k), 30 + int(116 * k), 40 - int(30 * k))
                else:
                    k = (hot - 0.75) / 0.25
                    col = (255, 146 + int(80 * k), 10 + int(150 * k))
                d.point((X, cy + y), fill=col)
        # стенки
        for x in range(0, self.LEN):
            r = int(self.wall_r(x))
            d.rectangle((x0 + x, cy - r - 3, x0 + x, cy - r - 1), fill=GREY)
            d.rectangle((x0 + x, cy + r + 1, x0 + x, cy + r + 3), fill=GREY)
        d.rectangle((x0 + 33, cy - 33, x0 + 34, cy - 15), fill=GREY)
        d.rectangle((x0 + 33, cy + 15, x0 + 34, cy + 33), fill=GREY)
        d.rectangle((x0 - 3, cy - 17, x0 - 1, cy + 17), fill=GREY)
        # подача: синие O2 (ось и уступ), оранжевые CH4 (кольцо)
        for fx, fy, kind, ph in self.parts:
            s = (fx + t * (0.35 + 0.2 * ph)) % 1.0
            if kind == "f":
                x = s * 55
                y = (6 + fy * 5) * (1 if ph > 0.5 else -1)
                col = ORANGE
            else:
                if ph < 0.4:
                    x, y = s * 70, (fy * 3) * (1 if ph > 0.2 else -1)
                else:
                    x = 34 + s * 40
                    y = (26 - s * 10 + fy * 2) * (1 if ph > 0.7 else -1)
                col = BLUE
            if t > ign and x > front - 10:
                continue
            d.point((x0 + int(x), cy + int(y)), fill=col)
        # искра поджига
        if ign - 0.3 < t < ign + 0.4:
            for i in range(8):
                a = i * 0.785 + t * 10
                d.point((x0 + 20 + int(math.cos(a) * 4), cy + int(math.sin(a) * 4)),
                        fill=WHITE)
            puff(d, x0 + 20, cy, 2, YELLOW)
        # струя из сопла с ромбами (скачки уплотнения)
        if front > 130:
            k = min(1.0, (front - 130) / 30)
            nx = x0 + self.LEN
            L = int((W - nx) * k)
            for i in range(L):
                w = 10 + i // 6 + int(math.sin(i * 0.8 + t * 20))
                fade = 1 - i / max(1, W - nx)
                col = tuple(int(a * fade + b * (1 - fade)) for a, b in
                            zip((116, 192, 252), (14, 22, 24)))
                d.line((nx + i, cy - w // 2, nx + i, cy + w // 2), fill=col)
            for j in range(4):
                dx = nx + 4 + j * 12
                if dx < nx + L - 4:
                    sz = 5 - j
                    d.polygon([(dx, cy), (dx + sz, cy - sz), (dx + 2 * sz, cy),
                               (dx + sz, cy + sz)], fill=WHITE)
        text(d, "CH4 + O2", 8, 8, ORANGE)
        text(d, "MET21", W - text_w("MET21") - 8, 8, TEAL)
        if t > ign + 1.6:
            s = "FKOMP 0.983"
            text(d, s, 96 - text_w(s) // 2, 96, YELLOW)
        return img


# --- история 3: полёт к планете --------------------------------------------
class PlanetStory:
    title = "Полёт к планете"
    length = 9.0

    def frame(self, t):
        img = Image.new("RGB", (W, H))
        d = sky(img, (6, 8, 16), (12, 14, 30))
        starfield(d, t, dx=-t * 30)
        # планета растёт справа
        k = min(1.0, t / 6.5)
        px = int(250 - 100 * k)
        pr = int(10 + 26 * k)
        py = 56
        # планета: полосы только внутри диска, тень справа
        for yy in range(-pr, pr + 1):
            half = int(math.sqrt(max(0, pr * pr - yy * yy)))
            band = (yy // 5) % 2
            base_c = (52, 150, 136) if band else (40, 128, 116)
            d.line((px - half, py + yy, px + half, py + yy), fill=base_c)
            sh = int(half * 0.35)
            d.line((px + half - sh, py + yy, px + half, py + yy),
                   fill=(24, 80, 74))
        d.arc((px - pr - 12, py - 6, px + pr + 12, py + 8), 200, 340, fill=TEAL, width=1)
        d.arc((px - pr - 12, py - 6, px + pr + 12, py + 8), 0, 160, fill=TEAL, width=1)
        # астероиды
        for i in range(4):
            ax = int((W + 30 - (t * 50 + i * 60)) % (W + 60)) - 30
            ay = 15 + i * 23
            d.polygon([(ax, ay), (ax + 4, ay - 2), (ax + 7, ay + 1), (ax + 4, ay + 4),
                       (ax + 1, ay + 3)], fill=GREY)
        # ракета (горизонтально): рисуем вертикальную и поворачиваем
        if t < 6.5:
            rx, ry = 50 + int(6 * math.sin(t * 2)), 56 + int(4 * math.sin(t * 3))
        else:
            a = (t - 6.5) * 1.6
            rx = px + int((pr + 12) * math.cos(a + math.pi))
            ry = py + int((pr * 0.4 + 6) * math.sin(a + math.pi))
        layer = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        rocket(ld, 20, 30, 0.8 if t < 6.5 else 0.3, t)
        ang = -90 if t < 6.5 else -90 - math.degrees((t - 6.5) * 1.6)
        layer = layer.rotate(ang, resample=Image.NEAREST)
        img.paste(layer, (rx - 20, ry - 20), layer)
        # траектория-индикатор
        d = ImageDraw.Draw(img)
        for i in range(0, W - 20, 6):
            col = TEAL if i < (W - 20) * k else GREY_D
            d.point((10 + i, H - 6), fill=col)
        text(d, "METAN", 8, 6, TEAL, 2)
        return img


# --- история 4: из Фортрана в Питон ---------------------------------------
class FortranStory:
    title = "Из Фортрана в Питон"
    length = 10.0
    LINES = ["PROGRAM MET21", "DO 10 I=1,46", "CALL EQN(A)", "CALL BOUND(A)",
             "10 CONTINUE", "STOP"]

    def frame(self, t):
        img = Image.new("RGB", (W, H))
        d = sky(img, (16, 18, 22), (24, 26, 30))
        # стол
        d.rectangle((0, 86, W, H), fill=(52, 40, 32))
        d.rectangle((0, 86, W, 87), fill=(80, 62, 48))
        # компьютер
        cx, cy = 60, 20
        d.rectangle((cx - 4, cy - 4, cx + 80, cy + 56), fill=(170, 160, 140))
        d.rectangle((cx, cy, cx + 76, cy + 48), fill=(10, 20, 12))
        d.rectangle((cx + 20, cy + 56, cx + 56, cy + 62), fill=(150, 140, 120))
        d.rectangle((cx + 10, cy + 62, cx + 66, cy + 66), fill=(130, 120, 100))
        # щель для перфокарт и перфокарты
        d.rectangle((cx + 84, 70, cx + 110, 74), fill=(130, 120, 100))
        for i in range(3):
            s = (t * 0.7 + i / 3) % 1.0
            if t < 4.5:
                x = int(W + 10 - s * 70)
                y = 58 + int(6 * math.sin(s * 3))
                d.rectangle((x, y, x + 14, y + 8), fill=(230, 214, 170))
                for k in range(5):
                    d.point((x + 2 + k * 2, y + 2 + (k * 3) % 5), fill=(120, 100, 70))
        # экран
        green = (90, 230, 120)
        if t < 4.5:
            n = int(t / 0.6)
            for i, line in enumerate(self.LINES[:n + 1]):
                s = line if i < n else line[:int((t % 0.6) / 0.6 * len(line))]
                text(d, s, cx + 3, cy + 3 + i * 7, green)
        elif t < 5.3:
            r = random.Random(int(t * 30))
            for _ in range(60):
                x, y = cx + r.randrange(76), cy + r.randrange(48)
                d.rectangle((x, y, x + r.randrange(6), y), fill=r.choice((green, TEAL, WHITE)))
        else:
            text(d, ">>> IMPORT METAN", cx + 3, cy + 3, TEAL)
            if t > 6.0:
                text(d, "OK  FKOMP 0.983", cx + 3, cy + 11, YELLOW)
        # питон выползает из экрана
        if t > 5.3:
            k = min(1.0, (t - 5.3) / 1.6)
            seg = int(24 * k)
            for i in range(seg):
                x = cx + 70 - i * 3
                y = cy + 40 + int(3 * math.sin(i * 0.7 - t * 6)) + (i > 12) * (i - 12) * 2
                if y > 84:
                    y = 84
                col = TEAL if i % 2 else YELLOW
                d.rectangle((x, y, x + 2, y + 2), fill=col)
            if seg:
                hx = cx + 70 + 3
                hy = cy + 40 + int(3 * math.sin(-t * 6))
                d.rectangle((hx, hy - 1, hx + 4, hy + 3), fill=TEAL)
                d.point((hx + 3, hy), fill=WHITE)
                if int(t * 4) % 2:
                    d.point((hx + 5, hy + 2), fill=RED)
        # ракета стартует с монитора
        if t > 7.0:
            ry = int(cy - 6 - (t - 7.0) ** 2 * 14)
            rocket(d, cx + 38, ry, 0.9, t, small=False)
        text(d, "FORTRAN > PYTHON", 8, 96, (170, 160, 140))
        return img


STORIES = {}


def _register():
    from .splash_stories import STORIES2
    STORIES.update(STORIES2)
    STORIES.update(OLD_STORIES)


OLD_STORIES = {
    "rocket": ("Старт ракеты (простая)", RocketStory),
    "chamber": ("Камера сгорания", ChamberStory),
    "planet": ("Полёт к планете", PlanetStory),
    "fortran": ("Из Фортрана в Питон", FortranStory),
}
_register()


def render_gif(key, path, scale=3, fps=FPS):
    story = STORIES[key][1]()
    sw, sh = getattr(story, "size", (W, H))
    n = int(story.length * fps)
    frames = [story.frame(i / fps).resize((sw * scale, sh * scale), Image.NEAREST)
              .convert("P", palette=Image.ADAPTIVE, colors=128) for i in range(n)]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=int(1000 / fps), loop=0, optimize=True)
    return path


# --- окно заставки -------------------------------------------------------
def _warmup(status):
    """Загрузка библиотек и компиляция ядра (идёт в фоне за заставкой)."""
    import importlib
    status("Загрузка библиотек…")
    for mod in ("numpy", "matplotlib", "matplotlib.figure"):
        importlib.import_module(mod)
    status("Подготовка вычислительного ядра (numba)…")
    from ..params import Params
    from ..solver import Solver
    Solver(Params(NVARM=1, NMAX=2, NPRINT=1), track_history=False).run()
    status("Запуск интерфейса…")
    for mod in ("customtkinter", "metan.app.main"):
        importlib.import_module(mod)


def run_splash(key="rocket", min_time=4.0, max_time=180):
    """Показать заставку, пока идёт подготовка. key="none" - без заставки
    (подготовка всё равно выполняется)."""
    if key not in STORIES:
        try:
            _warmup(lambda s: None)
        except Exception:
            pass
        return
    import tkinter as tk
    from PIL import ImageTk

    story = STORIES[key][1]()
    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(background="#0d1312")
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    fw, fh = getattr(story, "size", (W, H))
    scale = max(2, min(SCALE, int(min(sw * 0.6 / fw, sh * 0.6 / fh))))
    w, h = fw * scale, fh * scale + 56
    root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))
    lab = tk.Label(root, borderwidth=0, background="#0d1312")
    lab.pack()
    status = tk.StringVar(value="Запуск…")
    tk.Label(root, textvariable=status, background="#0d1312", foreground="#93a7a3",
             font=("Consolas", 10)).pack(pady=(8, 2))
    bar = tk.Canvas(root, width=w - 40, height=4, background="#26332f",
                    highlightthickness=0)
    bar.pack()
    fill = bar.create_rectangle(0, 0, 0, 4, fill="#2dd4bf", width=0)
    state = {"done": False, "msg": "Запуск…", "step": 0}

    def set_status(s):
        state["msg"] = s
        state["step"] += 1

    def work():
        try:
            _warmup(set_status)
        except Exception:
            pass
        state["done"] = True

    threading.Thread(target=work, daemon=True).start()
    t0 = time.monotonic()
    holder = {}

    def tick():
        t = time.monotonic() - t0
        img = story.frame(t % story.length).resize((fw * scale, fh * scale),
                                                    Image.NEAREST)
        holder["img"] = ImageTk.PhotoImage(img)
        lab.configure(image=holder["img"])
        status.set(state["msg"])
        k = min(1.0, state["step"] / 4 + 0.05 * (t % 1))
        bar.coords(fill, 0, 0, int((w - 40) * k), 4)
        if (state["done"] and (t >= min_time or state.get("skip"))) or t > max_time:
            root.destroy()
            return
        root.after(int(1000 / FPS), tick)

    def skip(_e=None):
        if state["done"]:
            state["skip"] = True

    root.bind("<Button-1>", skip)
    root.bind("<Key>", skip)
    root.after(10, tick)
    root.mainloop()
