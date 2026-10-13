"""Страницы исследований: серии, подбор, сравнение, проверка сетки, протокол."""

import os
import pickle
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import numpy as np

from .. import analysis, plotting, studies
from ..kernels import NT
from ..solver import VAR_NAMES
from .pages import FIELD_NAMES, FIELD_ORDER, PARAM_META, Page, _num
from .theme import c
from .widgets import (Plot, Table, button, caps, check, entry, label, option,
                      segmented)

METRICS = {"Fkomp": "fkomp", "T на выходе, K": "exit_T", "Ms, кг/с": "Ms",
           "CH4 на выходе": "exit_CH4", "O2 на выходе": "exit_O2",
           "CO2 на выходе": "exit_CO2"}


def _plabel(name):
    m = PARAM_META[name]
    return "%s — %s" % (name, m["label"])


def open_folder(path):
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ======================================================================
class SeriesPage(Page):
    title = "Серии"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.pname = tk.StringVar(value=_plabel("DKR"))
        option(tb, [_plabel(n) for n in studies.SERIES_PARAMS],
               lambda _v: self._defaults(), self.pname, width=330).pack(side="left")
        self.v0, self.v1, self.n = tk.StringVar(), tk.StringVar(), tk.StringVar(value="9")
        for t, var, w in (("от", self.v0, 80), ("до", self.v1, 80),
                          ("точек", self.n, 50)):
            label(tb, t, 12, muted=True).pack(side="left", padx=(10, 4))
            entry(tb, var, w).pack(side="left")
        button(tb, "Запустить серию", self.run, primary=True, width=160).pack(
            side="right")
        tb2 = self.toolbar(1)
        label(tb2, "Показать:", 12, muted=True).pack(side="left")
        self.metric = tk.StringVar(value="Fkomp")
        segmented(tb2, list(METRICS), lambda _v: self.refresh(),
                  self.metric).pack(side="left", padx=8)
        self.plot = Plot(self, app)
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.table = Table(self, app, ["значение"], height=6)
        self.table.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.grid_rowconfigure(2, weight=1)
        self._defaults()

    def _pname(self):
        return self.pname.get().split(" — ")[0]

    def _defaults(self):
        try:
            cur = float(self.app.sidebar.vars[self._pname()].get().replace(",", "."))
        except (ValueError, KeyError):
            cur = 1.0
        lo, hi = sorted((cur * 0.75, cur * 1.25))
        if self._pname() == "NMAX":
            lo, hi = 200, 2000
        self.v0.set("%.6g" % lo)
        self.v1.set("%.6g" % hi)

    def run(self):
        try:
            prm = self.app.sidebar.params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        a, b, n = _num(self.v0.get()), _num(self.v1.get()), int(_num(self.n.get(), 0) or 0)
        if a is None or b is None or n < 2:
            messagebox.showerror("Серия", "Укажите диапазон и число точек (≥ 2).")
            return
        name = self._pname()
        vals = list(np.linspace(a, b, n))
        if name in ("NMAX",):
            vals = sorted(set(int(round(x)) for x in vals))

        def job(progress, cancel):
            return studies.run_series(
                prm, name, vals, cancel=cancel,
                progress=lambda d, t: progress(d / t, "Серия %s: %d из %d" % (name, d, t)))

        def done(res):
            self.app.series = res
            self.refresh()
            self.app.status("Серия по %s готова: %d расчётов" % (name, len(vals)))

        self.app.run_task(job, done, "Серия расчётов")

    def refresh(self):
        s = self.app.series
        if s is None:
            self.plot.message("Выберите параметр и диапазон, нажмите «Запустить серию».\n"
                              "При каждом значении считаются все варианты α.")
            return
        key = METRICS[self.metric.get()]
        alphas = s.alphas()
        curves = []
        for i, a in enumerate(alphas):
            x, y = s.curve(key, i + 1)
            curves.append(("α=%.2f" % a, x, y))
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        m = PARAM_META[s.name]
        plotting.draw_curves(ax, curves, "%s, %s" % (m["label"], m["unit"]),
                             self.metric.get(),
                             colors=plotting.THEMES[self.app.mode]["series"])
        ax.set_title("%s в зависимости от %s" % (self.metric.get(), s.name),
                     fontsize=11)
        self.plot.show()
        cols = [s.name] + ["α=%.2f" % a for a in alphas]
        self.table.destroy()
        self.table = Table(self, self.app, cols, height=6)
        self.table.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        rows, bad = [], []
        for val, sm, err in s.rows:
            if sm:
                rows.append(["%.5g" % val] + [
                    ("расх." if r["diverged"] else "%.5g" % r[key]) for r in sm])
                bad.append(any(r["diverged"] for r in sm))
            else:
                rows.append(["%.5g" % val] + ["ошибка: " + (err or "")] +
                            [""] * (len(alphas) - 1))
                bad.append(True)
        self.table.set_rows(rows, bad)


