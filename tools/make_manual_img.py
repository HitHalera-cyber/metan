"""Снимки окна программы и таблица параметров для руководства пользователя.

Запуск (Linux, нужен xvfb и ImageMagick):
    PYTHONPATH=. xvfb-run -s "-screen 0 1600x900x24" python tools/make_manual_img.py
Результат: docs/manual_img/*.jpg, splash.png, params.json, renames.json.
Затем: node tools/build_manual.js
"""

import json
import os
import subprocess
import sys
import tempfile
import time

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "manual_img")
sys.path.insert(0, ROOT)


def shot(name, box=None):
    tmp = os.path.join(tempfile.gettempdir(), "metan_shot.png")
    subprocess.run(["import", "-window", "root", tmp], check=True)
    im = Image.open(tmp).convert("RGB")
    if box:
        im = im.crop(box)
    im.save(os.path.join(OUT, name), quality=88)


def pump(app, t=0.6):
    t0 = time.time()
    while time.time() - t0 < t:
        app.update()
        time.sleep(0.03)


def wait(app, limit=900):
    t0 = time.time()
    while app.busy and time.time() - t0 < limit:
        app.update()
        time.sleep(0.05)
    pump(app, 0.8)


def data_files():
    from metan.params import GROUPS, Params
    from metan import notation
    titles = {k: t for k, t, _ in GROUPS}
    subs = {k: s for k, _, s in GROUPS}
    out = []
    for name, _, m in Params.field_info():
        if m.get("hidden"):
            continue
        out.append(dict(name=name, label=m["label"], sym=m["sym"],
                        unit=m["unit"], group=titles[m["group"]],
                        group_sub=subs[m["group"]], short=m["short"],
                        help=m["help"], default=getattr(Params(), name)))
    with open(os.path.join(OUT, "params.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    seen, ren = set(), []
    for ftn, s, name in notation.renames():
        if ftn in seen:
            continue
        seen.add(ftn)
        ren.append(dict(fortran=ftn, sym=s, name=name))
    with open(os.path.join(OUT, "renames.json"), "w", encoding="utf-8") as fh:
        json.dump(ren, fh, ensure_ascii=False, indent=0)


def splash_png():
    from metan.app.splash import make_story
    st = make_story("dawn", "light")
    im = st.frame(st.length * 0.7)
    im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
    im.save(os.path.join(OUT, "splash.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    data_files()
    splash_png()
    from metan.app.main import App
    res = tempfile.mkdtemp()

    app = App("light", cfg={"mode": "light", "scale": 1.0, "right_panel": True})
    app.geometry("1600x900+0+0")
    app.outdir.set(res)
    pump(app)
    shot("big_start.jpg")
    app.run()
    wait(app)
    app.sidebar.show_help("P")
    pump(app)
    shot("big_Поля.jpg")
    shot("big_sidebar_mode.jpg", (0, 50, 380, 900))
    app.sidebar.open_section("geom")
    pump(app)
    shot("big_sidebar_geom.jpg", (0, 50, 380, 900))
    app.sidebar.open_section("grid")
    pump(app)
    shot("big_sidebar_grid.jpg", (0, 50, 380, 620))
    app.sidebar.open_section("mode")

    # несколько значений α
    app.sidebar.multi_var.set(True)
    app.sidebar._multi_toggle()
    app.run()
    wait(app)
    shot("big_multi.jpg")
    pg = app.pages["Поля"]
    pg.style_var.set("Изолинии")
    pg.qty.set("Функция тока ψ")
    pg.mirror.set(False)
    pg.labels.set(True)
    pg.meters.set(True)
    pg.stream.set(False)
    pg.refresh()
    pump(app)
    shot("big_Поля_изолинии.jpg")
    for title in ("Профили", "Сходимость", "Анимация", "Геометрия"):
        app.show_page(title)
        pump(app, 1.0)
        shot("big_%s.jpg" % title)

    app.show_page("Серии")
    sp = app.page
    sp.v0.set("6")
    sp.v1.set("9")
    sp.n.set("7")
    sp.run()
    wait(app)
    shot("big_Серии.jpg")

    app.show_page("Подбор")
    op = app.page
    op.alpha.set("1.0")
    op.maxev.set("16")
    op.run()
    wait(app)
    shot("big_Подбор.jpg")

    # второй расчёт для сравнения
    app.sidebar.vars["DKR"].set("7")
    pump(app)
    app.run()
    wait(app)
    app.show_page("Сравнение")
    cp = app.page
    names = [n for n, _ in app.runs]
    cp.run_a.set(names[-2])
    cp._variants()
    cp.run_b.set(names[-1])
    cp._variants()
    cp.mode.set("Разность B − A")
    cp.refresh()
    pump(app, 1.0)
    shot("big_Сравнение_разность.jpg")
    app.sidebar.vars["DKR"].set("8")
    app.sidebar.multi_var.set(False)
    app.sidebar._multi_toggle()
    pump(app)
    app.run()
    wait(app)

    app.show_page("Сетка ×2")
    app.page.run()
    wait(app)
    shot("big_Сетка.jpg")
    app.show_page("Файлы .dat")
    pump(app)
    shot("big_Файлы_dat.jpg")

    app.toggle_theme()
    app.show_page("Поля")
    pump(app, 1.0)
    shot("big_dark_Поля.jpg")
    app.show_page("Анимация")
    pump(app, 1.0)
    shot("big_dark_Анимация.jpg")
    app.destroy()

    # маленький экран
    app = App("light", cfg={"mode": "light", "scale": 1.0})
    app.geometry("1366x768+0+0")
    app.outdir.set(res)
    pump(app)
    app.run()
    wait(app)
    shot("small_Поля.jpg", (0, 0, 1366, 768))
    app.destroy()
    print("ok", OUT)


if __name__ == "__main__":
    main()
