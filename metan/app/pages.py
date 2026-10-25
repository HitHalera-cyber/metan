"""Страницы рабочей области."""

import dataclasses
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
import numpy as np

from .. import analysis, plotting
from ..kernels import NF, NT
from ..params import Params
from ..solver import VAR_NAMES
from .theme import c, pal
from .widgets import Flow, Plot, Table, button, check, label, option, segmented

FIELD_ORDER = [13, 2, 1, 3, 4, 5, 6, 7, 8, 9, 12, 14, 15, 16, 11, 10]
FIELD_NAMES = [VAR_NAMES[k] for k in FIELD_ORDER]
PARAM_META = {n: m for n, _, m in Params.field_info()}


def _num(s, default=None):
    try:
        return float(str(s).replace(",", "."))
    except ValueError:
        return default


class Page(ctk.CTkFrame):
    title = ""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)

    def toolbar(self, row=0):
        fr = Flow(self)
        fr.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        return fr

    def refresh(self):
        pass

    def restyle(self):
        for w in self.__dict__.values():
            if isinstance(w, (Plot, Table)):
                w.restyle()
        self.refresh()

    def colors(self):
        return pal(self.app.mode)


# ======================================================================
class FieldsPage(Page):
    title = "Поля"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.qty = tk.StringVar(value=FIELD_NAMES[0])
        option(tb, FIELD_NAMES, lambda _v: self.refresh(), self.qty,
               width=230).pack(side="left")
        self.style_var = tk.StringVar(value="Заливка")
        segmented(tb, ["Заливка", "Изолинии", "Оба"], lambda _v: self.refresh(),
                  self.style_var).pack(side="left", padx=8)
        self.mirror = tk.BooleanVar(value=True)
        self.stream = tk.BooleanVar(value=True)
        self.labels = tk.BooleanVar(value=False)
        self.meters = tk.BooleanVar(value=False)
        tb2 = self.toolbar(1)
        for t, v in (("Зеркально", self.mirror), ("Линии тока", self.stream),
                     ("Подписи", self.labels), ("Оси в метрах", self.meters)):
            check(tb2, t, v, self.refresh).pack(side="left", padx=(0, 12))
        button(tb2, "CSV", self.export_csv, width=60).pack(side="right")
        button(tb2, "Рисунок…", self.save_fig, width=90).pack(
            side="right", padx=6)
        button(tb2, "Как в методичке", self.book, width=140).pack(side="right")
        self.plot = Plot(self, app)
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

    def book(self):
        self.qty.set(VAR_NAMES[NF])
        self.style_var.set("Изолинии")
        self.mirror.set(False)
        self.labels.set(True)
        self.meters.set(True)
        self.stream.set(False)
        self.refresh()

    def refresh(self):
        v = self.app.variant
        if v is None:
            self.plot.message("Нажмите «Рассчитать»")
            return
        k = FIELD_ORDER[FIELD_NAMES.index(self.qty.get())]
        st = {"Заливка": "fill", "Изолинии": "lines", "Оба": "both"}[
            self.style_var.get()]
        p = self.colors()
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        try:
            plotting.draw(ax, v, k, style=st, mirror=self.mirror.get(),
                          stream=self.stream.get(), labels=self.labels.get(),
                          units="m" if self.meters.get() else "mm",
                          fg=p["fg"], wall_color=p["muted"], label=VAR_NAMES[k],
                          colorbar_cb=lambda m, lab: f.colorbar(
                              m, ax=ax, label=lab, shrink=0.85))
        except Exception as e:
            ax.text(0.5, 0.5, "Не удалось построить: %s" % e, ha="center",
                    transform=ax.transAxes)
        ax.set_title("%s — α = %.2f%s" % (VAR_NAMES[k], v.values["ALFA"],
                                           "  (РАСХОДИМОСТЬ)" if v.diverged else ""),
                     fontsize=11)
        self.plot.show()

    def save_fig(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"),
                                                ("SVG", "*.svg")])
        if path:
            self.plot.fig.savefig(path, dpi=200,
                                  facecolor=self.plot.fig.get_facecolor())

    def export_csv(self):
        v = self.app.variant
        if v is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="variant%d.csv" % v.NVAR,
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        keys = sorted(VAR_NAMES)
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write("I;J;X1, м;X2, м;" + ";".join(VAR_NAMES[k] for k in keys) + "\n")
            for j in range(1, v.grid["JN"] + 1):
                for i in range(1, v.grid["IN"] + 1):
                    vals = [v.X1[i], v.X2[j]] + [v.A[i, j, k] for k in keys]
                    fh.write("%d;%d;" % (i, j) + ";".join("%.6e" % x for x in vals)
                             + "\n")
        self.app.status("Поля сохранены: " + path)