# ======================================================================
class OptimizePage(Page):
    title = "Подбор"

    def __init__(self, master, app):
        super().__init__(master, app)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        left = ctk.CTkFrame(top, fg_color=c("card"), corner_radius=12,
                            border_width=1, border_color=c("line"))
        left.grid(row=0, column=0, sticky="nw")
        caps(left, "Что подбирать (мин / макс)").grid(row=0, column=0,
                                                      columnspan=3, sticky="w",
                                                      padx=10, pady=(8, 4))
        self.sel, self.lo, self.hi = {}, {}, {}
        for r, n in enumerate(studies.OPT_PARAMS, start=1):
            self.sel[n] = tk.BooleanVar(value=n in ("DKR", "DELOK"))
            check(left, n, self.sel[n]).grid(row=r, column=0, sticky="w",
                                             padx=10, pady=1)
            self.lo[n], self.hi[n] = tk.StringVar(), tk.StringVar()
            entry(left, self.lo[n], 70).grid(row=r, column=1, padx=2)
            entry(left, self.hi[n], 70).grid(row=r, column=2, padx=(2, 10))
        right = ctk.CTkFrame(top, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        right.grid_columnconfigure(0, weight=1)
        row = ctk.CTkFrame(right, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        label(row, "α", 12, muted=True).pack(side="left")
        self.alpha = tk.StringVar(value="0.8")
        entry(row, self.alpha, 70).pack(side="left", padx=(4, 12))
        label(row, "макс. расчётов", 12, muted=True).pack(side="left")
        self.maxev = tk.StringVar(value="60")
        entry(row, self.maxev, 60).pack(side="left", padx=4)
        button(row, "Границы ±30%", self._defaults, width=120).pack(side="left",
                                                                   padx=8)
        button(row, "Подобрать", self.run, primary=True, width=130).pack(side="right")
        self.result = label(right, "", 12, anchor="w", justify="left",
                            wraplength=560)
        self.result.grid(row=1, column=0, sticky="ew", pady=8)
        self.table = Table(right, app, ["Параметр", "Было", "Стало"],
                           widths=[200, 100, 100], height=5)
        self.table.grid(row=2, column=0, sticky="ew")
        self.apply_btn = button(right, "Применить найденные значения",
                                self.apply, width=240)
        self.apply_btn.grid(row=3, column=0, sticky="w", pady=8)
        label(right, "Подбор максимизирует Fkomp при заданном α. При α > 1 "
              "Fkomp часто равен 1 во всей области - тогда подбор не "
              "информативен, берите α ≤ 1.", 11, muted=True, wraplength=560,
              justify="left", anchor="w").grid(row=4, column=0, sticky="ew")
        self.plot = Plot(self, app, figsize=(8, 3))
        self.plot.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.grid_rowconfigure(1, weight=1)
        self.after(200, self._defaults)

    def _defaults(self):
        for n in studies.OPT_PARAMS:
            cur = _num(self.app.sidebar.vars[n].get(), 1.0)
            self.lo[n].set("%.4g" % (cur * 0.7))
            self.hi[n].set("%.4g" % (cur * 1.3))

    def run(self):
        try:
            prm = self.app.sidebar.params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        names = [n for n in studies.OPT_PARAMS if self.sel[n].get()]
        if not names:
            messagebox.showinfo("Подбор", "Отметьте хотя бы один параметр.")
            return
        bounds = []
        for n in names:
            lo, hi = _num(self.lo[n].get()), _num(self.hi[n].get())
            if lo is None or hi is None or not lo < hi:
                messagebox.showerror("Подбор", "Неверные границы для %s" % n)
                return
            bounds.append((lo, hi))
        alpha = _num(self.alpha.get(), 0.8)
        maxev = int(_num(self.maxev.get(), 60))

        def job(progress, cancel):
            return studies.optimize(
                prm, names, bounds, alpha, max_evals=maxev, cancel=cancel,
                progress=lambda d, t: progress(min(1.0, d / t),
                                               "Подбор: расчёт %d (лимит %d)" % (d, t)))

        def done(res):
            self.app.opt = res
            self.refresh()
            self.app.status("Подбор завершён: Fkomp %.5f → %.5f"
                            % (res.start_f, res.best_f))

        self.app.run_task(job, done, "Подбор параметров")

    def apply(self):
        o = self.app.opt
        if o is None:
            return
        for n, x in zip(o.names, o.best_x):
            self.app.sidebar.vars[n].set("%.6g" % x)
        self.app.status("Найденные значения подставлены в исходные данные")

    def refresh(self):
        o = self.app.opt
        if o is None:
            self.plot.message("Здесь появится ход подбора")
            return
        self.result.configure(text="α = %.2f: Fkomp было %.5f, стало %.5f "
                              "(%d расчётов)." % (o.alpha, o.start_f, o.best_f,
                                                  len(o.evals)))
        self.table.set_rows([(n, "%.5g" % a, "%.5g" % b)
                             for n, a, b in zip(o.names, o.start_x, o.best_x)])
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        ys = [e[1] for e in o.evals]
        best = np.maximum.accumulate(ys)
        p = self.colors()
        ax.plot(range(1, len(ys) + 1), ys, "o", ms=4, color=p["muted"],
                label="расчёт")
        ax.plot(range(1, len(ys) + 1), best, "-", lw=2, color=p["accent"],
                label="лучшее")
        ax.set_ylim(max(min([y for y in ys if y > -1] or [0]) - 0.01, 0),
                    1.005)
        ax.set_xlabel("номер расчёта")
        ax.set_ylabel("Fkomp")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=9)
        self.plot.show()


# ======================================================================
class _Restricted(pickle.Unpickler):
    def find_class(self, module, name):
        if module.split(".")[0] in ("metan", "numpy", "collections") or \
                (module == "builtins" and name in ("dict", "list", "tuple",
                                                   "set", "frozenset", "slice",
                                                   "complex", "range")):
            return super().find_class(module, name)
        raise pickle.UnpicklingError("Недопустимый тип в файле: %s.%s"
                                     % (module, name))


class ComparePage(Page):
    title = "Сравнение"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.run_a, self.run_b = tk.StringVar(), tk.StringVar()
        self.var_a, self.var_b = tk.StringVar(), tk.StringVar()
        label(tb, "A:", 12, bold=True).pack(side="left")
        self.om_ra = option(tb, ["—"], lambda _v: self._variants(), self.run_a, 210)
        self.om_ra.pack(side="left", padx=4)
        self.om_va = option(tb, ["—"], lambda _v: self.refresh(), self.var_a, 110)
        self.om_va.pack(side="left", padx=(0, 14))
        label(tb, "B:", 12, bold=True).pack(side="left")
        self.om_rb = option(tb, ["—"], lambda _v: self._variants(), self.run_b, 210)
        self.om_rb.pack(side="left", padx=4)
        self.om_vb = option(tb, ["—"], lambda _v: self.refresh(), self.var_b, 110)
        self.om_vb.pack(side="left")
        tb2 = self.toolbar(1)
        self.qty = tk.StringVar(value=VAR_NAMES[NT])
        option(tb2, FIELD_NAMES, lambda _v: self.refresh(), self.qty, 220).pack(
            side="left")
        self.mode = tk.StringVar(value="Рядом")
        segmented(tb2, ["Рядом", "Разность B − A"], lambda _v: self.refresh(),
                  self.mode).pack(side="left", padx=8)
        button(tb2, "Загрузить расчёт…", self.load, width=150).pack(side="right")
        button(tb2, "Сохранить текущий…", self.save, width=160).pack(
            side="right", padx=6)
        self.plot = Plot(self, app)
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.table = Table(self, app, ["Величина", "A", "B", "B − A"],
                           widths=[220, 120, 120, 120], height=6)
        self.table.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.grid_rowconfigure(2, weight=1)

    def update_runs(self):
        names = [n for n, _ in self.app.runs] or ["—"]
        self.om_ra.configure(values=names)
        self.om_rb.configure(values=names)
        if self.run_a.get() not in names:
            self.run_a.set(names[-2] if len(names) > 1 else names[-1])
        if self.run_b.get() not in names:
            self.run_b.set(names[-1])
        self._variants()

    def _res(self, name):
        for n, r in self.app.runs:
            if n == name:
                return r
        return None

    def _variants(self):
        for rv, vv, om in ((self.run_a, self.var_a, self.om_va),
                           (self.run_b, self.var_b, self.om_vb)):
            r = self._res(rv.get())
            vals = (["α=%.2f" % v.values["ALFA"] for v in r.variants] if r
                    else ["—"])
            om.configure(values=vals)
            if vv.get() not in vals:
                vv.set(vals[0])
        self.refresh()

    def _variant(self, rv, vv):
        r = self._res(rv.get())
        if r is None:
            return None
        for v in r.variants:
            if "α=%.2f" % v.values["ALFA"] == vv.get():
                return v
        return None

    def refresh(self):
        a = self._variant(self.run_a, self.var_a)
        b = self._variant(self.run_b, self.var_b)
        if a is None or b is None:
            self.plot.message("Сделайте два расчёта (или загрузите сохранённый) "
                              "и выберите их здесь как A и B.\nМожно сравнивать и "
                              "разные варианты α одного расчёта.")
            return
        k = FIELD_ORDER[FIELD_NAMES.index(self.qty.get())]
        p = self.colors()
        f = self.plot.fig
        f.clear()
        if self.mode.get() == "Рядом":
            vals = []
            for v in (a, b):
                mask = plotting.node_mask(v)
                Z = np.asarray(v.A[1:v.grid["IN"] + 1, 1:v.grid["JN"] + 1, k],
                               float).T[~mask]
                vals.append(Z[np.isfinite(Z)])
            allv = np.concatenate(vals)
            vr = (float(allv.min()), float(allv.max())) if allv.size else None
            for n, (v, t) in enumerate(((a, "A"), (b, "B"))):
                ax = f.add_subplot(2, 1, n + 1)
                m = plotting.draw(ax, v, k, fg=p["fg"], wall_color=p["muted"],
                                  vrange=vr, stream=False)
                ax.set_title("%s: %s, α = %.2f" % (t, self.run_a.get() if n == 0
                                                   else self.run_b.get(),
                                                   v.values["ALFA"]), fontsize=10)
            if m is not None:
                f.colorbar(m, ax=f.axes, label=VAR_NAMES[k], shrink=0.85)
            plotting.style(f, self.app.mode)
            self.plot.restyle()
            self.plot.canvas.draw_idle()
        else:
            ax = f.add_subplot(111)
            x, r, D = analysis.difference(a, b, k)
            plotting.draw_difference(
                ax, x, r, D, label="Δ " + VAR_NAMES[k],
                colorbar_cb=lambda m, lab: f.colorbar(m, ax=ax, label=lab,
                                                      shrink=0.85))
            note = "" if analysis.same_grid(a, b) else \
                " (сетки разные - сравнение на общей сетке)"
            ax.set_title("Разность B − A: %s%s" % (VAR_NAMES[k], note),
                         fontsize=11)
            self.plot.show()
        ea, eb = analysis.exit_summary(a), analysis.exit_summary(b)
        rows = [("Fkomp", a.fkomp, b.fkomp), ("Ms, кг/с", a.values["Ms"],
                                              b.values["Ms"]),
                ("T на выходе, K", ea["T"], eb["T"])]
        rows += [("%s на выходе" % n, ea[n], eb[n]) for n in ("CH4", "O2", "CO2")]
        self.table.set_rows([(n, "%.5g" % x, "%.5g" % y, "%+.3g" % (y - x))
                             for n, x, y in rows])

    def save(self):
        if self.app.results is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".metan",
                                            filetypes=[("Расчёт Metan", "*.metan")])
        if not path:
            return
        import dataclasses
        res = dataclasses.replace(
            self.app.results,
            variants=[dataclasses.replace(v, snapshots=[])
                      for v in self.app.results.variants])
        with open(path, "wb") as fh:
            pickle.dump(res, fh)
        self.app.status("Расчёт сохранён: " + path)

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("Расчёт Metan", "*.metan")])
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                res = _Restricted(fh).load()
        except Exception as e:
            messagebox.showerror("Ошибка", "Не удалось прочитать файл:\n%s" % e)
            return
        self.app.add_run(res, os.path.basename(path))


