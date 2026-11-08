"""Вкладка «Уточнённая модель» (экспериментальная).

Удаление: папка metan/advanced и строка с AdvancedPage в metan/app/main.py.
"""

import dataclasses
import tkinter as tk
from tkinter import messagebox

import numpy as np

from .. import analysis, plotting
from ..app.pages import Page
from ..app.widgets import Plot, Table, button, label, option
from ..kernels import NT
from . import model as M

T_NAMES = {0: "исходная", 1: "сглаженная", 2: "равновесная"}


class AdvancedPage(Page):
    title = "Уточнённая модель"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar(0)
        label(tb, "Горение", 12, muted=True).pack(side="left")
        self.comb = tk.StringVar(value=M.COMBUSTION["instant"])
        option(tb, list(M.COMBUSTION.values()), lambda _v: self._sync(),
               self.comb, 210).pack(side="left", padx=(6, 14))
        label(tb, "турбулентность", 12, muted=True).pack(side="left")
        self.turb = tk.StringVar(value=M.TURBULENCE["algebraic"])
        option(tb, list(M.TURBULENCE.values()), None, self.turb, 200).pack(
            side="left", padx=(6, 14))
        label(tb, "температура", 12, muted=True).pack(side="left")
        self.temp = tk.StringVar(value=T_NAMES[2])
        self.temp_menu = option(tb, list(T_NAMES.values()), None, self.temp, 140)
        self.temp_menu.pack(side="left", padx=(6, 0))
        tb2 = self.toolbar(1)
        button(tb2, "Рассчитать", self.run_one, primary=True,
               width=130).pack(side="left")
        button(tb2, "Сравнить все модели", self.run_all, width=170).pack(
            side="left", padx=8)
        button(tb2, "Сеточное исследование (GCI)", self.run_grid,
               width=220).pack(side="left")
        self.show_btn = button(tb2, "Показать во всех вкладках", self.show_in_app,
                               width=200)
        self.show_btn.pack(side="right")
        self.note = label(
            self, "Экспериментальная вкладка: расчёт с уточнёнными моделями при "
            "исходных данных слева. Основная программа от неё не зависит.", 12, anchor="w", justify="left",
            wraplength=900, muted=True)
        self.note.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self._wrap = None
        self.bind("<Configure>", self._rewrap, add="+")
        self.plot = Plot(self, app, figsize=(8, 3.2))
        self.plot.grid(row=3, column=0, sticky="nsew")
        self.table = Table(self, app, ["Модель", "φк", "φβ", "Tвых, K"],
                           height=7, copy_button=True)
        self.table.grid(row=4, column=0, sticky="nsew", pady=(8, 0))
        self.grid_rowconfigure(3, weight=3, minsize=200)
        self.grid_rowconfigure(4, weight=3)
        self.results = []          # [(название, Results)]
        self.study = None
        self._sync()

    def _rewrap(self, e):
        w = max(300, e.width - 20)
        if self._wrap is None or abs(w - self._wrap) > 20:
            self._wrap = w
            self.note.configure(wraplength=w)

    def _sync(self):
        eq = self.comb.get() == M.COMBUSTION["equil"]
        edm = self.comb.get() == M.COMBUSTION["edm"]
        if eq or edm:
            self.temp_menu.configure(state="disabled")
        else:
            self.temp_menu.configure(state="normal")

    def _adv_options(self, comb=None, turb=None):
        inv_c = {v: k for k, v in M.COMBUSTION.items()}
        inv_t = {v: k for k, v in M.TURBULENCE.items()}
        inv_T = {v: k for k, v in T_NAMES.items()}
        return M.AdvOptions(combustion=comb or inv_c[self.comb.get()],
                            turbulence=turb or inv_t[self.turb.get()],
                            tmodel=inv_T[self.temp.get()])

    def _params(self):
        try:
            p = self.app.sidebar.params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return None
        if p.NVARM > 1:
            p = dataclasses.replace(p, NVARM=1)
        return p

    # ------------------------------------------------------------ расчёты
    def run_one(self):
        p = self._params()
        if p is None:
            return
        opt = self._adv_options()

        def job(progress, cancel):
            def prog(nvar, nvarm, niter, nmax):
                progress(niter / nmax, "Уточнённая модель: итерация %d/%d"
                         % (niter, nmax))
            return M.run(p, opt, progress=prog, cancel=cancel)

        def done(res):
            self.results = [(opt.short(), res)]
            self.study = None
            self.refresh()

        self.app.run_task(job, done, "Уточнённая модель")

    def run_all(self):
        p = self._params()
        if p is None:
            return
        combos = [(c, t) for t in ("algebraic", "keps")
                  for c in ("instant", "edm", "equil")]

        def job(progress, cancel):
            out = []
            # исходная программа - для сравнения
            from ..solver import Solver
            base = Solver(p, cancel=cancel).run()
            out.append(("исходная программа (T %s)"
                        % T_NAMES.get(p.TMODEL, "?"), base))
            for n, (c, t) in enumerate(combos):
                opt = M.AdvOptions(combustion=c, turbulence=t)

                def prog(nvar, nvarm, niter, nmax, n=n):
                    progress((n + niter / nmax) / len(combos),
                             "Модель %d из %d: итерация %d"
                             % (n + 1, len(combos), niter))
                out.append((opt.short(), M.run(p, opt, progress=prog,
                                                  cancel=cancel)))
            return out

        def done(res):
            self.results = res
            self.study = None
            self.refresh()

        self.app.run_task(job, done, "Сравнение моделей")

    def run_grid(self):
        p = self._params()
        if p is None:
            return
        opt = self._adv_options()
        if not messagebox.askyesno(
                "Сеточное исследование",
                "Расчёт на сетках 100×44, 141×62, 200×88, 283×124, 400×176 "
                "(пока GCI не станет меньше 2 %%; для равновесного горения - по φβ).\n"
                "Это может занять от нескольких минут до часа. Продолжить?"):
            return

        def job(progress, cancel):
            def prog(k, levels, niter, nmax):
                progress((k + niter / nmax) / levels,
                         "Сетка %d из %d: итерация %d/%d"
                         % (k + 1, levels, niter, nmax))
            return M.grid_study(p, opt, progress=prog, cancel=cancel)

        def done(out):
            rows, gcis = out
            self.study = (opt.short(), rows, gcis)
            self.results = [("%d×%d" % (r["IN"], r["JN"]), r["res"])
                            for r in rows]
            self.refresh()

        self.app.run_task(job, done, "Сеточное исследование")

    def show_in_app(self):
        """Последний (или единственный) уточнённый расчёт - во все вкладки."""
        if not self.results:
            messagebox.showinfo("Уточнённая модель", "Сначала выполните расчёт.")
            return
        name, res = self.results[-1]
        self.app.results = res
        self.app.variant_idx = 0
        self.app.add_run(res, "Уточнённая: " + name[:40])
        self.app._build_chips()
        self.app._update_right()
        self.app.status("Во вкладках - результат уточнённой модели: " + name)
        self.app.show_page("Поля")

    # ------------------------------------------------------------ вывод
    @staticmethod
    def _status(v):
        if v.diverged:
            return "расходится"
        if v.settled is False:
            n = v.extra.get("averaged", 0)
            return ("колеблется, среднее за %d итер." % n) if n \
                else "не установился"
        return "установился"

    def refresh(self):
        if not self.results:
            self.plot.message("Выберите модели и нажмите «Рассчитать»,\n"
                              "«Сравнить все модели» или «Сеточное исследование»")
            return
        rows, bad = [], []
        for name, res in self.results:
            v = res.variants[0]
            ex = analysis.exit_summary(v)
            rows.append([name, "%.4f" % v.fkomp,
                         "%.4f" % v.extra.get("FIbeta", np.nan),
                         "%.0f" % ex["T"], "%.4f" % ex["CH4"], str(v.NITER),
                         self._status(v)])
            bad.append(v.diverged or v.settled is False)
        self.table.set_columns(["Модель / сетка", "φк", "φβ", "Tвых, K",
                                "gCH4 вых", "N", "Состояние"])
        self.table.set_rows(rows, bad)
        txt = ""
        if self.study:
            name, srows, gcis = self.study
            txt = "Сеточное исследование (%s). " % name
            if gcis:
                g = gcis[-1]
                kinds = {"monotone": "сходится", "oscillating": "колеблется",
                         "diverging": "разности не убывают",
                         "converged": "не зависит от сетки"}
                m = g.get("metric", "φк")
                txt += ("Последние три сетки %s: GCI(%s) = %.2f %% (%s)"
                        % (" → ".join(g["grids"]), m, g["gci"],
                           kinds[g["kind"]]))
                if g["ext"] == g["ext"]:
                    txt += ", %s на бесконечно мелкой сетке ≈ %.4f" % (m, g["ext"])
                txt += "." + (" Сетки достаточно." if g["gci"] < 2 and
                              g["kind"] in ("monotone", "converged") else
                              " GCI ≥ 2 % - нужна более подробная сетка.")
            else:
                txt += "Для GCI нужны три сетки."
        else:
            txt = ("Красным - решения, которые не установились: при k–ε "
                   "течение за уступом колеблется (вязкость в 5–10 раз меньше "
                   "алгебраической), поля и φк - средние по последним "
                   "итерациям.")
        self.note.configure(text=txt)
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        cols = plotting.THEMES[self.app.mode]["series"]
        for n, (name, res) in enumerate(self.results):
            v = res.variants[0]
            r, T = analysis.radial_profile(v, NT, v.grid["IN"])
            ax.plot(r * 1000, T, "-" if n < len(cols) else "--",
                    color=cols[n % len(cols)], lw=1.6, label=name)
        ax.set_xlabel("r, мм")
        ax.set_ylabel("T на выходе, K")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5))
        ax.set_title("Профиль температуры на выходе", fontsize=11)
        self.plot.show()
