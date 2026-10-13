"""Обработка результатов: профили, средние величины на выходе, перенос поля
на общую сетку для сравнения расчётов."""

import numpy as np
from matplotlib.path import Path
from matplotlib.tri import LinearTriInterpolator, Triangulation

from .kernels import NF, NMFU1, NMOX1, NMPR1, NMPR2, NMDF, NMOX2, NMFU2, NT
from .plotting import node_mask, outline

SPECIES = [(NMFU1, "CH4"), (NMOX1, "O2"), (NMPR1, "CO2"), (NMPR2, "H2O"),
           (NMDF, "H2"), (NMOX2, "CO"), (NMFU2, "OH")]


def radial_profile(v, k, i):
    """Значения величины k вдоль радиуса в сечении с номером узла i.
    Возвращает (r, значения) в метрах, только узлы внутри области."""
    mask = node_mask(v)
    js = [j for j in range(1, v.grid["JN"] + 1) if not mask[j - 1, i - 1]]
    return (np.array([v.X2[j] for j in js]),
            np.array([v.A[i, j, k] for j in js], dtype=float))


def axial_profile(v, k, j=1):
    """Значения величины k вдоль оси x на радиусе с номером узла j."""
    mask = node_mask(v)
    iis = [i for i in range(1, v.grid["IN"] + 1) if not mask[j - 1, i - 1]]
    return (np.array([v.X1[i] for i in iis]),
            np.array([v.A[i, j, k] for i in iis], dtype=float))


def exit_section(v):
    """Номер узла выходного сечения (последний столбец сетки)."""
    return v.grid["IN"]


def mass_average(v, k, i=None):
    """Среднемассовое значение величины k в сечении i (по умолчанию выход).
    Вес - расход через кольцо между соседними узлами (разность ψ)."""
    i = exit_section(v) if i is None else i
    r, vals = radial_profile(v, k, i)
    _, psi = radial_profile(v, NF, i)
    if len(vals) < 2:
        return float("nan")
    w = np.abs(np.diff(psi))
    mid = 0.5 * (vals[1:] + vals[:-1])
    s = w.sum()
    return float((w * mid).sum() / s) if s > 0 else float("nan")


def exit_summary(v):
    """Среднемассовые T и состав на выходе."""
    d = {"T": mass_average(v, NT)}
    for k, name in SPECIES:
        d[name] = mass_average(v, k)
    return d


def _triangulation(v):
    """Триангуляция узлов расчётной области в метрах."""
    mask = node_mask(v)
    xs, rs, ij = [], [], []
    for j in range(1, v.grid["JN"] + 1):
        for i in range(1, v.grid["IN"] + 1):
            if not mask[j - 1, i - 1]:
                xs.append(v.X1[i])
                rs.append(v.X2[j])
                ij.append((i, j))
    xs, rs = np.array(xs, dtype=float), np.array(rs, dtype=float)
    tri = Triangulation(xs, rs)
    poly = Path(outline(v, scale=1.0))
    cx = xs[tri.triangles].mean(axis=1)
    cr = rs[tri.triangles].mean(axis=1)
    inside = poly.contains_points(np.c_[cx, cr], radius=1e-9)
    tri.set_mask(~inside)
    return tri, ij


def to_regular(v, k, xg, rg):
    """Поле величины k варианта v, перенесённое линейной интерполяцией на
    прямоугольную сетку (xg, rg) в метрах. Вне области - маска."""
    tri, ij = _triangulation(v)
    z = np.array([v.A[i, j, k] for i, j in ij], dtype=float)
    interp = LinearTriInterpolator(tri, z)
    X, R = np.meshgrid(xg, rg)
    return interp(X, R)


def same_grid(a, b):
    return (a.grid == b.grid and np.allclose(a.X1, b.X1)
            and np.allclose(a.X2, b.X2))


def difference(a, b, k, n=(240, 80)):
    """Разность поля k: b - a. Если сетки совпадают - по узлам, иначе на общей
    прямоугольной сетке. Возвращает (x, r, D) в метрах, D - masked array."""
    if same_grid(a, b):
        IN, JN = a.grid["IN"], a.grid["JN"]
        mask = node_mask(a)
        D = (np.asarray(b.A[1:IN + 1, 1:JN + 1, k], dtype=float)
             - np.asarray(a.A[1:IN + 1, 1:JN + 1, k], dtype=float)).T
        return a.X1[1:IN + 1], a.X2[1:JN + 1], np.ma.array(D, mask=mask)
    xmax = min(a.X1[a.grid["IN"]], b.X1[b.grid["IN"]])
    rmax = min(max(p[1] for p in outline(a, 1.0)),
               max(p[1] for p in outline(b, 1.0)))
    xg = np.linspace(0, xmax, n[0])
    rg = np.linspace(0, rmax, n[1])
    return xg, rg, to_regular(b, k, xg, rg) - to_regular(a, k, xg, rg)
