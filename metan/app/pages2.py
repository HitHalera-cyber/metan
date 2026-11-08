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
from .theme import c, pal
from .widgets import (Flow, Plot, Table, button, caps, check, entry, label, option,
                      segmented)

METRICS = {"φк": "fkomp", "Tвых, K": "exit_T", "ṁ, кг/с": "Ms",
           "gCH4 вых": "exit_CH4", "gO2 вых": "exit_O2",
           "gCO2 вых": "exit_CO2"}


def _short(name):
    """Обозначение параметра (DKAR -> dпк)."""
    return PARAM_META[name].get("sym") or name


def _olabel(name):
    m = PARAM_META[name]
    text = m["label"][0].lower() + m["label"][1:]
    return "%s — %s" % (_short(name), text)


def _plabel(name):
    m = PARAM_META[name]
    return "%s — %s" % (_short(name), m["label"])


def _axis(name):
    m = PARAM_META[name]
    return "%s %s%s" % (m["label"], _short(name),
                        ", " + m["unit"] if m["unit"] else "")


def open_folder(path, file=False):
    path = os.path.abspath(path)
    if not (os.path.isfile(path) if file else os.path.isdir(path)):
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
        self.metric = tk.StringVar(value="φк")
        segmented(tb2, list(METRICS), lambda _v: self.refresh(),
                  self.metric).pack(side="left", padx=8)
        # график и таблица - в окне с перетаскиваемой границей
        self.pane = tk.PanedWindow(self, orient="vertical", sashwidth=10,
                                   bd=0, sashrelief="flat", showhandle=False,
                                   sashcursor="sb_v_double_arrow",
                                   bg=pal(app.mode)["bg"])
        self.pane.grid(row=2, column=0, sticky="nsew")
        self.plot = Plot(self.pane, app)
        self.table = Table(self.pane, app, ["значение"], height=3,
                           copy_button=True)
        self.table.set_title("Таблица результатов (границу над ней можно "
                             "перетаскивать)")
        self.pane.add(self.plot, minsize=160, stretch="always")
        self.pane.add(self.table, minsize=150, stretch="never")
        self.grid_rowconfigure(2, weight=1)
        self.after(200, self._init_sash)
        self._defaults()

    def _init_sash(self):
        h, w = self.pane.winfo_height(), self.pane.winfo_width()
        if h <= 1:
            self.after(300, self._init_sash)
            return
        self.pane.bind("<Configure>", self._pane_resized, add="+")
        self._pane_resized()

    def _pane_resized(self, _e=None):
        """Низкое окно - таблица справа от графика, иначе - под ним."""
        h, w = self.pane.winfo_height(), self.pane.winfo_width()
        orient = "horizontal" if h < 430 and w > 760 else "vertical"
        if orient == str(self.pane.cget("orient")) and _e is not None:
            return
        self.pane.configure(orient=orient, sashcursor="sb_h_double_arrow"
                            if orient == "horizontal" else "sb_v_double_arrow")
        self.update_idletasks()
        if orient == "horizontal":
            self.pane.sash_place(0, max(300, int(w * 0.6)), 0)
        else:
            self.pane.sash_place(0, 0, max(160, int(h * 0.62)))

    def _pname(self):
        lab = self.pname.get()
        for n in studies.SERIES_PARAMS:
            if _plabel(n) == lab:
                return n
        return "DKR"

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
        self.pane.configure(bg=pal(self.app.mode)["bg"])
        s = self.app.series
        if s is None:
            self.plot.message("Выберите параметр и диапазон, нажмите «Запустить серию».\n"
                              "Если отмечено «Несколько значений α», при каждом значении\n"
                              "считаются все α - на графике будет семейство кривых.")
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
        plotting.draw_curves(ax, curves, _axis(s.name),
                             self.metric.get(),
                             colors=plotting.THEMES[self.app.mode]["series"])
        ax.set_title("%s в зависимости от %s" % (self.metric.get(), _short(s.name)),
                     fontsize=11)
        self.plot.show()
        m = PARAM_META[s.name]
        cols = ["%s, %s" % (_short(s.name), m["unit"]) if m["unit"] else _short(s.name)] + \
            ["α = %.2f" % a for a in alphas]
        self.table.set_columns(cols)
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
        self.table.set_title("%s от %s: %d точек%s" % (
            self.metric.get(), _short(s.name), len(s.rows),
            " · красным - разошедшиеся" if any(bad) else ""))
        self.table.set_rows(rows, bad)