# ======================================================================
class GridCheckPage(Page):
    title = "Сетка ×2"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        label(tb, "Каждый интервал сетки делится на", 12, muted=True).pack(side="left")
        self.factor = tk.StringVar(value="2")
        option(tb, ["2", "3"], None, self.factor, 60).pack(side="left", padx=6)
        label(tb, "итераций ×", 12, muted=True).pack(side="left", padx=(10, 0))
        self.itf = tk.StringVar(value="3")
        entry(tb, self.itf, 50).pack(side="left", padx=6)
        button(tb, "Проверить", self.run, primary=True, width=130).pack(side="right")
        self.verdict = label(self, "Сравнивает результаты на текущей и более "
                             "мелкой сетке той же камеры: если отличия малы, "
                             "результат не зависит от сетки.", 12, anchor="w",
                             justify="left", wraplength=900)
        self.verdict.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.plot = Plot(self, app, figsize=(8, 3.5))
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.table = Table(self, app, ["α", "Величина", "Базовая", "Мелкая",
                                       "Отличие, %"],
                           widths=[60, 160, 110, 110, 110], height=7)
        self.table.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.grid_rowconfigure(2, weight=1)

    def run(self):
        try:
            prm = self.app.sidebar.params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        fac, itf = int(self.factor.get()), int(_num(self.itf.get(), 3))

        def job(progress, cancel):
            state = [0.0, 0.0]

            def prog(idx, nvar, nvarm, niter, nmax):
                state[idx] = ((nvar - 1) + niter / nmax) / nvarm
                progress(min(state), "Базовая сетка %.0f%%, мелкая %.0f%%"
                         % (state[0] * 100, state[1] * 100))
            return studies.grid_check(prm, fac, itf, progress=prog, cancel=cancel)

        def done(res):
            self.app.gridcheck = res
            self.refresh()

        self.app.run_task(job, done, "Проверка на мелкой сетке")

    def refresh(self):
        g = self.app.gridcheck
        if g is None:
            self.plot.message("Нажмите «Проверить»")
            return
        rows = g.table()
        self.table.set_rows(
            [("%.2f" % a, n, "%.5g" % x, "%.5g" % y,
              ("—" if rel != rel else "%+.2f" % rel) + (" расх." if bad else ""))
             for a, n, x, y, rel, bad in rows],
            bad=[r[5] for r in rows])
        fk = [abs(r[4]) for r in rows if r[1] == "Fkomp" and r[4] == r[4] and not r[5]]
        nbad = sum(1 for a, b in zip(g.base.variants, g.fine.variants)
                   if a.diverged or b.diverged)
        gb, gf = g.base_params, g.fine_params
        txt = "Базовая сетка %d×%d, мелкая %d×%d. " % (gb.IN, gb.JN, gf.IN, gf.JN)
        if fk:
            txt += "Наибольшее отличие Fkomp: %.2f %%. " % max(fk)
            txt += ("Результат практически не зависит от сетки."
                    if max(fk) < 1 else
                    "Отличие заметное - результат зависит от сетки.")
        if nbad:
            txt += " Варианты с расходимостью: %d (на мелкой сетке схема может " \
                   "требовать больше итераций или меньшей релаксации)." % nbad
        self.verdict.configure(text=txt)
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        cols = plotting.THEMES[self.app.mode]["series"]
        for n, (a, b) in enumerate(zip(g.base.variants, g.fine.variants)):
            for v, ls, t in ((a, "-", "база"), (b, "--", "мелкая")):
                r, T = analysis.radial_profile(v, NT, v.grid["IN"])
                ax.plot(r * 1000, T, ls, color=cols[n % len(cols)], lw=1.6,
                        label="α=%.2f, %s" % (v.values["ALFA"], t))
        ax.set_xlabel("r, мм")
        ax.set_ylabel("T на выходе, K")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, ncol=2)
        ax.set_title("Профиль температуры на выходе: базовая и мелкая сетка",
                     fontsize=11)
        self.plot.show()


