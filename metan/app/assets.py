"""Пути к файлам, поставляемым с программой (значок, руководство)."""

import os
import sys

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets_data")
MANUAL_NAME = "Metan_Руководство_пользователя.docx"


def _find(name):
    cands = [os.path.join(HERE, name)]
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        cands += [os.path.join(exe_dir, name),
                  os.path.join(getattr(sys, "_MEIPASS", exe_dir), "metan", "app",
                               "assets_data", name)]
    else:
        cands.append(os.path.join(HERE, "..", "..", "..", "docs", name))
    for p in cands:
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def icon_paths():
    return _find("metan.ico"), _find("metan.png")


def manual_path():
    return _find(MANUAL_NAME)