# ======================================================================
class ProfilesPage(Page):
    title = "Профили"
    COMPOSITION = "Состав (все компоненты)"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.mode = tk.StringVar(value="По радиусу")
        segmented(tb, ["По радиусу", "Вдоль оси"], lambda _v: self._mode(),
                  self.mode).pack(side="left")
        self.qty = tk.StringVar(value=VAR_NAMES[NT])
        option(tb, [VAR_NAMES[NT], self.COMPOSITION] +
               [n for n in FIELD_NAMES if n != VAR_NAMES[NT]],
               lambda _v: self.refresh(), self.qty, width=230).pack(
            side="left", padx=8)
        self.allv = tk.BooleanVar(value=True)
        check(tb, "Все варианты", self.allv, self.refresh).pack(side="left")
        tb2 = self.toolbar(1)
        for t, cmd in (("T(r) на выходе", self.p_exit_t),
                       ("T(x) по оси", self.p_axis_t),
                       ("Состав на выходе", self.p_exit_comp)):
            button(tb2, t, cmd, width=140).pack(side="left", padx=(0, 6))
        self.pos_lbl = label(tb2, "", 12, mono=True)
        self.pos_lbl.pack(side="right")
        self.slider = ctk.CTkSlider(tb2, from_=1, to=46, number_of_steps=45,
                                    command=lambda _v: self.refresh(),
                                    button_color=c("accent"),
                                    button_hover_color=c("accent_hover"),
                                    progress_color=c("accent"),
                                    fg_color=c("line"), width=260)
        self.slider.pack(side="right", padx=8)
        self.plot = Plot(self, app)
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)
        self._mode()

    def _mode(self):
        v = self.app.variant
        if v is not None:
            n = v.grid["IN"] if self.mode.get() == "По радиусу" else v.grid["JN"]
            cur = int(self.slider.get())
            self.slider.configure(to=n, number_of_steps=max(1, n - 1))
            self.slider.set(min(cur, n) if self.mode.get() == "Вдоль оси" else
                            (cur if cur > 1 else n))
        self.refresh()

    def p_exit_t(self):
        self.mode.set("По радиусу")
        self.qty.set(VAR_NAMES[NT])
        self._mode()
        if self.app.variant is not None:
            self.slider.set(self.app.variant.grid["IN"])
        self.refresh()

    def p_axis_t(self):
        self.mode.set("Вдоль оси")
        self.qty.set(VAR_NAMES[NT])
        self._mode()
        self.slider.set(1)
        self.refresh()

    def p_exit_comp(self):
        self.p_exit_t()
        self.qty.set(self.COMPOSITION)
        self.allv.set(False)
        self.refresh()

    def refresh(self):
        v = self.app.variant
        if v is None:
            self.plot.message("Нет результатов")
            return
        radial = self.mode.get() == "По радиусу"
        n = v.grid["IN"] if radial else v.grid["JN"]
        idx = max(1, min(n, int(round(self.slider.get()))))
        if radial:
            self.pos_lbl.configure(text="сечение i=%d, x = %.2f мм"
                                   % (idx, v.X1[idx] * 1000))
        else:
            self.pos_lbl.configure(text="узел j=%d, r = %.2f мм"
                                   % (idx, v.X2[idx] * 1000))
        p = self.colors()
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        variants = (self.app.results.variants if self.allv.get()
                    and self.app.results else [v])
        comp = self.qty.get() == self.COMPOSITION
        series = []
        if comp:
            for n_, (k, name) in enumerate(analysis.SPECIES):
                xs, ys = (analysis.radial_profile(v, k, idx) if radial
                          else analysis.axial_profile(v, k, idx))
                series.append((name, xs * 1000, ys))
            ylabel = "массовая доля"
        else:
            k = FIELD_ORDER[FIELD_NAMES.index(self.qty.get())]
            for vv in variants:
                xs, ys = (analysis.radial_profile(vv, k, min(idx, vv.grid["IN"]))
                          if radial else
                          analysis.axial_profile(vv, k, min(idx, vv.grid["JN"])))
                series.append(("α=%.2f" % vv.values["ALFA"], xs * 1000, ys))
            ylabel = VAR_NAMES[k]
        for n_, (name, xs, ys) in enumerate(series):
            ax.plot(xs, ys, "o-", ms=3, lw=1.6, label=name,
                    color=p["accent"] if len(series) == 1 else
                    plotting.THEMES[self.app.mode]["series"][n_ % 7])
        ax.set_xlabel("r, мм" if radial else "x, мм")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        if len(series) > 1:
            ax.legend(fontsize=9)
        ax.set_title(("Профиль по радиусу, x = %.2f мм" % (v.X1[idx] * 1000))
                     if radial else ("Профиль вдоль оси, r = %.2f мм"
                                     % (v.X2[idx] * 1000)), fontsize=11)
        self.plot.show()