# ======================================================================
class ProtocolPage(Page):
    title = "Файлы .dat"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.which = tk.StringVar(value="shi10.dat (протокол)")
        segmented(tb, ["shi10.dat (протокол)", "shi20.dat (поля)"],
                  lambda _v: self.refresh(), self.which).pack(side="left")
        button(tb, "Открыть папку", lambda: open_folder(self.app.outdir.get()),
               width=130).pack(side="right")
        button(tb, "Сохранить копию…", self.save_copy, width=150).pack(
            side="right", padx=6)
        self.path_lbl = label(self, "", 11, muted=True, anchor="w")
        self.path_lbl.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.text = ctk.CTkTextbox(self, wrap="none", fg_color=c("card"),
                                   text_color=c("fg"), border_width=1,
                                   border_color=c("line"), corner_radius=12,
                                   font=ctk.CTkFont(family=__import__(
                                       "metan.app.theme", fromlist=["MONO"]).MONO,
                                       size=12))
        self.text.grid(row=2, column=0, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

    def _lines(self):
        r = self.app.results
        if r is None:
            return None, None
        if self.which.get().startswith("shi10"):
            return r.text10, r.params.out10
        return r.text20, r.params.out20

    def refresh(self):
        lines, name = self._lines()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if lines is None:
            self.text.insert("1.0", "После расчёта здесь будут файлы shi10.dat и "
                                    "shi20.dat - те же, что писала программа на "
                                    "Фортране. Они же сохраняются в папку "
                                    "результатов.")
            self.path_lbl.configure(text="")
        else:
            self.text.insert("1.0", "\n".join(lines))
            self.path_lbl.configure(text="Файл: " + os.path.abspath(
                os.path.join(self.app.outdir.get(), name)))
        self.text.configure(state="disabled")

    def save_copy(self):
        lines, name = self._lines()
        if lines is None:
            return
        path = filedialog.asksaveasfilename(initialfile=name,
                                            defaultextension=".dat")
        if path:
            with open(path, "w", newline="\n") as fh:
                fh.write("".join(s + "\n" for s in lines))
