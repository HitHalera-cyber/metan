"""Запуск окна программы (нужен дисплей: в CI - xvfb-run)."""
import os
import time

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")


def _display_ok():
    try:
        r = tk.Tk()
        r.destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _display_ok(), reason="нет дисплея")


def test_app_all_pages(tmp_path):
    from metan.app.main import PAGES, App
    app = App("light")
    try:
        app.outdir.set(str(tmp_path))
        app.sidebar.vars["NVARM"].set("2")
        app.sidebar.vars["NMAX"].set("40")
        app.sidebar.vars["NPRINT"].set("10")
        app.update()
        app.run()
        t0 = time.time()
        while app.busy and time.time() - t0 < 300:
            app.update()
            time.sleep(0.05)
        app.update()
        assert app.results is not None
        assert os.path.exists(tmp_path / "shi10.dat")
        assert os.path.exists(tmp_path / "shi20.dat")
        for P in PAGES:
            app.show_page(P.title)
            app.update()
        app.toggle_theme()
        app.update()
        app.select_variant(1)
        app.update()
    finally:
        app.destroy()