# ======================================================================
class OptimizePage(Page):
    title = "Подбор"

    def __init__(self, master, app):
        super().__init__(master, app)
        # верхняя строка: α, лимит, кнопки (переносится на узком экране)
        tb = self.toolbar(0)
        label(tb, "α", 12, muted=True).pack(side="left")
        self.alpha = tk.StringVar(
            value=app.sidebar.vars["ALFA"].get() or "1.0")
        entry(tb, self.alpha, 70).pack(side="left", padx=(4, 14))
        label(tb, "макс. расчётов", 12, muted=True).pack(side="left")
        self.maxev = tk.StringVar(value="60")
        entry(tb, self.maxev, 60).pack(side="left", padx=(4, 14))
        button(tb, "Границы ±30%", self._defaults, width=120).pack(side="left")
        button(tb, "Подобрать", self.run, primary=True, width=130).pack(
            side="right")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew")
        self._top = top
        left = ctk.CTkFrame(top, fg_color=c("card"), corner_radius=12,
                            border_width=1, border_color=c("line"))
        self._left = left
        caps(left, "Что подбирать (мин / макс, мм)").grid(row=0, column=0,
                                                      columnspan=3, sticky="w",
                                                      padx=10, pady=(8, 4))
        self.sel, self.lo, self.hi = {}, {}, {}
        for r, n in enumerate(studies.OPT_PARAMS, start=1):
            self.sel[n] = tk.BooleanVar(value=n in ("DKR", "DELOK"))
            check(left, _olabel(n), self.sel[n]).grid(row=r, column=0,
                                                      sticky="w", padx=10,
                                                      pady=1)
            self.lo[n], self.hi[n] = tk.StringVar(), tk.StringVar()
            entry(left, self.lo[n], 70).grid(row=r, column=1, padx=2)
            entry(left, self.hi[n], 70).grid(row=r, column=2, padx=(2, 10))
        right = ctk.CTkFrame(top, fg_color="transparent")
        self._right = right
        right.grid_columnconfigure(0, weight=1)
        self.result = label(right, "Отметьте параметры, задайте границы и "
                            "нажмите «Подобрать». Цель - наибольший φк.", 12,
                            anchor="w", justify="left", wraplength=300)
        self.result.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.table = Table(right, app, ["Параметр", "Было", "Стало"], height=3)
        self.table.grid(row=1, column=0, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        self.apply_btn = button(right, "Применить найденные значения",
                                self.apply, width=240)
        self.apply_btn.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self._side = None
        top.bind("<Configure>", self._arrange, add="+")
        self._wrap = None
        right.bind("<Configure>", self._rewrap, add="+")
        self._arrange()
        self.plot = Plot(self, app, figsize=(8, 3))
        self.plot.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self.grid_rowconfigure(2, weight=1)
        self.after(200, self._defaults)

    def _rewrap(self, e):
        w = max(200, e.width - 10)
        if self._wrap is None or abs(w - self._wrap) > 20:
            self._wrap = w
            self.result.configure(wraplength=w)

    def _arrange(self, _e=None):
        """Таблица справа от списка параметров, а на узком экране - под ним."""
        w = self._top.winfo_width()
        side = w <= 1 or w >= self._left.winfo_reqwidth() + 340
        if side == self._side:
            return
        self._side = side
        self._left.grid_forget()
        self._right.grid_forget()
        self._top.grid_columnconfigure(0, weight=0)
        self._top.grid_columnconfigure(1, weight=1 if side else 0)
        self._left.grid(row=0, column=0, sticky="nw")
        self._right.grid_rowconfigure(1, weight=1 if side else 0)
        if side:
            self._right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        else:
            self._top.grid_columnconfigure(0, weight=1)
            self._right.grid(row=1, column=0, sticky="ew", pady=(8, 0))

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
            self.app.status("Подбор завершён: φк %.5f → %.5f"
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
        self.result.configure(text="α = %.2f: φк было %.5f, стало %.5f "
                              "(%d расчётов)." % (o.alpha, o.start_f, o.best_f,
                                                  len(o.evals)))
        self.table.set_rows([(_short(n), "%.5g" % a, "%.5g" % b)
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
        ax.set_ylabel("φк")
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
                           widths=[220, 120, 120, 120], height=3)
        self.table.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        self.grid_rowconfigure(2, weight=3, minsize=220)
        self.grid_rowconfigure(3, weight=1)

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
        rows = [("φк", a.fkomp, b.fkomp),
                ("φβ", a.extra.get("FIbeta", np.nan), b.extra.get("FIbeta", np.nan)),
                ("ṁ, кг/с", a.values["Ms"], b.values["Ms"]),
                ("Tвых, K", ea["T"], eb["T"])]
        rows += [("g%s вых" % n, ea[n], eb[n]) for n in ("CH4", "O2", "CO2")]
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

    GOOD_GCI = 2.0       # %, ниже - сгущать дальше нет смысла

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        label(tb, "Сеток", 12, muted=True).pack(side="left")
        self.levels = tk.StringVar(value="3 (индекс GCI)")
        option(tb, ["2", "3 (индекс GCI)"], None, self.levels, 150).pack(
            side="left", padx=(6, 14))
        label(tb, "каждый интервал делится на", 12, muted=True).pack(side="left")
        self.factor = tk.StringVar(value="2")
        option(tb, ["2", "3"], None, self.factor, 60).pack(side="left", padx=6)
        button(tb, "Проверить", self.run, primary=True, width=130).pack(side="right")
        self.verdict = label(
            self, "Тот же расчёт на всё более мелких сетках. По трём сеткам "
            "считается индекс сеточной сходимости GCI - насколько ещё может "
            "измениться результат при сгущении; GCI < 2 % - сгущать дальше нет "
            "смысла. Предел итераций на каждой сетке берётся по Nуст.", 12,
            anchor="w", justify="left", wraplength=900)
        self.verdict.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        # перенос строк - по ширине страницы (не самой подписи: иначе
        # изменение переноса снова меняет её размер - бесконечный цикл)
        self._wrap = None
        self.bind("<Configure>", self._rewrap, add="+")
        self.plot = Plot(self, app, figsize=(8, 3.5))
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.table = Table(self, app, ["α", "Величина", "Сетка 1", "Сетка 2"],
                           height=3, copy_button=True)
        self.table.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        self.grid_rowconfigure(2, weight=3, minsize=200)
        self.grid_rowconfigure(3, weight=1)

    def run(self):
        try:
            prm = self.app.sidebar.params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        fac = int(self.factor.get())
        lev = 3 if self.levels.get().startswith("3") else 2

        def job(progress, cancel):
            state = [0.0] * lev

            def prog(idx, nvar, nvarm, niter, nmax):
                state[idx] = ((nvar - 1) + niter / nmax) / nvarm
                progress(min(state), "Сетки: " + ", ".join(
                    "%.0f%%" % (x * 100) for x in state))
            return studies.grid_check(prm, fac, progress=prog, cancel=cancel,
                                      levels=lev)

        def done(res):
            self.app.gridcheck = res
            self.refresh()

        self.app.run_task(job, done, "Проверка на мелких сетках")

    def _rewrap(self, e):
        w = max(300, e.width - 20)
        if self._wrap is None or abs(w - self._wrap) > 20:
            self._wrap = w
            self.verdict.configure(wraplength=w)

    @staticmethod
    def _grid_name(p):
        return "%d×%d" % (p.IN, p.JN)

    def refresh(self):
        g = self.app.gridcheck
        if g is None:
            self.plot.message("Нажмите «Проверить»")
            return
        ps = [g.base_params, g.fine_params] + \
            ([g.finer_params] if g.finer is not None else [])
        names = [self._grid_name(p) for p in ps]
        txt = "Сетки: %s. " % " → ".join(names)
        rows_g = g.gci()
        if rows_g:
            self.table.set_columns(["α", "Величина"] + names +
                                   ["Порядок p", "Предел (h→0)", "GCI, %",
                                    "Вывод"])
            kinds = {"monotone": "сходится", "oscillating": "колеблется",
                     "diverging": "сетки грубые", "converged": "не зависит"}
            rows, bad = [], []
            for r in rows_g:
                fmt = "%.5f" if r["name"] == "φк" else "%.1f"
                rows.append(["%.2f" % r["alpha"], r["name"], fmt % r["f3"],
                             fmt % r["f2"], fmt % r["f1"],
                             "—" if r["p"] != r["p"] else "%.2f" % r["p"],
                             "—" if r["ext"] != r["ext"] else fmt % r["ext"],
                             "%.2f" % r["gci"], kinds[r["kind"]]])
                bad.append(r["bad"])
            self.table.set_rows(rows, bad)
            fk = [r for r in rows_g if r["name"] == "φк"]
            worst = max(fk, key=lambda r: r["gci"])
            if any(r["kind"] == "diverging" for r in fk):
                txt += ("Разности φк между сетками не убывают (%.4f → %.4f): "
                        "эти сетки ещё слишком грубые, результат заметно "
                        "зависит от сетки. Сгущать имеет смысл - повторите "
                        "проверку, начав с более подробной сетки."
                        % (abs(worst["f2"] - worst["f3"]),
                           abs(worst["f1"] - worst["f2"])))
            elif worst["gci"] < self.GOOD_GCI:
                txt += ("GCI для φк = %.2f %% < %g %%: сгущать дальше нет "
                        "смысла, результат на мелкой сетке отличается от "
                        "предела не больше чем на %.2f %%."
                        % (worst["gci"], self.GOOD_GCI, worst["gci"]))
            else:
                txt += ("GCI для φк = %.2f %%: при дальнейшем сгущении φк может "
                        "измениться примерно на столько. Сгущать имеет смысл; "
                        "оценка на бесконечно мелкой сетке φк ≈ %s."
                        % (worst["gci"], "—" if worst["ext"] != worst["ext"]
                           else "%.4f" % worst["ext"]))
        else:
            rows = g.table()
            self.table.set_columns(["α", "Величина"] + names + ["Отличие, %"])
            self.table.set_rows(
                [("%.2f" % a, n, "%.5g" % x, "%.5g" % y,
                  ("—" if rel != rel else "%+.2f" % rel) + (" расх." if b else ""))
                 for a, n, x, y, rel, b in rows], bad=[r[5] for r in rows])
            fk = [abs(r[4]) for r in rows if r[1] == "φк" and r[4] == r[4]
                  and not r[5]]
            if fk:
                txt += "Наибольшее отличие φк: %.2f %%. " % max(fk)
                txt += ("Результат практически не зависит от сетки."
                        if max(fk) < 1 else
                        "Отличие заметное - результат зависит от сетки; для "
                        "оценки, нужно ли сгущать, выберите 3 сетки (GCI).")
        res_all = [g.base, g.fine] + ([g.finer] if g.finer is not None else [])
        unsettled = sum(v.settled is False or v.diverged
                        for r in res_all for v in r.variants)
        if unsettled:
            txt += (" Внимание: на %d сетке(ах) решение не установилось или "
                    "разошлось - такие строки красные." % unsettled)
        self.verdict.configure(text=txt)
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        cols = plotting.THEMES[self.app.mode]["series"]
        styles = ("-", "--", ":")
        for k, (res, nm) in enumerate(zip(res_all, names)):
            for n, v in enumerate(res.variants):
                r, T = analysis.radial_profile(v, NT, v.grid["IN"])
                ax.plot(r * 1000, T, styles[k], color=cols[n % len(cols)],
                        lw=1.6, label="α=%.2f, %s" % (v.values["ALFA"], nm))
        ax.set_xlabel("r, мм")
        ax.set_ylabel("T на выходе, K")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, ncol=2)
        ax.set_title("Профиль температуры на выходе на разных сетках",
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