# ======================================================================
class ConvergencePage(Page):
    title = "Сходимость"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.key_vars = {}
        for k, t, on in (("psi", "ψ", True), ("T", "T", True), ("CH4", "CH4", False),
                         ("omega", "ω", False)):
            self.key_vars[k] = tk.BooleanVar(value=on)
            check(tb, t, self.key_vars[k], self.refresh).pack(side="left", padx=(0, 10))
        self.allv = tk.BooleanVar(value=False)
        check(tb, "Все варианты", self.allv, self.refresh).pack(side="left", padx=10)
        self.verdict = label(self, "", 12, anchor="w", justify="left",
                             wraplength=900)
        self.verdict.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.plot = Plot(self, app)
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

    def refresh(self):
        v = self.app.variant
        if v is None or not v.history:
            self.plot.message("Нет данных о сходимости")
            self.verdict.configure(text="")
            return
        variants = self.app.results.variants if self.allv.get() else [v]
        keys = [k for k, var in self.key_vars.items() if var.get()] or ["psi"]
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        plotting.draw_convergence(ax, variants, keys=keys,
                                  colors=plotting.THEMES[self.app.mode]["series"])
        ax.legend(fontsize=8, ncol=2)
        ax.set_title("Изменение величин за одну итерацию", fontsize=11)
        self.plot.show()
        lines = []
        for vv in variants:
            h = vv.history
            tail = slice(-200, None)
            last = {k: float(np.nanmax(np.asarray(h[k])[tail])) for k in
                    ("psi", "T", "CH4")}
            ok = last["psi"] < 5e-3 and last["T"] < 1e-2 and not vv.diverged
            lines.append(
                "α=%.2f: за последние 200 итераций ψ меняется до %.1e, T до %.1e, "
                "CH4 до %.1e  →  %s" % (
                    vv.values["ALFA"], last["psi"], last["T"], last["CH4"],
                    "РАСХОДИМОСТЬ" if vv.diverged else
                    ("установился (изменения малы)" if ok
                     else "не установился (идут заметные колебания)")))
        self.verdict.configure(
            text="\n".join(lines) +
            "\nКритерий: ψ < 5·10⁻³ и T < 10⁻² (отн. изменение за итерацию).")


