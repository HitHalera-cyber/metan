"""Общие элементы интерфейса."""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from .. import plotting
from .theme import MONO, SANS, c, pal


def font(size=13, weight="normal", mono=False):
    return ctk.CTkFont(family=MONO if mono else SANS, size=size, weight=weight)


def caps(master, text):
    """Заголовок раздела прописными буквами."""
    return ctk.CTkLabel(master, text=text.upper(), font=font(11, "bold"),
                        text_color=c("muted"), anchor="w")


def button(master, text, command, primary=False, **kw):
    if primary:
        return ctk.CTkButton(master, text=text, command=command,
                             fg_color=c("accent"), hover_color=c("accent_hover"),
                             text_color=c("on_accent"), corner_radius=18,
                             height=36, font=font(13, "bold"), **kw)
    return ctk.CTkButton(master, text=text, command=command,
                         fg_color=c("card"), hover_color=c("accent_soft"),
                         text_color=c("fg"), border_width=1,
                         border_color=c("line"), corner_radius=16, height=32,
                         font=font(12), **kw)


def entry(master, var, width=110, mono=True):
    return ctk.CTkEntry(master, textvariable=var, width=width, height=30,
                        fg_color=c("card"), border_color=c("line"),
                        text_color=c("fg"), font=font(12, mono=mono),
                        corner_radius=8)


def option(master, values, command=None, variable=None, width=200):
    return ctk.CTkOptionMenu(master, values=values, command=command,
                             variable=variable, width=width, height=30,
                             fg_color=c("card"), button_color=c("accent_soft"),
                             button_hover_color=c("accent"),
                             text_color=c("fg"), dropdown_fg_color=c("card"),
                             dropdown_text_color=c("fg"),
                             dropdown_hover_color=c("accent_soft"),
                             font=font(12), dropdown_font=font(12),
                             corner_radius=8)


class PillGroup(ctk.CTkFrame):
    """Группа кнопок-плашек с одной выбранной (замена CTkSegmentedButton).

    Каждая кнопка подстраивается под длину текста при любом масштабе
    Windows; при wrap=True ряд переносится, если не хватает ширины.
    """

    def __init__(self, master, values, command=None, variable=None, wrap=False,
                 size=12):
        super().__init__(master, fg_color="transparent")
        self.command = command
        self.var = variable or tk.StringVar(value=values[0])
        self.wrap = wrap
        self.buttons = {}
        self.rows = []
        for v in values:
            b = ctk.CTkButton(self, text=v, width=20, height=32,
                              corner_radius=16, border_width=1,
                              font=font(size), command=lambda v=v: self._click(v))
            self.buttons[v] = b
        self._layout_width = None
        if wrap:
            self._place_all(10 ** 6)
        else:
            for b in self.buttons.values():
                b.pack(side="left", padx=(0, 6))
        self.var.trace_add("write", lambda *a: self._paint())
        self._paint()
        if wrap:
            self.bind("<Configure>", self._on_resize)

    def _click(self, v):
        self.var.set(v)
        if self.command:
            self.command(v)

    def _paint(self):
        cur = self.var.get()
        for v, b in self.buttons.items():
            sel = v == cur
            b.configure(fg_color=c("accent") if sel else c("card"),
                        hover_color=c("accent_hover") if sel else c("accent_soft"),
                        text_color=c("on_accent") if sel else c("fg"),
                        border_color=c("accent") if sel else c("line"))

    def _place_all(self, avail):
        """Разложить кнопки по рядам; каждый ряд - отдельная строка без
        выравнивания по колонкам."""
        groups, cur, x = [], [], 0
        for b in self.buttons.values():
            w = b.winfo_reqwidth() + 6
            if self.wrap and cur and x + w > avail:
                groups.append(cur)
                cur, x = [], 0
            cur.append(b)
            x += w
        if cur:
            groups.append(cur)
        for n, grp in enumerate(groups):
            for k, b in enumerate(grp):
                b.grid(row=n, column=0, sticky="w", padx=(sum(
                    g.winfo_reqwidth() + 6 for g in grp[:k]), 0),
                    pady=(0, 6 if self.wrap else 0))
        self._groups = groups

    def _on_resize(self, e):
        if self._layout_width is not None and abs(e.width - self._layout_width) < 8:
            return
        self._layout_width = e.width
        for b in self.buttons.values():
            b.grid_forget()
        self._place_all(max(e.width, 100))

    def set(self, v):
        self.var.set(v)

    def get(self):
        return self.var.get()


def segmented(master, values, command=None, variable=None, wrap=False):
    return PillGroup(master, values, command, variable, wrap=wrap)


def check(master, text, var, command=None):
    return ctk.CTkCheckBox(master, text=text, variable=var, command=command,
                           fg_color=c("accent"), hover_color=c("accent_hover"),
                           border_color=c("muted"), text_color=c("fg"),
                           checkmark_color=c("on_accent"), font=font(12),
                           checkbox_width=18, checkbox_height=18,
                           corner_radius=5)


