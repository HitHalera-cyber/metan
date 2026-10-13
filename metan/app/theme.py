"""Оформление «Инженерный пульт»: палитры светлой и тёмной темы."""

import sys

LIGHT = dict(bg="#eef1f0", panel="#f6f8f7", card="#ffffff", fg="#12201d",
             muted="#4e605c", line="#d3dbd9", accent="#0e7c6b",
             accent_hover="#0a6457", accent_soft="#cdeae4", on_accent="#ffffff",
             danger="#c92a2a", danger_soft="#ffe3e3", warn="#b35c00")
DARK = dict(bg="#0d1312", panel="#111918", card="#18211f", fg="#e3ecea",
            muted="#93a7a3", line="#26332f", accent="#2dd4bf",
            accent_hover="#25b3a1", accent_soft="#134a42", on_accent="#04231e",
            danger="#ff6b6b", danger_soft="#3b1717", warn="#ffa94d")


def c(name):
    """Цвет для CTk-виджета: пара (светлая, тёмная)."""
    return (LIGHT[name], DARK[name])


def pal(mode):
    return DARK if mode == "dark" else LIGHT


if sys.platform == "win32":
    SANS, MONO = "Segoe UI", "Consolas"
elif sys.platform == "darwin":
    SANS, MONO = "Helvetica Neue", "Menlo"
else:
    SANS, MONO = "DejaVu Sans", "DejaVu Sans Mono"