# ======================================================================
class AnimationPage(Page):
    title = "Анимация"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.qty = tk.StringVar(value=VAR_NAMES[NT])
        option(tb, FIELD_NAMES, lambda _v: self._calc_range(), self.qty,
               width=230).pack(side="left")
        self.play_btn = button(tb, "▶  Пуск", self.toggle, width=100)
        self.play_btn.pack(side="left", padx=8)
        self.fps = tk.StringVar(value="8 кадр/с")
        option(tb, ["4 кадр/с", "8 кадр/с", "15 кадр/с"], None, self.fps,
               width=110).pack(side="left")
        button(tb, "Сохранить GIF", self.save_gif, width=130).pack(side="right")
        tb2 = self.toolbar(1)
        self.slider = ctk.CTkSlider(tb2, from_=0, to=1, number_of_steps=1,
                                    command=lambda _v: self.refresh(),
                                    button_color=c("accent"),
                                    button_hover_color=c("accent_hover"),
                                    progress_color=c("accent"), fg_color=c("line"))
        self.slider.pack(side="left", fill="x", expand=True)
        self.frame_lbl = label(tb2, "", 12, mono=True, width=180)
        self.frame_lbl.pack(side="right")
        self.plot = Plot(self, app, toolbar=False)
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)
        self.playing = False
        self.vrange = None
        self._last_v = None

    def _calc_range(self):
        v = self.app.variant
        self.vrange = None
        if v is not None and v.snapshots:
            k = FIELD_ORDER[FIELD_NAMES.index(self.qty.get())]
            mask = plotting.node_mask(v)
            vals = []
            for _, A in v.snapshots:
                Z = np.asarray(A[1:v.grid["IN"] + 1, 1:v.grid["JN"] + 1, k],
                               float).T[~mask]
                vals.append(Z[np.isfinite(Z)])
            allv = np.concatenate(vals) if vals else np.array([])
            if allv.size:
                lo, hi = np.percentile(allv, [0.5, 99.5])
                self.vrange = (float(lo), float(hi)) if hi > lo else None
        self.refresh()

    def refresh(self):
        v = self.app.variant
        if v is None or not v.snapshots:
            self.plot.message("Нет кадров. Задайте «Кадр анимации каждые N "
                              "итераций» (слева, раздел «Расчёт») и пересчитайте.")
            self.frame_lbl.configure(text="")
            return
        if self._last_v is not v:
            self._last_v = v
            n = len(v.snapshots)
            self.slider.configure(to=n - 1, number_of_steps=max(1, n - 1))
            self.slider.set(n - 1)
            self._calc_range()
            return
        n = int(round(self.slider.get()))
        n = max(0, min(n, len(v.snapshots) - 1))
        it, A = v.snapshots[n]
        self.frame_lbl.configure(text="итерация %d / %d" % (it, v.NITER))
        k = FIELD_ORDER[FIELD_NAMES.index(self.qty.get())]
        vv = dataclasses.replace(v, A=A.astype(float))
        p = self.colors()
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        plotting.draw(ax, vv, k, fg=p["fg"], wall_color=p["muted"],
                      vrange=self.vrange, label=VAR_NAMES[k],
                      colorbar_cb=lambda m, lab: f.colorbar(m, ax=ax, label=lab,
                                                            shrink=0.85))
        ax.set_title("%s, α = %.2f — итерация %d" % (VAR_NAMES[k],
                                                     v.values["ALFA"], it),
                     fontsize=11)
        self.plot.show()

    def toggle(self):
        self.playing = not self.playing
        self.play_btn.configure(text="❚❚  Пауза" if self.playing else "▶  Пуск")
        if self.playing:
            self._tick()

    def _tick(self):
        v = self.app.variant
        if not self.playing or v is None or not v.snapshots:
            self.playing = False
            self.play_btn.configure(text="▶  Пуск")
            return
        n = int(round(self.slider.get())) + 1
        if n >= len(v.snapshots):
            n = 0
        self.slider.set(n)
        self.refresh()
        fps = int(self.fps.get().split()[0])
        self.after(int(1000 / fps), self._tick)

    def save_gif(self):
        v = self.app.variant
        if v is None or not v.snapshots:
            return
        path = filedialog.asksaveasfilename(defaultextension=".gif",
                                            filetypes=[("GIF", "*.gif")])
        if not path:
            return
        k = FIELD_ORDER[FIELD_NAMES.index(self.qty.get())]
        vrange, mode = self.vrange, self.app.mode
        fps = int(self.fps.get().split()[0])

        def job(progress, cancel):
            from matplotlib.animation import PillowWriter
            from matplotlib.figure import Figure
            fig = Figure(figsize=(8, 4.2), dpi=100)
            ax = fig.add_subplot(111)
            p = pal(mode)
            writer = PillowWriter(fps=fps)
            with writer.saving(fig, path, dpi=100):
                for n, (it, A) in enumerate(v.snapshots):
                    if cancel():
                        break
                    fig.clear()
                    ax = fig.add_subplot(111)
                    plotting.draw(ax, dataclasses.replace(v, A=A.astype(float)),
                                  k, fg=p["fg"], wall_color=p["muted"],
                                  vrange=vrange, label=VAR_NAMES[k],
                                  colorbar_cb=lambda m, lab: fig.colorbar(
                                      m, ax=ax, label=lab, shrink=0.85))
                    ax.set_title("%s — итерация %d" % (VAR_NAMES[k], it))
                    plotting.style(fig, mode)
                    fig.tight_layout()
                    writer.grab_frame()
                    progress((n + 1) / len(v.snapshots),
                             "GIF: кадр %d из %d" % (n + 1, len(v.snapshots)))
            return path

        self.app.run_task(job, lambda p: self.app.status("GIF сохранён: " + p),
                          "Сохранение GIF")


