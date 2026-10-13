"""Построение картин полей в камере.

Контур камеры строится точно по геометрии сетки (как её задаёт GRID),
поле заливается только внутри контура (без «дыр» у стенок), линии тока -
изолинии функции тока ψ.
"""

import numpy as np
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path
from matplotlib.ticker import MaxNLocator

from .kernels import NF, NT

CMAPS = {NT: "inferno", 1: "RdBu_r", NF: "RdBu_r"}


def node_mask(v):
    """True для узлов вне расчётной области (внутри стенок). Форма (JN, IN)."""
    IN, JN = v.grid["IN"], v.grid["JN"]
    mask = np.ones((JN, IN), dtype=bool)
    for j in range(1, JN + 1):
        il = v.IMIN[j] - 1
        im = IN if j <= v.grid["JC"] else v.IMAX[j] + 1
        mask[j - 1, il - 1:im] = False
    return mask


def outline(v, scale=1000.0):
    """Контур верхней половины камеры: список точек (x, r)."""
    g, X1, X2 = v.grid, v.X1 * scale, v.X2 * scale
    return [
        (X1[1], 0.0),
        (X1[1], X2[g["JA3"]]),              # торец головки, предкамера
        (X1[g["IC2"]], X2[g["JA3"]]),       # стенка предкамеры
        (X1[g["IC2"]], X2[g["JN"]]),        # уступ (торец с подачей окислителя)
        (X1[g["IC1"]], X2[g["JN"]]),        # цилиндр КС
        (X1[g["IC"]], X2[g["JC"]]),         # сужение до критики
        (X1[g["IN"]], X2[g["JC"]]),         # выходной участок
        (X1[g["IN"]], 0.0),
    ]


def inlets(v, scale=1000.0):
    """Входные сечения: (название, x, r1, r2, ось 'r' - щель на торце)."""
    g, X1, X2 = v.grid, v.X1 * scale, v.X2 * scale
    return [
        ("центральная струя O2", X1[1], 0.0, X2[g["JZ"]]),
        ("горючее CH4", X1[1], X2[g["JZ1"]], X2[g["JA"]]),
        ("окислитель O2", X1[g["IC2"]], X2[g["JA1"]], X2[g["JA2"]]),
    ]


def _fill_outside(Z, mask):
    """Заполнить узлы вне области значениями соседей (только для гладкой
    заливки у стенок; потом всё равно обрезается по контуру)."""
    Z = np.array(Z, dtype=float)
    bad = mask | ~np.isfinite(Z)
    Z[bad] = np.nan
    for _ in range(Z.shape[0] + Z.shape[1]):
        nb = np.isnan(Z)
        if not nb.any():
            break
        acc = np.zeros_like(Z)
        cnt = np.zeros_like(Z)
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            S = np.roll(np.roll(Z, dj, 0), di, 1)
            if dj == 1:
                S[0, :] = np.nan
            if dj == -1:
                S[-1, :] = np.nan
            if di == 1:
                S[:, 0] = np.nan
            if di == -1:
                S[:, -1] = np.nan
            ok = np.isfinite(S)
            acc[ok] += S[ok]
            cnt[ok] += 1
        fill = nb & (cnt > 0)
        Z[fill] = acc[fill] / cnt[fill]
    return np.nan_to_num(Z)


