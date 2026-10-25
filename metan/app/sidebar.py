"""Левая панель: исходные данные, справка, мини-схема камеры."""

import tkinter as tk

import customtkinter as ctk
from matplotlib.figure import Figure

from .. import plotting
from ..params import GROUPS, Params, geometry_warnings
from .theme import c, pal
from .widgets import Canvas, Tooltip, button, entry, font, label, option


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=c("panel"), corner_radius=0, width=360)
        self.app = app
        self.vars = {}
        self.rows = {}
        self._preview_job = None
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        sf = ctk.CTkScrollableFrame(self, fg_color=c("panel"),
                                    scrollbar_button_color=c("line"),
                                    scrollbar_button_hover_color=c("muted"))
        sf.grid(row=0, column=0, sticky="nsew", padx=(10, 4), pady=(10, 0))
        sf.grid_columnconfigure(0, weight=1)
        self.sf = sf

        info = Params.field_info()
        self.sections = {}
        self._hl = None
        for n, (key, title) in enumerate(GROUPS):
            head = ctk.CTkButton(
                sf, text="", anchor="w", height=36, corner_radius=10,
                fg_color=c("card"), hover_color=c("accent_soft"),
                text_color=c("fg"), border_width=1, border_color=c("line"),
                font=font(12, "bold"),
                command=lambda k=key: self.open_section(k))
            head.grid(row=2 * n, column=0, sticky="ew", pady=(6, 2), padx=2)
            body = ctk.CTkFrame(sf, fg_color="transparent")
            body.grid(row=2 * n + 1, column=0, sticky="ew")
            body.grid_columnconfigure(0, weight=1)
            r = 0
            if key == "geom":
                r = self._mini_schema(body, r)
            cnt = 0
            for name, typ, meta in info:
                if meta["group"] != key:
                    continue
                r = self._row(body, r, name, meta)
                cnt += 1
            if key == "mode":
                self.alfa_lbl = label(body, "", 11, wraplength=300,
                                      justify="left")
                self.alfa_lbl.configure(text_color=c("accent"))
                self.alfa_lbl.grid(row=r, column=0, sticky="w", padx=4,
                                   pady=(2, 0))
                r += 1
            if key == "calc":
                fr = ctk.CTkFrame(body, fg_color="transparent")
                fr.grid(row=r, column=0, sticky="ew", padx=4, pady=2)
                fr.grid_columnconfigure(0, weight=1)
                label(fr, "Кадр анимации каждые N итераций", 12,
                      wraplength=175, justify="left").grid(row=0, column=0,
                                                           sticky="w")
                self.snap_var = tk.StringVar(value="20")
                entry(fr, self.snap_var, 70).grid(row=0, column=1, sticky="e")
                r += 1
                cnt += 1
            self.sections[key] = (head, body, title, cnt)
        self.open_section("mode")

        # Справка по параметру (не прокручивается)
        hb = ctk.CTkFrame(self, fg_color=c("card"), corner_radius=12,
                          border_width=1, border_color=c("line"))
        hb.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        hb.grid_columnconfigure(0, weight=1)
        self.help_title = label(hb, "Наведите мышь на параметр", 12, bold=True,
                                anchor="w", justify="left", wraplength=320)
        self.help_title.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        self.help_text = ctk.CTkTextbox(
            hb, height=96 if self.winfo_screenheight() >= 900 else 64, wrap="word",
                                        fg_color=c("card"), text_color=c("muted"),
                                        font=font(11), border_width=0)
        self.help_text.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))
        self.help_text.configure(state="disabled")

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        for n, (t, cmd) in enumerate((("Открыть…", app.open_params),
                                      ("Сохранить…", app.save_params),
                                      ("Сбросить", app.reset_params))):
            bf.grid_columnconfigure(n, weight=1)
            button(bf, t, cmd).grid(row=0, column=n, sticky="ew",
                                    padx=(0 if n == 0 else 4, 0))
        self.load(Params())

    # ------------------------------------------------------------------
    def _row(self, parent, r, name, meta):
        fr = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8)
        fr.grid(row=r, column=0, sticky="ew", padx=0, pady=1)
        fr.grid_columnconfigure(0, weight=1)
        lab = label(fr, meta["label"], 12, anchor="w", justify="left",
                    wraplength=175)
        lab.grid(row=0, column=0, sticky="w", padx=(6, 6), pady=3)
        v = tk.StringVar()
        kind = meta.get("kind")
        if kind:
            w = option(fr, [str(x) for x in kind], variable=v, width=100)
        else:
            w = entry(fr, v, 100)
        w.grid(row=0, column=1, sticky="e", pady=3)
        label(fr, meta["unit"], 11, muted=True, width=30, anchor="w").grid(
            row=0, column=2, sticky="w", padx=(4, 4))
        text = "%s\n\nИмя в программе: %s" % (meta["help"], name)
        for wid in (fr, lab, w):
            wid.bind("<Enter>", lambda e, n=name, m=meta, t=text:
                     self._hover(n, m, t), add="+")
        Tooltip(lab, lambda t=text: t, self.app)
        v.trace_add("write", lambda *a: self._changed())
        self.vars[name] = v
        self.rows[name] = fr
        return r + 1

    def _mini_schema(self, parent, r):
        box = ctk.CTkFrame(parent, fg_color=c("card"), corner_radius=12,
                           border_width=1, border_color=c("line"))
        box.grid(row=r, column=0, sticky="ew", padx=2, pady=(0, 6))
        self.mini_fig = Figure(figsize=(3.3, 1.45), dpi=96)
        self.mini_canvas = Canvas(self.mini_fig, master=box)
        self.mini_canvas.get_tk_widget().configure(highlightthickness=0)
        self.mini_canvas.get_tk_widget().pack(fill="x", padx=6, pady=6)
        self.warn_lbl = label(box, "", 11, wraplength=300, justify="left",
                              anchor="w")
        self.warn_lbl.configure(text_color=c("danger"))
        self.warn_lbl.pack(fill="x", padx=8, pady=(0, 6))
        return r + 1

    def open_section(self, key):
        """Раскрыть один раздел, остальные свернуть (как вкладки)."""
        for k, (head, body, title, cnt) in self.sections.items():
            is_open = k == key
            head.configure(
                text=("▾  " if is_open else "▸  ") + title.upper() +
                ("" if is_open else "   (%d)" % cnt),
                fg_color=c("accent_soft") if is_open else c("card"))
            if is_open:
                body.grid()
            else:
                body.grid_remove()
        self.current_section = key
        try:
            self.sf._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def _hover(self, name, meta, text):
        if self._hl == name:
            return
        self.help_title.configure(text=meta["label"])
        self.help_text.configure(state="normal")
        self.help_text.delete("1.0", "end")
        self.help_text.insert("1.0", text)
        self.help_text.configure(state="disabled")
        if self._hl in self.rows:
            self.rows[self._hl].configure(fg_color="transparent")
        self.rows[name].configure(fg_color=c("accent_soft"))
        self._hl = name

    # ------------------------------------------------------------------
    def load(self, p):
        for k, v in p.to_dict().items():
            self.vars[k].set(str(v))
        self._changed()

    def params(self):
        d = {k: v.get().strip() for k, v in self.vars.items()}
        for k in d:
            if k not in ("out10", "out20", "precision", "model"):
                d[k] = d[k].replace(",", ".")
        return Params.from_dict(d)

    def snapshot_every(self):
        try:
            return max(0, int(self.snap_var.get()))
        except ValueError:
            return 20

    def _changed(self):
        try:
            a0 = float(self.vars["ALFA"].get().replace(",", "."))
            da = float(self.vars["DALFA"].get().replace(",", "."))
            n = int(self.vars["NVARM"].get())
            vals, a = [], a0
            for _ in range(min(n, 30)):
                a += da
                vals.append("%.2f" % a)
            self.alfa_lbl.configure(text="Варианты: α = " + " · ".join(vals))
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
        self.update_preview()