# ======================================================================
class GeometryPage(Page):
    title = "Геометрия"

    def __init__(self, master, app):
        super().__init__(master, app)
        tb = self.toolbar()
        self.grid_v = tk.BooleanVar(value=True)
        self.dims_v = tk.BooleanVar(value=True)
        self.mirror = tk.BooleanVar(value=False)
        for t, v in (("Сетка", self.grid_v), ("Размеры", self.dims_v),
                     ("Зеркально", self.mirror)):
            check(tb, t, v, self.refresh).pack(side="left", padx=(0, 12))
        label(tb, "Схема обновляется сразу при изменении параметров слева",
              11, muted=True).pack(side="right")
        self.info_lbl = label(self, "", 12, anchor="w", justify="left",
                          wraplength=900)
        self.info_lbl.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.plot = Plot(self, app)
        self.plot.grid(row=2, column=0, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

    def refresh(self):
        pv, msgs = self.app.preview, self.app.preview_msgs
        p = self.colors()
        if pv is None:
            self.plot.message("Геометрия задана с ошибкой:\n" + "\n".join(msgs))
            self.info_lbl.configure(text="")
            return
        f = self.plot.fig
        f.clear()
        ax = f.add_subplot(111)
        plotting.draw_geometry(ax, pv, grid=self.grid_v.get(),
                               dims=self.dims_v.get(), mirror=self.mirror.get(),
                               fg=p["fg"], accent=p["accent"],
                               gridcolor=p["muted"])
        ax.set_title("Камера и расчётная сетка %d × %d узлов (первый вариант)"
                     % (pv.grid["IN"], pv.grid["JN"]), fontsize=11)
        self.plot.show()
        g, X1, X2 = pv.grid, pv.X1 * 1000, pv.X2 * 1000
        dx = np.diff(X1[1:g["IN"] + 1])
        dr = np.diff(X2[1:g["JN"] + 1])
        txt = ("Узлов: предкамера %d, цилиндр %d, конус %d, выход %d по длине; "
               "по радиусу %d. Шаг по x от %.2f до %.2f мм, по r от %.2f до %.2f мм. "
               "Критика: JC=%d, IC=%d." % (
                   g["IC2"] - 1, g["IC1"] - g["IC2"], g["IC"] - g["IC1"],
                   g["IN"] - g["IC"], g["JN"] - 1, dx.min(), dx.max(),
                   dr.min(), dr.max(), g["JC"], g["IC"]))
        if msgs:
            txt += "\n⚠ " + "\n⚠ ".join(msgs)
        self.info_lbl.configure(text=txt, text_color=c("danger") if msgs else c("fg"))
