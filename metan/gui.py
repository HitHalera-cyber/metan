"""Десктопная программа: ввод параметров, запуск расчёта, графики полей.

Запуск:  python -m metan gui   (или двойной щелчок по metan_gui.pyw)
"""

import os
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_tkagg import (  # noqa: E402
    FigureCanvasTkAgg, NavigationToolbar2Tk)

from .params import Params, GROUPS  # noqa: E402

APP_TITLE = "Metan — расчёт горения метана в камере"

SUMMARY_COLS = [
    ("NVAR", "№", 40, "{:d}"),
    ("ALFA", "ALFA", 60, "{:.2f}"),
    ("KM", "KM", 60, "{:.2f}"),
    ("BETA", "BETA", 70, "{:.1f}"),
    ("Ms", "Ms, кг/с", 90, "{:.4e}"),
    ("Mok", "Mok, кг/с", 90, "{:.4e}"),
    ("Mgor", "Mgor, кг/с", 90, "{:.4e}"),
    ("Vgor", "Vgor, м/с", 75, "{:.1f}"),
    ("Vok", "Vok, м/с", 75, "{:.1f}"),
    ("Vcmw", "Vcmw, м/с", 75, "{:.1f}"),
    ("NITER", "NITER", 60, "{:d}"),
    ("fkomp", "Fkomp", 75, "{:.5f}"),
    ("fkomp_kind", "по", 45, "{}"),
    ("FIbeta", "FIbeta", 80, "{:.4e}"),
    ("status", "Статус", 110, "{}"),
]


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _e=None):
        if not self.text or self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        tk.Label(tw, text=self.text, justify="left", background="#ffffe0",
                 relief="solid", borderwidth=1, wraplength=380,
                 padx=6, pady=4).pack()

    def hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ScrollFrame(ttk.Frame):
    """Фрейм с вертикальной прокруткой."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.inner.bind("<Enter>", lambda e: self._bind_wheel(True))
        self.inner.bind("<Leave>", lambda e: self._bind_wheel(False))

    def _bind_wheel(self, on):
        if on:
            self.canvas.bind_all("<MouseWheel>", self._wheel)
            self.canvas.bind_all("<Button-4>", self._wheel)
            self.canvas.bind_all("<Button-5>", self._wheel)
        else:
            for s in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.canvas.unbind_all(s)

    def _wheel(self, e):
        if getattr(e, "num", None) == 4:
            d = -1
        elif getattr(e, "num", None) == 5:
            d = 1
        else:
            d = -1 if e.delta > 0 else 1
        self.canvas.yview_scroll(d, "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1400x860")
        self.minsize(1000, 640)
        self.vars = {}
        self.results = None
        self.worker = None
        self.cancel_ev = threading.Event()
        self.q = queue.Queue()
        self.params_path = None
        self.outdir = tk.StringVar(value=os.path.abspath("results"))

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Run.TButton", font=("TkDefaultFont", 10, "bold"))

        self._build_menu()
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned, padding=6)
        right = ttk.Frame(paned, padding=(0, 6, 6, 6))
        paned.add(left, weight=0)
        paned.add(right, weight=1)
        self._build_params(left)
        self._build_results(right)
        self._load_into_form(Params())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    # ------------------------------------------------------------ меню
    def _build_menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=False)
        f.add_command(label="Открыть параметры…", command=self.open_params,
                      accelerator="Ctrl+O")
        f.add_command(label="Сохранить параметры", command=self.save_params,
                      accelerator="Ctrl+S")
        f.add_command(label="Сохранить параметры как…",
                      command=lambda: self.save_params(ask=True))
        f.add_separator()
        f.add_command(label="Параметры по умолчанию", command=self.reset_params)
        f.add_separator()
        f.add_command(label="Экспорт полей варианта в CSV…",
                      command=self.export_csv)
        f.add_separator()
        f.add_command(label="Выход", command=self._on_close)
        m.add_cascade(label="Файл", menu=f)
        r = tk.Menu(m, tearoff=False)
        r.add_command(label="Рассчитать", command=self.run, accelerator="F5")
        r.add_command(label="Остановить", command=self.stop)
        m.add_cascade(label="Расчёт", menu=r)
        h = tk.Menu(m, tearoff=False)
        h.add_command(label="О программе", command=self.about)
        m.add_cascade(label="Справка", menu=h)
        self.config(menu=m)
        self.bind_all("<F5>", lambda e: self.run())
        self.bind_all("<Control-o>", lambda e: self.open_params())
        self.bind_all("<Control-s>", lambda e: self.save_params())

    # ------------------------------------------------------------ параметры
    def _build_params(self, parent):
        ttk.Label(parent, text="Исходные данные",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        nb = ttk.Notebook(parent, width=430)
        nb.pack(fill="both", expand=True, pady=(4, 6))
        frames = {}
        for key, title in GROUPS:
            sf = ScrollFrame(nb)
            nb.add(sf, text=title)
            frames[key] = sf.inner
            sf.inner.columnconfigure(1, weight=1)
        rows = {k: 0 for k in frames}
        for name, typ, meta in Params.field_info():
            fr = frames[meta["group"]]
            r = rows[meta["group"]]
            lab = ttk.Label(fr, text=meta["label"], wraplength=230,
                            justify="left")
            lab.grid(row=r, column=0, sticky="w", padx=(2, 6), pady=3)
            v = tk.StringVar()
            kind = meta.get("kind")
            if kind:
                w = ttk.Combobox(fr, textvariable=v, width=12, state="readonly",
                                 values=[str(x) for x in kind])
            else:
                w = ttk.Entry(fr, textvariable=v, width=14)
            w.grid(row=r, column=1, sticky="ew", pady=3)
            ttk.Label(fr, text=meta["unit"], width=4).grid(row=r, column=2,
                                                          sticky="w", padx=2)
            tip = meta["help"] or ""
            Tooltip(lab, "%s\n\nИмя в программе: %s" % (tip, name) if tip
                    else "Имя в программе: %s" % name)
            Tooltip(w, tip)
            v.trace_add("write", lambda *a: self._update_alfa_preview())
            self.vars[name] = v
            rows[meta["group"]] = r + 1

        self.alfa_lbl = ttk.Label(parent, text="", foreground="#1f4e8c",
                                  wraplength=420, justify="left")
        self.alfa_lbl.pack(anchor="w", pady=(0, 4))

        b = ttk.Frame(parent)
        b.pack(fill="x")
        ttk.Button(b, text="Открыть…", command=self.open_params).pack(
            side="left")
        ttk.Button(b, text="Сохранить…",
                   command=lambda: self.save_params(ask=True)).pack(
            side="left", padx=4)
        ttk.Button(b, text="По умолчанию", command=self.reset_params).pack(
            side="left")

        o = ttk.LabelFrame(parent, text="Папка для shi10.dat / shi20.dat",
                           padding=4)
        o.pack(fill="x", pady=6)
        ttk.Entry(o, textvariable=self.outdir).pack(side="left", fill="x",
                                                    expand=True)
        ttk.Button(o, text="…", width=3, command=self._choose_outdir).pack(
            side="left", padx=(4, 0))

        rb = ttk.Frame(parent)
        rb.pack(fill="x")
        self.run_btn = ttk.Button(rb, text="▶  Рассчитать (F5)",
                                  style="Run.TButton", command=self.run)
        self.run_btn.pack(side="left", fill="x", expand=True)
        self.stop_btn = ttk.Button(rb, text="■  Стоп", command=self.stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=(4, 0))
        self.pbar = ttk.Progressbar(parent, mode="determinate", maximum=1000)
        self.pbar.pack(fill="x", pady=(6, 2))
        self.status = ttk.Label(parent, text="Готово к расчёту",
                                wraplength=420)
        self.status.pack(anchor="w")

    def _load_into_form(self, p):
        for k, v in p.to_dict().items():
            self.vars[k].set(str(v))
        self._update_alfa_preview()

    def _form_params(self):
        d = {k: v.get().strip().replace(",", ".") for k, v in self.vars.items()}
        for k in ("out10", "out20", "precision"):
            d[k] = self.vars[k].get().strip()
        return Params.from_dict(d)

    def _update_alfa_preview(self):
        try:
            a0 = float(self.vars["ALFA"].get().replace(",", "."))
            da = float(self.vars["DALFA"].get().replace(",", "."))
            n = int(self.vars["NVARM"].get())
            vals, a = [], a0
            for _ in range(min(n, 50)):
                a += da
                vals.append("%.2f" % a)
            txt = "Будут рассчитаны варианты ALFA = " + ", ".join(vals)
            if n > 50:
                txt += ", …"
        except (ValueError, KeyError):
            txt = ""
        self.alfa_lbl.configure(text=txt)

    def open_params(self):
        path = filedialog.askopenfilename(
            title="Открыть параметры", filetypes=[("JSON", "*.json"),
                                                  ("Все файлы", "*.*")])
        if not path:
            return
        try:
            self._load_into_form(Params.load(path))
            self.params_path = path
            self.status.configure(text="Загружено: " + path)
        except Exception as e:
            messagebox.showerror("Ошибка", "Не удалось прочитать файл:\n%s" % e)

    def save_params(self, ask=False):
        try:
            p = self._form_params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        path = self.params_path
        if ask or not path:
            path = filedialog.asksaveasfilename(
                title="Сохранить параметры", defaultextension=".json",
                initialfile="params.json", filetypes=[("JSON", "*.json")])
            if not path:
                return
        p.save(path)
        self.params_path = path
        self.status.configure(text="Сохранено: " + path)

    def reset_params(self):
        self._load_into_form(Params())

    def _choose_outdir(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get())
        if d:
            self.outdir.set(d)

    # ------------------------------------------------------------ результаты
    def _build_results(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)
        self.res_nb = nb

        # --- сводка
        f = ttk.Frame(nb, padding=4)
        nb.add(f, text="Сводка по вариантам")
        cols = [c[0] for c in SUMMARY_COLS]
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=12)
        for key, title, w, _ in SUMMARY_COLS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=w, minwidth=w, anchor="e",
                             stretch=False)
        txs = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        tys = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(xscrollcommand=txs.set, yscrollcommand=tys.set)
        tys.pack(side="right", fill="y")
        txs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._tree_open)
        self.tree.tag_configure("bad", background="#ffd6d6")
        ttk.Label(f, foreground="#555", wraplength=900, justify="left",
                  text="Двойной щелчок по строке - открыть поля варианта. "
                       "Fkomp - коэффициент полноты сгорания (по окислителю "
                       "при ALFA ≤ 1, по горючему при ALFA > 1). FIbeta "
                       "считалась в исходной программе, но не печаталась.").pack(
            anchor="w", pady=(4, 0))

        # --- поля
        g = ttk.Frame(nb, padding=4)
        nb.add(g, text="Поля")
        ctl = ttk.Frame(g)
        ctl.pack(fill="x")
        ttk.Label(ctl, text="Вариант:").pack(side="left")
        self.var_cb = ttk.Combobox(ctl, state="readonly", width=22)
        self.var_cb.pack(side="left", padx=(2, 10))
        ttk.Label(ctl, text="Величина:").pack(side="left")
        from .solver import VAR_NAMES
        self.field_keys = [13, 2, 1, 3, 4, 5, 6, 7, 8, 9, 12, 14, 15, 16, 11, 10]
        self.field_cb = ttk.Combobox(
            ctl, state="readonly", width=30,
            values=[VAR_NAMES[k] for k in self.field_keys])
        self.field_cb.current(0)
        self.field_cb.pack(side="left", padx=(2, 10))
        self.mirror = tk.BooleanVar(value=True)
        self.stream = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctl, text="Зеркально", variable=self.mirror,
                        command=self.redraw).pack(side="left")
        ttk.Checkbutton(ctl, text="Линии тока", variable=self.stream,
                        command=self.redraw).pack(side="left", padx=6)
        ttk.Button(ctl, text="Сохранить рисунок…",
                   command=self.save_figure).pack(side="right")
        self.var_cb.bind("<<ComboboxSelected>>", lambda e: self.redraw())
        self.field_cb.bind("<<ComboboxSelected>>", lambda e: self.redraw())

        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=g)
        tb = NavigationToolbar2Tk(self.canvas, g, pack_toolbar=False)
        tb.update()
        tb.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._empty_plot()

        # --- протокол
        h = ttk.Frame(nb, padding=4)
        nb.add(h, text="Протокол (shi10.dat)")
        self.text = tk.Text(h, wrap="none", font=("Courier New", 9))
        xs = ttk.Scrollbar(h, orient="horizontal", command=self.text.xview)
        ys = ttk.Scrollbar(h, orient="vertical", command=self.text.yview)
        self.text.configure(xscrollcommand=xs.set, yscrollcommand=ys.set,
                            state="disabled")
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.text.pack(fill="both", expand=True)

    def _empty_plot(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.text(0.5, 0.5, "Нажмите «Рассчитать»", ha="center", va="center",
                fontsize=14, color="#888", transform=ax.transAxes)
        ax.set_axis_off()
        self.canvas.draw_idle()

    def _tree_open(self, _e):
        sel = self.tree.selection()
        if not sel or not self.results:
            return
        idx = self.tree.index(sel[0])
        self.var_cb.current(idx)
        self.res_nb.select(1)
        self.redraw()

    def redraw(self):
        if not self.results or not self.results.variants:
            return
        from .solver import VAR_NAMES
        v = self.results.variants[max(self.var_cb.current(), 0)]
        k = self.field_keys[max(self.field_cb.current(), 0)]
        IN, JN = v.grid["IN"], v.grid["JN"]
        x = v.X1[1:IN + 1] * 1000.0
        y = v.X2[1:JN + 1] * 1000.0
        Z = np.array(v.A[1:IN + 1, 1:JN + 1, k], dtype=float).T
        F = np.array(v.A[1:IN + 1, 1:JN + 1, 2], dtype=float).T
        # маска: узлы вне расчётной области (в стенках)
        mask = np.zeros_like(Z, dtype=bool)
        for j in range(1, JN + 1):
            il = v.IMIN[j] - 1
            im = v.IMAX[j] + 1
            if j <= v.grid["JC"]:
                im = IN
            for i in range(1, IN + 1):
                if i < il or i > im:
                    mask[j - 1, i - 1] = True
        Z = np.ma.array(Z, mask=mask | ~np.isfinite(Z))
        F = np.ma.array(F, mask=mask | ~np.isfinite(F))
        wall = np.array([y[np.where(~mask[:, i])[0].max()]
                         if (~mask[:, i]).any() else np.nan
                         for i in range(IN)])
        if self.mirror.get():
            y = np.concatenate([-y[:0:-1], y])
            Z = np.ma.concatenate([Z[:0:-1], Z])
            F = np.ma.concatenate([F[:0:-1], F])
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        cmap = "turbo" if k == 13 else ("RdBu_r" if k in (1, 2) else "viridis")
        try:
            cs = ax.contourf(x, y, Z, levels=30, cmap=cmap)
            self.fig.colorbar(cs, ax=ax, label=VAR_NAMES[k])
        except (ValueError, TypeError):
            ax.text(0.5, 0.5, "Поле не определено (NaN/Inf)", ha="center",
                    transform=ax.transAxes)
        if self.stream.get():
            try:
                ax.contour(x, y, F, levels=20, colors="k", linewidths=0.5,
                           alpha=0.6)
            except (ValueError, TypeError):
                pass
        ax.plot(x, wall, color="k", lw=2)
        if self.mirror.get():
            ax.plot(x, -wall, color="k", lw=2)
        else:
            ax.axhline(0, color="k", lw=0.8, ls="--")
        ax.set_xlabel("x, мм")
        ax.set_ylabel("r, мм")
        ax.set_aspect("equal", adjustable="datalim")
        val = v.values
        ax.set_title("Вариант %d: ALFA=%.2f, Fkomp(%s)=%.5f%s" % (
            v.NVAR, val["ALFA"], v.fkomp_kind, v.fkomp,
            "  — РАСХОДИМОСТЬ" if v.diverged else ""))
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def save_figure(self):
        if not self.results:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png"),
                                                ("PDF", "*.pdf"),
                                                ("SVG", "*.svg")])
        if path:
            self.fig.savefig(path, dpi=200)

    def export_csv(self):
        if not self.results or not self.results.variants:
            messagebox.showinfo("Экспорт", "Сначала выполните расчёт.")
            return
        from .solver import VAR_NAMES
        v = self.results.variants[max(self.var_cb.current(), 0)]
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="variant%d.csv" % v.NVAR,
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        keys = sorted(VAR_NAMES)
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write("I;J;X1, м;X2, м;" + ";".join(VAR_NAMES[k] for k in keys)
                     + "\n")
            for j in range(1, v.grid["JN"] + 1):
                for i in range(1, v.grid["IN"] + 1):
                    vals = [i, j, v.X1[i], v.X2[j]] + [v.A[i, j, k] for k in keys]
                    fh.write(";".join(str(int(x)) if n < 2 else "%.6e" % x
                                      for n, x in enumerate(vals)) + "\n")
        self.status.configure(text="Экспортировано: " + path)

    # ------------------------------------------------------------ расчёт
    def run(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            p = self._form_params()
        except ValueError as e:
            messagebox.showerror("Ошибка в параметрах", str(e))
            return
        self.cancel_ev.clear()
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.pbar.configure(value=0)
        self.status.configure(text="Подготовка (при первом запуске - "
                                   "компиляция, до 30 с)…")
        outdir = self.outdir.get()
        self.worker = threading.Thread(target=self._work, args=(p, outdir),
                                       daemon=True)
        self.worker.start()

    def stop(self):
        self.cancel_ev.set()
        self.status.configure(text="Остановка…")

    def _work(self, p, outdir):
        from .solver import Solver, Cancelled

        def progress(nvar, nvarm, niter, nmax):
            self.q.put(("progress", nvar, nvarm, niter, nmax))
        try:
            res = Solver(p, progress=progress,
                         cancel=self.cancel_ev.is_set).run()
            files = res.write_files(outdir)
            self.q.put(("done", res, files))
        except Cancelled:
            self.q.put(("cancelled",))
        except Exception as e:
            self.q.put(("error", "%s\n\n%s" % (e, traceback.format_exc())))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, nvar, nvarm, niter, nmax = msg
                    self.pbar.configure(
                        value=int(1000 * ((nvar - 1) + niter / nmax) / nvarm))
                    self.status.configure(
                        text="Вариант %d из %d, итерация %d из %d"
                             % (nvar, nvarm, niter, nmax))
                elif kind == "done":
                    self._finish()
                    self._show_results(msg[1], msg[2])
                elif kind == "cancelled":
                    self._finish()
                    self.status.configure(text="Расчёт остановлен")
                elif kind == "error":
                    self._finish()
                    self.status.configure(text="Ошибка расчёта")
                    messagebox.showerror("Ошибка расчёта", msg[1])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish(self):
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _show_results(self, res, files):
        self.results = res
        self.pbar.configure(value=1000)
        self.tree.delete(*self.tree.get_children())
        for v in res.variants:
            d = dict(v.values)
            d.update(NVAR=v.NVAR, NITER=v.NITER, fkomp=v.fkomp,
                     fkomp_kind=v.fkomp_kind, FIbeta=v.extra.get("FIbeta"),
                     status="расходимость" if v.diverged else "сошёлся")
            row = []
            for key, _, _, fmt in SUMMARY_COLS:
                try:
                    row.append(fmt.format(d[key]))
                except (TypeError, ValueError):
                    row.append(str(d[key]))
            self.tree.insert("", "end", values=row,
                             tags=("bad",) if v.diverged else ())
        self.var_cb.configure(values=["%d: ALFA=%.2f" % (v.NVAR, v.values["ALFA"])
                                      for v in res.variants])
        self.var_cb.current(0)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(res.text10))
        self.text.configure(state="disabled")
        self.redraw()
        bad = sum(v.diverged for v in res.variants)
        self.status.configure(
            text="Готово за %.1f с. Файлы: %s%s" % (
                res.elapsed, ", ".join(files),
                "\nВНИМАНИЕ: расходимость в %d вариант(ах)" % bad if bad else ""))

    def about(self):
        from . import __version__
        messagebox.showinfo(
            "О программе",
            "%s\nверсия %s\n\nPython-версия программы met21 (RK1–RK7.FOR).\n"
            "Логика расчёта перенесена построчно; при точности float64 "
            "результаты совпадают с Фортраном (gfortran -fdefault-real-8) "
            "до последнего печатаемого знака." % (APP_TITLE, __version__))

    def _on_close(self):
        self.cancel_ev.set()
        self.destroy()


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
