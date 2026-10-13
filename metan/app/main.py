"""Главное окно (оформление «Инженерный пульт»)."""

import datetime
import os
import sys
import queue
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .. import __version__, analysis, plotting
from ..params import Params
from ..solver import Cancelled, Solver
from .pages import (AnimationPage, ConvergencePage, FieldsPage, GeometryPage,
                    ProfilesPage)
from .pages2 import (ComparePage, GridCheckPage, OptimizePage, ProtocolPage,
                     SeriesPage, open_folder)
from .sidebar import Sidebar
from .theme import SANS, c, pal
from .widgets import button, caps, entry, font, label, segmented

PAGES = [FieldsPage, ProfilesPage, ConvergencePage, AnimationPage, GeometryPage,
         SeriesPage, OptimizePage, ComparePage, GridCheckPage, ProtocolPage]


class App(ctk.CTk):
    def __init__(self, mode=None, cfg=None):
        from . import config
        self.cfg = cfg if cfg is not None else config.load()
        mode = mode or self.cfg.get("mode", "light")
        ctk.set_appearance_mode(mode)
        try:
            ctk.set_widget_scaling(float(self.cfg.get("scale", 1.0)))
        except (TypeError, ValueError):
            pass
        super().__init__(fg_color=c("bg"))
        self.mode = mode
        self._set_icon()
        self.title("Metan — расчёт горения метана в камере")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1600, sw - 40), min(960, sh - 80)
        self.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), 10))
        self.minsize(1000, 640)
        self.results = None
        self.variant_idx = 0
        self.runs = []
        self.series = self.opt = self.gridcheck = None
        self.preview, self.preview_msgs = None, []
        self.outdir = tk.StringVar(value=os.path.abspath("results"))
        self.params_path = None
        self.q = queue.Queue()
        self.cancel_ev = threading.Event()
        self.busy = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._topbar()
        self._chips()
        self.sidebar = Sidebar(self, self)
        self.sidebar.grid(row=2, column=0, sticky="nsw")
        self._workspace()
        self._rightpanel()
        self.bind_all("<F5>", lambda e: self.run())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)
        self.show_page(PAGES[0].title)

    # ------------------------------------------------------------ верх
    def _topbar(self):
        tb = ctk.CTkFrame(self, fg_color=c("bg"), corner_radius=0, height=64)
        tb.grid(row=0, column=0, columnspan=3, sticky="ew")
        tb.grid_columnconfigure(2, weight=1)
        label(tb, "METAN", 18, mono=True, bold=True).grid(row=0, column=0,
                                                         padx=(20, 10), pady=12)
        label(tb, "горение CH4 + O2 · met21 · v%s" % __version__, 12,
              muted=True).grid(row=0, column=1, sticky="w")
        pf = ctk.CTkFrame(tb, fg_color="transparent")
        pf.grid(row=0, column=3, padx=10)
        self.prog_lbl = label(pf, "Готово к расчёту", 11, muted=True, mono=True,
                              anchor="w", width=260)
        self.prog_lbl.pack(fill="x")
        self.pbar = ctk.CTkProgressBar(pf, width=260, height=6,
                                       progress_color=c("accent"),
                                       fg_color=c("line"))
        self.pbar.set(0)
        self.pbar.pack(fill="x", pady=(4, 0))
        self.run_btn = button(tb, "▶  Рассчитать", self.run, primary=True,
                              width=150)
        self.run_btn.grid(row=0, column=4, padx=6)
        self.stop_btn = button(tb, "Стоп", self.stop, width=70)
        self.stop_btn.grid(row=0, column=5, padx=6)
        self.stop_btn.configure(state="disabled")
        button(tb, "Отчёт Word", self.report, width=110).grid(row=0, column=6,
                                                              padx=6)
        self.menu_btn = button(tb, "Меню ▾", self._show_menu, width=90)
        self.menu_btn.grid(row=0, column=7, padx=(6, 20))
        ctk.CTkFrame(self, fg_color=c("line"), height=1, corner_radius=0).grid(
            row=0, column=0, columnspan=3, sticky="sew")

    def _chips(self):
        fr = ctk.CTkFrame(self, fg_color=c("bg"), corner_radius=0, height=50)
        fr.grid(row=1, column=0, columnspan=3, sticky="ew")
        caps(fr, "Варианты").pack(side="left", padx=(20, 10), pady=10)
        self.chips_fr = ctk.CTkFrame(fr, fg_color="transparent")
        self.chips_fr.pack(side="left")
        self.chip_btns = []
        self.chips_hint = label(self.chips_fr, "появятся после расчёта", 12,
                                muted=True)
        self.chips_hint.pack(side="left")

    def _build_chips(self):
        for b in self.chip_btns:
            b.destroy()
        self.chips_hint.pack_forget()
        self.chip_btns = []
        for n, v in enumerate(self.results.variants):
            sel = n == self.variant_idx
            txt = "α %.2f · %s" % (v.values["ALFA"],
                                   "расх." if v.diverged else "%.3f" % v.fkomp)
            b = ctk.CTkButton(
                self.chips_fr, text=txt, height=32, corner_radius=16,
                font=font(12, mono=True), width=10,
                fg_color=c("accent") if sel else c("card"),
                hover_color=c("accent_hover") if sel else c("accent_soft"),
                text_color=c("on_accent") if sel else
                (c("danger") if v.diverged else c("fg")),
                border_width=1, border_color=c("accent") if sel else
                (c("danger") if v.diverged else c("line")),
                command=lambda n=n: self.select_variant(n))
            b.pack(side="left", padx=4)
            self.chip_btns.append(b)

    # ------------------------------------------------------------ центр
    def _workspace(self):
        ws = ctk.CTkFrame(self, fg_color=c("bg"), corner_radius=0)
        ws.grid(row=2, column=1, sticky="nsew", padx=14, pady=(10, 14))
        ws.grid_columnconfigure(0, weight=1)
        ws.grid_rowconfigure(1, weight=1)
        self.nav_var = tk.StringVar(value=PAGES[0].title)
        segmented(ws, [p.title for p in PAGES], self.show_page,
                  self.nav_var, wrap=True).grid(row=0, column=0, sticky="ew",
                                                pady=(0, 4))
        holder = ctk.CTkFrame(ws, fg_color="transparent")
        holder.grid(row=1, column=0, sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.pages = {}
        for P in PAGES:
            pg = P(holder, self)
            pg.grid(row=0, column=0, sticky="nsew")
            pg.grid_remove()
            self.pages[P.title] = pg
        self.page = None

    def show_page(self, title):
        if self.page is not None:
            self.page.grid_remove()
        self.page = self.pages[title]
        self.nav_var.set(title)
        self.page.grid()
        if title == "Сравнение":
            self.page.update_runs()
        else:
            self.page.refresh()

    # ------------------------------------------------------------ справа
    def _rightpanel(self):
        rp = ctk.CTkFrame(self, fg_color=c("panel"), corner_radius=0, width=290)
        rp.grid(row=2, column=2, sticky="nse")
        self.rp = rp
        show = self.cfg.get("right_panel")
        if show is None:
            show = self.winfo_screenwidth() >= 1500
        if not show:
            rp.grid_remove()
        rp.grid_propagate(False)
        rp.grid_columnconfigure(0, weight=1)
        self.res_caps = caps(rp, "Результат")
        self.res_caps.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        self.kv_fr = ctk.CTkFrame(rp, fg_color="transparent")
        self.kv_fr.grid(row=1, column=0, sticky="ew", padx=16)
        self.kv_fr.grid_columnconfigure(1, weight=1)
        self.kv = {}
        for n, key in enumerate(("Fkomp", "KM", "BETA", "Ms, кг/с", "Vгор, м/с",
                                 "Vок, м/с", "NITER", "T вых, K", "CH4 вых",
                                 "O2 вых", "CO2 вых")):
            label(self.kv_fr, key, 12, muted=True, anchor="w").grid(
                row=n, column=0, sticky="w", pady=1)
            lv = label(self.kv_fr, "—", 12, mono=True, anchor="e")
            lv.grid(row=n, column=1, sticky="e", pady=1)
            self.kv[key] = lv
        caps(rp, "Fkomp(α)").grid(row=2, column=0, sticky="w", padx=16,
                                  pady=(14, 4))
        box = ctk.CTkFrame(rp, fg_color=c("card"), corner_radius=12,
                           border_width=1, border_color=c("line"))
        box.grid(row=3, column=0, sticky="ew", padx=12)
        self.mini = Figure(figsize=(2.6, 1.7), dpi=96)
        self.mini_canvas = FigureCanvasTkAgg(self.mini, master=box)
        self.mini_canvas.get_tk_widget().configure(highlightthickness=0)
        self.mini_canvas.get_tk_widget().pack(fill="x", padx=6, pady=6)
        caps(rp, "Файлы результатов").grid(row=4, column=0, sticky="w", padx=16,
                                           pady=(14, 4))
        of = ctk.CTkFrame(rp, fg_color="transparent")
        of.grid(row=5, column=0, sticky="ew", padx=12)
        of.grid_columnconfigure(0, weight=1)
        entry(of, self.outdir, 200, mono=False).grid(row=0, column=0, sticky="ew")
        button(of, "…", self._choose_outdir, width=36).grid(row=0, column=1,
                                                            padx=(4, 0))
        self.files_lbl = label(rp, "shi10.dat, shi20.dat - после расчёта", 11,
                               muted=True, anchor="w", justify="left",
                               wraplength=250)
        self.files_lbl.grid(row=6, column=0, sticky="ew", padx=16, pady=4)
        button(rp, "Открыть папку", lambda: open_folder(self.outdir.get())).grid(
            row=7, column=0, sticky="ew", padx=12, pady=(2, 0))
        self.status_lbl = label(rp, "", 11, muted=True, anchor="w",
                                justify="left", wraplength=250)
        self.status_lbl.grid(row=8, column=0, sticky="ew", padx=16, pady=12)
        self._update_right()

    def _choose_outdir(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get())
        if d:
            self.outdir.set(d)

    def _update_right(self):
        v = self.variant
        p = pal(self.mode)
        if v is None:
            for lv in self.kv.values():
                lv.configure(text="—")
        else:
            ex = analysis.exit_summary(v)
            val = v.values
            self.res_caps.configure(text="РЕЗУЛЬТАТ · α %.2f" % val["ALFA"])
            data = {"Fkomp": "%.5f (%s)" % (v.fkomp, v.fkomp_kind.lower()),
                    "KM": "%.2f" % val["KM"], "BETA": "%.1f" % val["BETA"],
                    "Ms, кг/с": "%.5f" % val["Ms"],
                    "Vгор, м/с": "%.1f" % val["Vgor"],
                    "Vок, м/с": "%.1f" % val["Vok"],
                    "NITER": "%d%s" % (v.NITER, " расх." if v.diverged else ""),
                    "T вых, K": "%.0f" % ex["T"], "CH4 вых": "%.4f" % ex["CH4"],
                    "O2 вых": "%.4f" % ex["O2"], "CO2 вых": "%.4f" % ex["CO2"]}
            for k, lv in self.kv.items():
                lv.configure(text=data[k],
                             text_color=c("danger") if v.diverged and k in
                             ("Fkomp", "NITER") else c("fg"))
        self.mini.clear()
        ax = self.mini.add_subplot(111)
        if self.results and len(self.results.variants) > 0:
            xs = [x.values["ALFA"] for x in self.results.variants]
            ys = [float("nan") if x.diverged else x.fkomp
                  for x in self.results.variants]
            ax.plot(xs, ys, "o-", color=p["accent"], lw=2, ms=4)
            if v is not None:
                ax.plot([v.values["ALFA"]], [v.fkomp], "o", ms=9, mfc="none",
                        mec=p["fg"])
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.25)
        plotting.style(self.mini, self.mode)
        self.mini.tight_layout(pad=0.4)
        self.mini_canvas.get_tk_widget().configure(background=p["card"])
        self.mini_canvas.draw_idle()

    # ------------------------------------------------------------ данные
    @property
    def variant(self):
        if self.results is None or not self.results.variants:
            return None
        return self.results.variants[min(self.variant_idx,
                                          len(self.results.variants) - 1)]

    def select_variant(self, n):
        self.variant_idx = n
        self._build_chips()
        self._update_right()
        self.page.refresh()

    def add_run(self, res, name=None):
        name = name or "Расчёт %d · %s" % (len(self.runs) + 1,
                                           datetime.datetime.now().strftime("%H:%M:%S"))
        self.runs.append((name, res))
        if self.page is self.pages["Сравнение"]:
            self.page.update_runs()

    def on_preview(self, pv, msgs):
        self.preview, self.preview_msgs = pv, msgs
        if getattr(self, "page", None) is self.pages.get("Геометрия"):
            self.page.refresh()

    def status(self, text):
        self.status_lbl.configure(text=text)

    # ------------------------------------------------------------ параметры
    def open_params(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"),
                                                     ("Все файлы", "*.*")])
        if path:
            try:
                self.sidebar.load(Params.load(path))
                self.params_path = path
                self.status("Загружено: " + path)
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def save_params(self):
        try:
            p = self.sidebar.params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile="params.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            p.save(path)
            self.status("Сохранено: " + path)

    def reset_params(self):
        self.sidebar.load(Params())

    # ------------------------------------------------------------ задачи
    def run_task(self, job, on_done, title):
        """Выполнить job(progress, cancel) в фоне; on_done(result) в окне."""
        if self.busy:
            messagebox.showinfo("Подождите", "Идёт другой расчёт.")
            return
        self.busy = True
        self.cancel_ev.clear()
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.pbar.set(0)
        self.prog_lbl.configure(text=title + "… (первый запуск - компиляция)")

        def progress(frac, text):
            self.q.put(("progress", frac, text))

        def worker():
            try:
                res = job(progress, self.cancel_ev.is_set)
                self.q.put(("done", on_done, res))
            except Cancelled:
                self.q.put(("cancelled",))
            except Exception as e:
                self.q.put(("error", "%s\n\n%s" % (e, traceback.format_exc())))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            last = None
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "progress":
                    last = msg
                    continue
                self.busy = False
                self.run_btn.configure(state="normal")
                self.stop_btn.configure(state="disabled")
                if msg[0] == "done":
                    self.pbar.set(1)
                    self.prog_lbl.configure(text="Готово")
                    msg[1](msg[2])
                elif msg[0] == "cancelled":
                    self.prog_lbl.configure(text="Остановлено")
                else:
                    self.prog_lbl.configure(text="Ошибка")
                    messagebox.showerror("Ошибка", msg[1])
        except queue.Empty:
            pass
        if last is not None and self.busy:
            self.pbar.set(max(0.0, min(1.0, last[1])))
            self.prog_lbl.configure(text=last[2])
        self.after(100, self._poll)

    def stop(self):
        self.cancel_ev.set()

    def run(self):
        try:
            prm = self.sidebar.params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        snap = self.sidebar.snapshot_every()
        outdir = self.outdir.get()

        def job(progress, cancel):
            def prog(nvar, nvarm, niter, nmax):
                progress(((nvar - 1) + niter / nmax) / nvarm,
                         "вариант %d/%d · итерация %d/%d" % (nvar, nvarm, niter, nmax))
            res = Solver(prm, progress=prog, cancel=cancel,
                         snapshot_every=snap).run()
            files = res.write_files(outdir)
            return res, files

        def done(out):
            res, files = out
            self.results = res
            self.variant_idx = 0
            self.add_run(res)
            self._build_chips()
            self._update_right()
            self.files_lbl.configure(text="Записано:\n" + "\n".join(
                os.path.abspath(f) for f in files))
            bad = sum(v.diverged for v in res.variants)
            self.status("Расчёт за %.1f с.%s" % (
                res.elapsed, " Расходимость в %d вариантах!" % bad if bad else ""))
            self.page.refresh()

        self.run_task(job, done, "Расчёт")

    def report(self):
        if self.results is None:
            messagebox.showinfo("Отчёт", "Сначала выполните расчёт.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".docx", initialfile="Отчёт_Metan.docx",
            filetypes=[("Документ Word", "*.docx")])
        if not path:
            return
        res, series, opt, gc = self.results, self.series, self.opt, self.gridcheck

        def job(progress, cancel):
            from .. import report
            progress(0.3, "Отчёт: построение рисунков…")
            return report.build(path, res, series=series, opt=opt, gridcheck=gc)

        self.run_task(job, lambda p: self.status("Отчёт сохранён: " + p),
                      "Отчёт Word")

    # ------------------------------------------------------------ меню
    def _set_icon(self):
        from .assets import icon_paths
        ico, png = icon_paths()
        try:
            if sys.platform == "win32" and ico:
                self.iconbitmap(ico)
            elif png:
                self._icon_img = tk.PhotoImage(file=png)
                self.iconphoto(True, self._icon_img)
        except tk.TclError:
            pass

    def _save_cfg(self):
        from . import config
        config.save(self.cfg)

    def _show_menu(self):
        from .splash import STORIES
        m = tk.Menu(self, tearoff=False, font=(SANS, 11))
        m.add_command(label="Светлая тема" if self.mode == "dark"
                      else "Тёмная тема", command=self.toggle_theme)
        sm = tk.Menu(m, tearoff=False, font=(SANS, 11))
        self._scale_var = tk.DoubleVar(value=float(self.cfg.get("scale", 1.0)))
        for v in (0.8, 0.9, 1.0, 1.1, 1.25, 1.5):
            sm.add_radiobutton(label="%d %%" % round(v * 100), value=v,
                               variable=self._scale_var,
                               command=lambda v=v: self.set_scale(v))
        m.add_cascade(label="Масштаб интерфейса", menu=sm)
        spm = tk.Menu(m, tearoff=False, font=(SANS, 11))
        self._splash_var = tk.StringVar(value=self.cfg.get("splash", "rocket"))
        for key, (title, _) in STORIES.items():
            spm.add_radiobutton(label=title, value=key, variable=self._splash_var,
                                command=lambda k=key: self._set_cfg("splash", k))
        spm.add_radiobutton(label="Без заставки", value="none",
                            variable=self._splash_var,
                            command=lambda: self._set_cfg("splash", "none"))
        m.add_cascade(label="Заставка при запуске", menu=spm)
        m.add_command(label=("Скрыть" if self.rp.winfo_ismapped() else "Показать")
                      + " панель результатов", command=self.toggle_right)
        m.add_separator()
        m.add_command(label="Руководство пользователя (Word)",
                      command=self.open_manual)
        m.add_command(label="О программе", command=self.about)
        b = self.menu_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _set_cfg(self, k, v):
        self.cfg[k] = v
        self._save_cfg()

    def set_scale(self, v):
        self._set_cfg("scale", v)
        ctk.set_widget_scaling(v)

    def toggle_right(self):
        if self.rp.winfo_ismapped():
            self.rp.grid_remove()
            self._set_cfg("right_panel", False)
        else:
            self.rp.grid()
            self._set_cfg("right_panel", True)

    def open_manual(self):
        from .assets import manual_path
        path = manual_path()
        if not path:
            messagebox.showinfo("Руководство", "Файл руководства не найден.")
            return
        open_folder(path, file=True)

    def about(self):
        messagebox.showinfo(
            "О программе",
            "Metan %s\nРасчёт горения метана в камере сгорания.\n"
            "Python-версия программы met21 (Фортран, RK1–RK7.FOR).\n"
            "При точности float64 результаты совпадают с Фортраном "
            "побайтно." % __version__)

    # ------------------------------------------------------------ тема
    def toggle_theme(self):
        self.mode = "dark" if self.mode == "light" else "light"
        ctk.set_appearance_mode(self.mode)
        self._set_cfg("mode", self.mode)
        self.sidebar.restyle()
        self._update_right()
        if self.results:
            self._build_chips()
        for pg in self.pages.values():
            for w in pg.__dict__.values():
                if hasattr(w, "restyle") and w is not pg:
                    try:
                        w.restyle()
                    except Exception:
                        pass
        self.page.refresh()

    def _close(self):
        self.cancel_ev.set()
        self.destroy()


def main(mode=None):
    from . import config
    from .splash import run_splash
    cfg = config.load()
    run_splash(cfg.get("splash", "rocket"))
    App(mode, cfg).mainloop()
    return 0