def draw(ax, v, k, *, style="fill", mirror=True, stream=True, labels=False,
         nlevels=24, units="mm", fg="black", wall_color="#9a9a9a",
         cmap=None, colorbar_cb=None, label=None, show_inlets=True):
    """Нарисовать поле A[:, :, k] варианта v на осях ax.

    style: "fill" - цветная заливка; "lines" - только изолинии (как в
    методичке); "both" - заливка + изолинии этой же величины.
    """
    scale = 1000.0 if units == "mm" else 1.0
    IN, JN = v.grid["IN"], v.grid["JN"]
    x = v.X1[1:IN + 1] * scale
    y = v.X2[1:JN + 1] * scale
    mask = node_mask(v)
    Z = np.asarray(v.A[1:IN + 1, 1:JN + 1, k], dtype=float).T
    F = np.asarray(v.A[1:IN + 1, 1:JN + 1, NF], dtype=float).T
    inside = ~mask & np.isfinite(Z)
    zin = Z[inside]
    Zf = _fill_outside(Z, mask)
    Ff = _fill_outside(F, mask)

    poly = outline(v, scale)
    if mirror:
        full = poly + [(px, -py) for px, py in reversed(poly)]
        y = np.concatenate([-y[:0:-1], y])
        Zf = np.concatenate([Zf[:0:-1], Zf])
        Ff = np.concatenate([Ff[:0:-1], Ff])
    else:
        full = poly
    clip = Polygon(full, closed=True, transform=ax.transData,
                   facecolor="none", edgecolor="none")
    ax.add_patch(clip)

    def _clip(cs):
        if hasattr(cs, "set_clip_path"):
            cs.set_clip_path(clip)
        for c in getattr(cs, "collections", []):
            c.set_clip_path(clip)

    mappable = None
    if zin.size and np.ptp(zin) > 0:
        levels = MaxNLocator(nlevels).tick_values(zin.min(), zin.max())
    elif zin.size:
        levels = np.array([zin.min() - 1e-12, zin.min() + 1e-12])
    else:
        levels = None
    cmap = cmap or CMAPS.get(k, "viridis")
    if levels is not None and style in ("fill", "both"):
        mappable = ax.contourf(x, y, Zf, levels=levels, cmap=cmap,
                               extend="neither")
        _clip(mappable)
    if levels is not None and style in ("lines", "both"):
        cs = ax.contour(x, y, Zf, levels=levels[1:-1], colors=fg,
                        linewidths=0.8, negative_linestyles="solid")
        _clip(cs)
        if labels:
            for t in ax.clabel(cs, cs.levels[::2], fmt="%.3g", fontsize=7,
                               inline=True, colors=fg):
                t.set_clip_path(clip)
    if stream and k != NF:
        fin = F[~mask & np.isfinite(F)]
        if fin.size and np.ptp(fin) > 0:
            fl = np.linspace(fin.min(), fin.max(), 22)[1:-1]
            cs = ax.contour(x, y, Ff, levels=fl, colors=fg, linewidths=0.55,
                            alpha=0.55, negative_linestyles="solid")
            _clip(cs)

    # стенки: всё вне контура в пределах габарита закрашено
    xmin, xmax = x[0], x[-1]
    rmax = max(p[1] for p in poly)
    pad = 0.12 * rmax
    frame = [(xmin, rmax + pad), (xmax, rmax + pad), (xmax, -rmax - pad if mirror else 0),
             (xmin, -rmax - pad if mirror else 0)]
    verts = frame + [frame[0]] + full[::-1] + [full[-1]]
    codes = ([Path.MOVETO] + [Path.LINETO] * 3 + [Path.CLOSEPOLY]
             + [Path.MOVETO] + [Path.LINETO] * (len(full) - 1) + [Path.CLOSEPOLY])
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=wall_color,
                           edgecolor="none", hatch="////", alpha=0.35, zorder=3))
    ax.add_patch(Polygon(full, closed=True, fill=False, edgecolor=fg, lw=1.6,
                         zorder=4))
    if show_inlets:
        colors = ["#2b8cbe", "#e6550d", "#2b8cbe"]
        for (name, xi, r1, r2), c in zip(inlets(v, scale), colors):
            for s in ((1, -1) if mirror else (1,)):
                ax.plot([xi, xi], [s * r1, s * r2], color=c, lw=4,
                        solid_capstyle="butt", zorder=5)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-rmax - pad if mirror else 0, rmax + pad)
    ax.set_aspect("equal")
    u = "мм" if units == "mm" else "м"
    ax.set_xlabel("x, " + u)
    ax.set_ylabel("r, " + u)
    if mappable is not None and colorbar_cb is not None:
        colorbar_cb(mappable, label)
    return mappable
