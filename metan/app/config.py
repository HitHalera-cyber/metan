"""Настройки интерфейса, сохраняемые между запусками."""

import json
import os
import sys

DEFAULTS = {"mode": "light", "scale": 1.0, "splash": "city",
            "right_panel": None}   # None - по размеру экрана


def _path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "Metan", "config.json")


SPLASH_REV = 2      # при смене заставки по умолчанию - увеличить


def load():
    d = dict(DEFAULTS)
    try:
        with open(_path(), encoding="utf-8") as fh:
            d.update(json.load(fh))
    except (OSError, ValueError):
        pass
    if d.get("splash_rev", 0) < SPLASH_REV:
        # новая заставка по умолчанию заменяет сохранённую старую
        d["splash"] = DEFAULTS["splash"]
        d["splash_rev"] = SPLASH_REV
    return d


def save(cfg):
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass
