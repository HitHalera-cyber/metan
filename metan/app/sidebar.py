"""Левая панель: исходные данные, справка, мини-схема камеры.

Строки параметров собраны из лёгких виджетов Tk (Frame/Label/Entry), а не
из CustomTkinter: их втрое меньше по числу окон, и прокрутка не
подтормаживает. Шрифты - общие объекты tkfont, они пересчитываются при
смене масштаба интерфейса.
"""

import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk
from matplotlib.figure import Figure

from .. import plotting
from ..params import GROUPS, Params, auto_grid, geometry_warnings
from .theme import MONO, SANS, c, pal
from .widgets import Canvas, button, check, font, label, option, _scaling

# подписи вариантов в выпадающих списках
CHOICES = {"NCORD": {"2": "осесимметричная", "1": "плоская"}}

HELP_HINT = ("Щёлкните правой кнопкой мыши по параметру, чтобы увидеть, "
             "что он означает.")


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=c("panel"), corner_radius=0, width=355)
        self.app = app
        self.vars = {}           # видимые параметры
        self.hidden = {}         # скрытые (значения по умолчанию / из файла)
        self.rows = {}
        self.meta = {}
        self._tk = []            # (виджет, {опция: роль цвета})
        self._preview_job = None
        self._sel = None
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.f_lab = tkfont.Font(family=SANS, size=-14)
        self.f_ent = tkfont.Font(family=MONO, size=-14)
        self.f_unit = tkfont.Font(family=SANS, size=-12)
        self.f_head = tkfont.Font(family=SANS, size=-14, weight="bold")
        self.f_sub = tkfont.Font(family=SANS, size=-12)
        self._scale_fonts()

        sf = ctk.CTkScrollableFrame(self, fg_color=c("panel"),
                                    scrollbar_button_color=c("line"),
                                    scrollbar_button_hover_color=c("muted"))
        sf.grid(row=0, column=0, sticky="nsew", padx=(10, 4), pady=(10, 0))
        sf.grid_columnconfigure(0, weight=1)
        self.sf = sf

        info = Params.field_info()
        self.sections = {}
        for n, (key, title, sub) in enumerate(GROUPS):
            head = self._head(sf, title, sub, key)
            head.grid(row=2 * n, column=0, sticky="ew", pady=(6, 2), padx=2)
            body = tk.Frame(sf, bd=0, highlightthickness=0)
            self._reg(body, bg="panel")
            body.grid(row=2 * n + 1, column=0, sticky="ew")
            body.grid_columnconfigure(0, weight=1)
            r = 0
            if key == "geom":
                r = self._mini_schema(body, r)
            for name, typ, meta in info:
                if meta["group"] != key:
                    continue
                if meta.get("hidden"):
                    self.hidden[name] = tk.StringVar()
                    continue
                r = self._row(body, r, name, meta)
                if name == "ALFA":
                    r = self._multi_alpha(body, r)
                if name == "JN":
                    self._pe_gen = 0
                    r = self._iters_block(body, r)
            if key == "mode":
                self.alfa_lbl = label(body, "", 11, wraplength=280,
                                      justify="left")
                self.alfa_lbl.configure(text_color=c("accent"))
                self.alfa_lbl.grid(row=r, column=0, sticky="w", padx=6,
                                   pady=(2, 0))
                r += 1
            if key == "calc":
                self.snap_var = tk.StringVar(value="20")
                r = self._row(body, r, "_snap", dict(
                    label="Кадр анимации каждые", sym="", unit="итер.",
                    short="Как часто запоминать поле для вкладки «Анимация»",
                    help="0 - не запоминать. На результат расчёта не влияет."),
                    var=self.snap_var)
            self.sections[key] = (head, body)
        self._multi_toggle()
        self.open_section("mode")

        # Справка по параметру (не прокручивается)
        hb = ctk.CTkFrame(self, fg_color=c("card"), corner_radius=12,
                          border_width=1, border_color=c("line"))
        hb.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        hb.grid_columnconfigure(0, weight=1)
        self.help_title = label(hb, "Описание параметра", 12, bold=True,
                                anchor="w", justify="left", wraplength=320)
        self.help_title.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        self.help_text = ctk.CTkTextbox(
            hb, height=110 if self.winfo_screenheight() >= 900 else 72,
            wrap="word", fg_color=c("card"), text_color=c("muted"),
            font=font(11), border_width=0)
        self.help_text.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))
        self._set_help("Описание параметра", HELP_HINT)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        for n, (t, cmd) in enumerate((("Открыть…", app.open_params),
                                      ("Сохранить…", app.save_params),
                                      ("Сбросить", app.reset_params))):
            bf.grid_columnconfigure(n, weight=1)
            button(bf, t, cmd).grid(row=0, column=n, sticky="ew",
                                    padx=(0 if n == 0 else 4, 0))
        self.restyle_tk()
        for name in self.rows:
            self._paint_row(name, pal(self.app.mode)["panel"])
        self.open_section(self.current_section)
        self.rescale()
        self.load(Params())

    # ------------------------------------------------------------ виджеты
    def _reg(self, w, **roles):
        self._tk.append((w, roles))
        return w

    def _scale_fonts(self):
        k = _scaling(self) if self.winfo_exists() else 1.0
        for f, px in ((self.f_lab, 14), (self.f_ent, 14), (self.f_unit, 12),
                      (self.f_head, 14), (self.f_sub, 12)):
            f.configure(size=-int(round(px * k)))

    def rescale(self):
        """Вызывается после смены масштаба интерфейса."""
        self._scale_fonts()
        k = _scaling(self)
        for w, roles in self._tk:
            if isinstance(w, tk.Label) and roles.get("wrap"):
                w.configure(wraplength=int(roles["wrap"] * k))

    def restyle_tk(self):
        p = pal(self.app.mode)
        for w, roles in self._tk:
            kw = {}
            for opt, role in roles.items():
                if opt == "wrap":
                    continue
                kw[opt] = p[role]
            try:
                w.configure(**kw)
            except tk.TclError:
                pass

    def _head(self, parent, title, sub, key):
        # скруглённая карточка; подписи - лёгкие tk.Label с тем же фоном
        fr = ctk.CTkFrame(parent, fg_color=c("card"), corner_radius=10,
                          border_width=1, border_color=c("line"),
                          cursor="hand2")
        arrow = tk.Label(fr, text="▸", font=self.f_head, width=2, anchor="w")
        self._reg(arrow, bg="card", fg="muted")
        t = tk.Label(fr, text=title.upper(), font=self.f_head, anchor="w")
        self._reg(t, bg="card", fg="fg")
        s = tk.Label(fr, text=sub, font=self.f_sub, anchor="w", justify="left")
        self._reg(s, bg="card", fg="muted", wrap=235)
        arrow.grid(row=0, column=0, rowspan=2, sticky="n", padx=(8, 0), pady=8)
        t.grid(row=0, column=1, sticky="w", pady=(8, 0))
        s.grid(row=1, column=1, sticky="w", pady=(0, 8), padx=(0, 10))
        fr.grid_columnconfigure(1, weight=1)
        for w in (fr, arrow, t, s):
            w.bind("<Button-1>", lambda e, k=key: self.open_section(k))
        fr.arrow, fr.title_lbl, fr.sub_lbl = arrow, t, s
        return fr

    def _row(self, parent, r, name, meta, var=None):
        fr = tk.Frame(parent, bd=0, highlightthickness=0)
        self._reg(fr, bg="panel")
        fr.grid(row=r, column=0, sticky="ew", padx=0, pady=1)
        fr.grid_columnconfigure(0, weight=1)
        text = meta["label"] + ("  " + meta["sym"] if meta.get("sym") else "")
        lab = tk.Label(fr, text=text, font=self.f_lab, anchor="w",
                       justify="left", wraplength=150)
        self._reg(lab, bg="panel", fg="fg", wrap=150)
        lab.grid(row=0, column=0, sticky="w", padx=(6, 6), pady=3)
        v = var or tk.StringVar()
        kind = meta.get("kind")
        if kind:
            names = CHOICES.get(name, {})
            w = option(fr, [names.get(str(x), str(x)) for x in kind],
                       variable=v, width=150 if names else 96)
            w.grid(row=0, column=1, sticky="e", pady=3)
        else:
            w = ctk.CTkEntry(fr, textvariable=v, width=90, height=30,
                             fg_color=c("card"), border_color=c("line"),
                             text_color=c("fg"), font=font(12, mono=True),
                             corner_radius=8, border_width=1)
            w.grid(row=0, column=1, sticky="e", pady=3)
            w.bind("<FocusIn>", lambda e, w=w: w.configure(
                border_color=c("accent")), add="+")
            w.bind("<FocusOut>", lambda e, w=w: w.configure(
                border_color=c("line")), add="+")
        u = tk.Label(fr, text=meta.get("unit", ""), font=self.f_unit, width=6,
                     anchor="w")
        self._reg(u, bg="panel", fg="muted")
        u.grid(row=0, column=2, sticky="w", padx=(4, 2))
        for wid in (fr, lab, w, u):
            wid.bind("<Button-3>", lambda e, n=name: self.show_help(n),
                     add="+")
            wid.bind("<Button-2>", lambda e, n=name: self.show_help(n),
                     add="+")      # macOS
        if var is None:
            v.trace_add("write", lambda *a: self._changed())
            self.vars[name] = v
        self.rows[name] = fr
        self.meta[name] = meta
        return r + 1

    # ------------------------------------------------------------ Nуст
    IT_HELP = dict(
        label="Итераций до установления", sym="Nуст", unit="",
        short="Сколько итераций понадобится этой сетке; считается само",
        help="Простыми словами: расчёт идёт «шагами» - на каждой итерации "
             "поля немного уточняются, пока не перестанут меняться. Nуст - "
             "примерно сколько таких шагов понадобится выбранной сетке.\n\n"
             "Почему число зависит от сетки: за одну итерацию поправка "
             "передаётся только в соседние узлы. Чем подробнее сетка, тем "
             "больше узлов от одного края камеры до другого и тем больше "
             "шагов нужно, чтобы поправка «дошла» везде. Число итераций "
             "растёт быстрее числа узлов: 46×22 - около 1200, 100×44 - около "
             "3000, 200×88 - около 8000, 300×66 - около 12 000 (по "
             "расчётам).\n\n"
             "Как это используется: программа сама останавливается, как "
             "только решение установилось, а Nит - только предел. Если Nит "
             "меньше Nуст, расчёт, скорее всего, упрётся в предел, не "
             "успев установиться, - Nуст подсказывает это ещё до запуска.\n\n"
             "Как считается: при каждой итерации ψ уточняется одним проходом "
             "метода Гаусса-Зейделя; ошибка за итерацию уменьшается в 1/ρ "
             "раз, где ρ - спектральный радиус итерационной матрицы (зависит "
             "только от сетки и находится до расчёта). Из него n₀ = "
             "ln(10⁻³)/ln ρ - сколько итераций нужно одному уравнению ψ. Вся "
             "система (вихрь, температура, состав) устанавливается иначе, "
             "поэтому Nуст = 1.15·23.9·n₀^0.703 - зависимость подобрана по "
             "расчётам на 8 сетках от 46×22 до 300×66 (точность ±11 %, "
             "1.15 - запас).\n\n"
             "Запас K = Nит / Nуст: ≥ 1 - успеет установиться; 0.5…1 - может "
             "не успеть; < 0.5 - не успеет, увеличьте Nит или уменьшите "
             "сетку.")

    def _iters_block(self, parent, r):
        fr = tk.Frame(parent, bd=0, highlightthickness=0)
        self._reg(fr, bg="panel")
        fr.grid(row=r, column=0, sticky="ew", pady=(6, 0))
        fr.grid_columnconfigure(0, weight=1)
        lab = tk.Label(fr, text="Итераций до установления  Nуст",
                       font=self.f_lab, anchor="w", justify="left",
                       wraplength=150)
        self._reg(lab, bg="panel", fg="fg", wrap=150)
        lab.grid(row=0, column=0, sticky="w", padx=(6, 6), pady=3)
        self.it_val = ctk.CTkLabel(fr, text="…", width=90, height=30,
                                   corner_radius=8, fg_color=c("card"),
                                   font=font(13, "bold", mono=True))
        self.it_val.grid(row=0, column=1, sticky="e", pady=3)
        sp = tk.Label(fr, width=6)
        self._reg(sp, bg="panel")
        sp.grid(row=0, column=2)
        self.it_note = tk.Label(fr, text="", font=self.f_unit, anchor="w",
                                justify="left", wraplength=270)
        self._reg(self.it_note, bg="panel", fg="muted", wrap=270)
        self.it_note.grid(row=2, column=0, columnspan=3, sticky="w", padx=6)
        lim = tk.Label(fr, text="Примерно столько итераций нужно этой сетке, "
                       "чтобы решение перестало меняться. Запас K = Nит / "
                       "Nуст:  ≥ 1 - успеет;  0.5…1 - может не успеть;  "
                       "< 0.5 - не успеет", font=self.f_unit,
                       anchor="w", justify="left", wraplength=270)
        self._reg(lim, bg="panel", fg="muted", wrap=270)
        lim.grid(row=1, column=0, columnspan=3, sticky="w", padx=6,
                 pady=(0, 4))
        for w in (fr, lab, self.it_val, self.it_note, lim):
            w.bind("<Button-3>", lambda e: self.show_help("_nreq"), add="+")
            w.bind("<Button-2>", lambda e: self.show_help("_nreq"), add="+")
        self.rows["_nreq"] = fr
        self.meta["_nreq"] = self.IT_HELP
        self._est = None
        self._node_cost = None
        return r + 1

    def show_iters(self, est=None):
        """Nуст и запас K = Nит/Nуст (est - из convergence.estimate)."""
        if est is not None:
            self._est = est
        est = self._est
        if not est:
            self.it_val.configure(text="—", text_color=c("muted"))
            return
        n = est["n_req"]
        try:
            nmax = int(float(self.vars["NMAX"].get()))
        except (ValueError, KeyError):
            nmax = 0
        k = nmax / n if n > 0 else float("inf")
        col = "accent" if k >= 1 else ("warn" if k >= 0.5 else "danger")
        self.it_val.configure(text="%.0f" % n if n < 1e7 else "> 10⁷",
                              text_color=c(col))
        verdict = ("успеет установиться" if k >= 1 else
                   "может не успеть" if k >= 0.5 else "не успеет")
        txt = "Предел Nит = %d → запас K = %.2f: %s." % (nmax, k, verdict)
        try:
            nx = int(float(self.vars["IN"].get()))
            nr = int(float(self.vars["JN"].get()))
            nv = int(float(self.vars["NVARM"].get())) if \
                self.multi_var.get() else 1
        except (ValueError, KeyError):
            nx = nr = 0
            nv = 1
        if nx and nr:
            fields = (nx + 1) * (nr + 1) * 17 * 8
            mem = 3 * fields + min(400e6, 120 * fields / 2 * nv)
            txt += " Память ≈ %.0f МБ." % (mem / 1e6)
            if self._node_cost:
                from .main import _fmt_time
                sec = min(n, nmax) * nx * nr * nv * self._node_cost
                txt += " Время ≈ %s%s." % (_fmt_time(sec),
                                           " на %d вариантов" % nv
                                           if nv > 1 else "")
        self.it_note.configure(text=txt)

    def _estimate_iters(self, prm):
        """Оценка Nуст в фоне (спектральный радиус, доли секунды)."""
        import threading
        self._pe_gen += 1
        gen = self._pe_gen
        self.it_val.configure(text="…", text_color=c("muted"))

        def work():
            import time as _t
            from .. import convergence
            from ..params import Params as _P
            from ..solver import Solver as _S
            try:
                est = convergence.estimate(prm)
            except Exception:
                est = None
            if self._node_cost is None:
                # скорость этого компьютера: секунд на узел·итерацию
                try:
                    t0 = _t.perf_counter()
                    _S(_P(NMAX=300, STOP_TOL=0), track_history=False).run()
                    self._node_cost = (_t.perf_counter() - t0) / (300 * 46 * 22)
                except Exception:
                    pass
            box.append(est)

        # Tk нельзя трогать из фонового потока: результат забирает таймер
        box = []

        def check():
            if gen != self._pe_gen:
                return
            if box:
                self.show_iters(box[0])
            else:
                self.after(60, check)
        threading.Thread(target=work, daemon=True).start()
        self.after(60, check)

    def _multi_alpha(self, parent, r):
        self.multi_var = tk.BooleanVar(value=False)
        cb = check(parent, "Несколько значений α (шаг Δα)", self.multi_var,
                   self._multi_toggle)
        cb.grid(row=r, column=0, sticky="w", padx=6, pady=(2, 4))
        self._multi_rows_at = r + 1
        return r + 1

    def _multi_toggle(self):
        on = self.multi_var.get()
        for name in ("DALFA", "NVARM"):
            if name in self.rows:
                (self.rows[name].grid if on else self.rows[name].grid_remove)()
        if on and self.vars["NVARM"].get().strip() in ("", "1"):
            self.vars["NVARM"].set("5")
        self._changed()

    def _mini_schema(self, parent, r):
        box = ctk.CTkFrame(parent, fg_color=c("card"), corner_radius=12,
                           border_width=1, border_color=c("line"))
        box.grid(row=r, column=0, sticky="ew", padx=2, pady=(0, 6))
        self.mini_fig = Figure(figsize=(3.3, 1.45), dpi=96)
        self.mini_canvas = Canvas(self.mini_fig, master=box)
        self.mini_canvas.get_tk_widget().configure(highlightthickness=0)
        self.mini_canvas.get_tk_widget().pack(fill="x", padx=6, pady=6)
        self.warn_lbl = label(box, "", 11, wraplength=280, justify="left",
                              anchor="w")
        self.warn_lbl.configure(text_color=c("danger"))
        self.warn_lbl.pack(fill="x", padx=8, pady=(0, 6))
        return r + 1

    def open_section(self, key):
        """Раскрыть один раздел, остальные свернуть."""
        p = pal(self.app.mode)
        for k, (head, body) in self.sections.items():
            is_open = k == key
            head.arrow.configure(text="▾" if is_open else "▸")
            bg = p["accent_soft"] if is_open else p["card"]
            head.configure(fg_color=bg)
            for w in (head.arrow, head.title_lbl, head.sub_lbl):
                w.configure(bg=bg)
            if is_open:
                body.grid()
            else:
                body.grid_remove()
        self.current_section = key
        try:
            self.sf._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    # ------------------------------------------------------------ справка
    def _set_help(self, title, text):
        self.help_title.configure(text=title)
        self.help_text.configure(state="normal")
        self.help_text.delete("1.0", "end")
        self.help_text.insert("1.0", text)
        self.help_text.configure(state="disabled")

    def show_help(self, name):
        m = self.meta[name]
        t = m["label"]
        if m.get("sym"):
            t += ", " + m["sym"]
        if m.get("unit"):
            t += " [%s]" % m["unit"]
        body = m.get("short", "")
        if m.get("help"):
            body += ".\n\n" + m["help"] if body else m["help"]
        if not name.startswith("_"):
            body += "\n\nИмя в файлах и в Фортране: %s" % name
        self._set_help(t, body)
        p = pal(self.app.mode)
        if self._sel in self.rows:
            self._paint_row(self._sel, p["panel"])
        self._paint_row(name, p["accent_soft"])
        self._sel = name

    def _paint_row(self, name, bg):
        fr = self.rows[name]
        fr.configure(bg=bg)
        for ch in fr.winfo_children():
            if isinstance(ch, tk.Label):
                ch.configure(bg=bg)
            elif isinstance(ch, ctk.CTkBaseClass):
                try:
                    ch.configure(bg_color=bg)      # уголки скругления
                except (ValueError, tk.TclError):
                    pass

    # ------------------------------------------------------------ данные
    @staticmethod
    def _fmt(v):
        if isinstance(v, float):
            t = repr(v)
            return t[:-2] if t.endswith(".0") else t
        return str(v)

    def load(self, p):
        for k, v in p.to_dict().items():
            if k in self.vars:
                self.vars[k].set(CHOICES.get(k, {}).get(str(v), self._fmt(v)))
            elif k in self.hidden:
                self.hidden[k].set(str(v))
        self.multi_var.set(p.NVARM > 1)
        self._multi_toggle()
        self._changed()

    def params(self):
        d = {k: v.get().strip() for k, v in self.hidden.items()}
        d.update({k: v.get().strip() for k, v in self.vars.items()})
        for k, names in CHOICES.items():
            back = {t: code for code, t in names.items()}
            d[k] = back.get(d[k], d[k])
        for k in d:
            if k not in ("out10", "out20", "precision", "model"):
                d[k] = d[k].replace(",", ".")
        if not self.multi_var.get():
            d["NVARM"] = "1"
        return Params.from_dict(d)

    def snapshot_every(self):
        try:
            return max(0, int(self.snap_var.get()))
        except ValueError:
            return 20

    def _changed(self):
        if getattr(self, "_est", None):
            self.show_iters()
        try:
            a0 = float(self.vars["ALFA"].get().replace(",", "."))
            if self.multi_var.get():
                da = float(self.vars["DALFA"].get().replace(",", "."))
                n = int(self.vars["NVARM"].get())
                vals = ["%.2f" % (a0 + k * da) for k in range(min(n, 30))]
                self.alfa_lbl.configure(text="Будут посчитаны α = " +
                                        " · ".join(vals))
            else:
                self.alfa_lbl.configure(text="")
        except (ValueError, KeyError, AttributeError):
            pass
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(350, self.update_preview)

    def update_preview(self):
        """Перерисовать мини-схему и проверить геометрию."""
        self._preview_job = None
        from ..solver import Solver
        p_ = pal(self.app.mode)
        self.mini_fig.clear()
        ax = self.mini_fig.add_subplot(111)
        msgs = []
        pv = None
        try:
            prm = self.params()
            msgs = geometry_warnings(prm)
            self._estimate_iters(prm)
            pv = Solver(prm).preview()
            plotting.draw_geometry(ax, pv, grid=False, dims=False,
                                   fg=p_["fg"], accent=p_["accent"])
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.tick_params(labelsize=7)
        except Exception as e:
            msgs.append(str(e).split("\n")[0])
            ax.set_axis_off()
        plotting.style(self.mini_fig, self.app.mode)
        self.mini_fig.tight_layout(pad=0.3)
        self.mini_canvas.get_tk_widget().configure(background=p_["card"])
        self.mini_canvas.draw_idle()
        self.warn_lbl.configure(text="\n".join("• " + m for m in msgs))
        self.app.on_preview(pv, msgs)

    def restyle(self):
        self.restyle_tk()
        p = pal(self.app.mode)
        for name in self.rows:
            self._paint_row(name, p["panel"])
        if self._sel in self.rows:
            self._paint_row(self._sel, pal(self.app.mode)["accent_soft"])
        self.open_section(self.current_section)
        self.update_preview()
