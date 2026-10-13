"""Данные для заставки «Чертёж оживает» из реального расчёта (вариант α=0.8):
контур камеры, поле температуры (PNG, 8 бит) и линии тока (JSON) в пикселях
заставки. Запуск: python tools/make_splash_data.py"""

import json
import os

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

from metan import Params, Solver, analysis, plotting
from metan.kernels import NF, NT

OUT = os.path.join(os.path.dirname(__file__), "..", "metan", "app", "assets_data")
PX_MM = 4.5          # пикселей на мм
X0, CY = 38, 70      # положение начала камеры и оси в кадре 256x144

v = Solver(Params(NVARM=1)).run().variants[0]
poly = plotting.outline(v, 1000.0)
full = poly + [(x, -r) for x, r in reversed(poly)]
outline_px = [[round(X0 + x * PX_MM, 1), round(CY - r * PX_MM, 1)] for x, r in full]

xmax = poly[-1][0]
nx, nr = int(xmax * PX_MM) + 1, int(12.2 * PX_MM) + 1
xg = np.linspace(0, xmax / 1000, nx)
rg = np.linspace(0, 12.2 / 1000, nr)
T = analysis.to_regular(v, NT, xg, rg)
P = analysis.to_regular(v, NF, xg, rg)
full_T = np.ma.concatenate([T[:0:-1], T])           # зеркально
tmin, tmax = 293.0, float(T.max())
arr = np.where(np.ma.getmaskarray(full_T), 0,
               1 + np.clip((full_T.filled(tmin) - tmin) / (tmax - tmin), 0, 1) * 254)
Image.fromarray(arr.astype(np.uint8)).save(os.path.join(OUT, "splash_T.png"))

fig = Figure()
ax = fig.add_subplot(111)
fin = P.compressed()
levels = np.linspace(fin.min(), fin.max(), 16)[1:-1]
cs = ax.contour(xg * 1000, rg * 1000, P, levels=levels)
lines = []
for seg_list in cs.allsegs:
    for seg in seg_list:
        if len(seg) < 4:
            continue
        pts = [[round(X0 + x * PX_MM, 1), round(CY - r * PX_MM, 1)] for x, r in seg]
        lines.append(pts)
        lines.append([[px, round(2 * CY - py, 1)] for px, py in pts])
g = v.grid
dims = {"Dks": [X0 + v.X1[g["IC2"]] * 1000 * PX_MM, v.X2[g["JN"]] * 1000],
        "Dkr": [X0 + v.X1[g["IC"]] * 1000 * PX_MM, v.X2[g["JC"]] * 1000],
        "Dprk": [X0 + v.X1[g["IC2"]] * 500 * PX_MM, v.X2[g["JA3"]] * 1000],
        "Lprk": v.X1[g["IC2"]] * 1000, "Lks": (v.X1[g["IC1"]] - v.X1[g["IC2"]]) * 1000}
json.dump({"px_mm": PX_MM, "x0": X0, "cy": CY, "outline": outline_px,
           "lines": lines, "tmax": tmax, "T_origin": [X0, CY - (nr - 1)],
           "fkomp": v.fkomp, "dims": dims},
          open(os.path.join(OUT, "splash_blueprint.json"), "w"))
print("ok", nx, 2 * nr - 1, len(lines), "lines")