def label(master, text="", size=12, muted=False, mono=False, bold=False,
          **kw):
    return ctk.CTkLabel(master, text=text,
                        font=font(size, "bold" if bold else "normal", mono),
                        text_color=c("muted") if muted else c("fg"), **kw)


def card(master, **kw):
    kw.setdefault("corner_radius", 12)
    return ctk.CTkFrame(master, fg_color=c("card"), border_width=1,
                        border_color=c("line"), **kw)


class Tooltip:
    """Всплывающая подсказка у курсора."""

    def __init__(self, widget, text_fn, app):
        self.widget, self.text_fn, self.app, self.tip = widget, text_fn, app, None
        self._after = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def _schedule(self, _e=None):
        self._after = self.widget.after(600, self.show)

    def show(self):
        text = self.text_fn()
        if not text or self.tip:
            return
        p = pal(self.app.mode)
        x = self.widget.winfo_rootx() + 24
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        tk.Label(tw, text=text, justify="left", background=p["card"],
                 foreground=p["fg"], relief="solid", borderwidth=1,
                 wraplength=420, padx=8, pady=6,
                 font=(SANS, 10)).pack()

    def hide(self, _e=None):
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class Plot(ctk.CTkFrame):
    """Рисунок matplotlib, вписанный в интерфейс, с панелью инструментов."""

    def __init__(self, master, app, toolbar=True, figsize=(8, 5)):
        super().__init__(master, fg_color=c("card"), corner_radius=12,
                         border_width=1, border_color=c("line"))
        self.app = app
        self.fig = Figure(figsize=figsize, dpi=96)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        w = self.canvas.get_tk_widget()
        w.configure(highlightthickness=0, borderwidth=0)
        self.toolbar = None
        if toolbar:
            self.toolbar = NavigationToolbar2Tk(self.canvas, self,
                                                pack_toolbar=False)
            self.toolbar.update()
            self.toolbar.pack(side="bottom", fill="x", padx=8, pady=(0, 6))
        w.pack(fill="both", expand=True, padx=8, pady=8)
        self.restyle()

    def restyle(self):
        p = pal(self.app.mode)
        self.canvas.get_tk_widget().configure(background=p["card"])
        if self.toolbar is not None:
            # значки панели чёрные - в тёмной теме нужен светлый фон под ними
            tbg = p["card"] if self.app.mode == "light" else p["muted"]
            self.toolbar.configure(background=tbg)
            for ch in self.toolbar.winfo_children():
                try:
                    ch.configure(background=tbg)
                    ch.configure(foreground="#12201d")
                except tk.TclError:
                    pass

    @property
    def theme(self):
        return self.app.mode

    def clear(self):
        self.fig.clear()

    def message(self, text):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_axis_off()
        ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=13,
                color=pal(self.app.mode)["muted"], transform=ax.transAxes,
                wrap=True)
        self.show()

    def show(self):
        plotting.style(self.fig, self.app.mode)
        try:
            self.fig.tight_layout()
        except Exception:
            pass
        self.restyle()
        self.canvas.draw_idle()


class Table(ctk.CTkFrame):
    """Таблица (ttk.Treeview) в оформлении темы."""

    _n = 0

    def __init__(self, master, app, columns, widths=None, height=8):
        super().__init__(master, fg_color=c("card"), corner_radius=12,
                         border_width=1, border_color=c("line"))
        self.app = app
        Table._n += 1
        self.style_name = "M%d.Treeview" % Table._n
        self.tree = ttk.Treeview(self, columns=[str(i) for i in range(len(columns))],
                                 show="headings", height=height,
                                 style=self.style_name)
        for i, title in enumerate(columns):
            self.tree.heading(str(i), text=title)
            self.tree.column(str(i), width=(widths or [100] * len(columns))[i],
                             anchor="e" if i else "w", stretch=True)
        ys = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y", pady=8)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.restyle()

    def restyle(self):
        p = pal(self.app.mode)
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(self.style_name, background=p["card"],
                     fieldbackground=p["card"], foreground=p["fg"],
                     rowheight=24, font=(SANS, 10), borderwidth=0)
        st.configure(self.style_name + ".Heading", background=p["panel"],
                     foreground=p["muted"], font=(SANS, 10, "bold"),
                     borderwidth=0, relief="flat")
        st.map(self.style_name, background=[("selected", p["accent_soft"])],
               foreground=[("selected", p["fg"])])
        self.tree.tag_configure("bad", foreground=p["danger"])

    def set_rows(self, rows, bad=None):
        self.tree.delete(*self.tree.get_children())
        for n, r in enumerate(rows):
            tags = ("bad",) if bad and bad[n] else ()
            self.tree.insert("", "end", values=[str(x) for x in r], tags=tags)

    def selected_index(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None
