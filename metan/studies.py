"""Параметрические исследования: серии по любому параметру, подбор
геометрии под максимум Fkomp, проверка на более мелкой сетке."""

import dataclasses
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import numpy as np

from .analysis import exit_summary
from .params import Params
from .solver import Cancelled, Solver

# Параметры, по которым имеет смысл строить серии и подбирать геометрию
SERIES_PARAMS = ["P", "DKR", "DCMB", "DOGOR", "DELGOR", "DKAR", "DOOK", "DELOK",
                 "DKS", "DELKAR", "ALKS", "TGY", "ROM1", "AKT", "H",
                 "ZMF2N", "ZMO2N", "NMAX"]
OPT_PARAMS = ["DKR", "DCMB", "DOGOR", "DELGOR", "DKAR", "DOOK", "DELOK",
              "DKS", "DELKAR", "ALKS", "TGY"]


def _workers():
    return max(1, min(4, os.cpu_count() or 1))


def summarize(res):
    """Краткая сводка расчёта (без полей) - для серий и таблиц."""
    out = []
    for v in res.variants:
        d = dict(v.values)
        d.update(NVAR=v.NVAR, NITER=v.NITER, fkomp=v.fkomp,
                 fkomp_kind=v.fkomp_kind, diverged=v.diverged)
        d.update({"exit_" + k: x for k, x in exit_summary(v).items()})
        out.append(d)
    return out


def with_value(params, name, value):
    d = params.to_dict()
    d[name] = value
    return Params.from_dict(d)


def at_alpha(params, alpha):
    """Параметры для одного варианта с заданным α."""
    d = params.to_dict()
    d.update(NVARM=1, ALFA=alpha - params.DALFA)
    return Params.from_dict(d)


# ----------------------------------------------------------------------
@dataclass
class SeriesResult:
    name: str
    values: list
    rows: list = field(default_factory=list)   # [(value, summarize(...)|None, error)]

    def alphas(self):
        for _, s, _ in self.rows:
            if s:
                return [r["ALFA"] for r in s]
        return []

    def curve(self, key="fkomp", nvar=1):
        xs, ys = [], []
        for val, s, _ in self.rows:
            if s and len(s) >= nvar:
                r = s[nvar - 1]
                xs.append(val)
                ys.append(np.nan if r["diverged"] else r[key])
        return np.array(xs), np.array(ys, dtype=float)


def run_series(params, name, values, progress=None, cancel=None):
    """Расчёт при каждом значении параметра name (все варианты α из params).
    progress(done, total); расчёты идут параллельно в несколько потоков."""
    values = list(values)
    res = SeriesResult(name=name, values=values)
    slots = [None] * len(values)

    def one(idx, val):
        try:
            p = with_value(params, name, val)
            r = Solver(p, cancel=cancel, track_history=False).run()
            return idx, summarize(r), None
        except Cancelled:
            raise
        except Exception as e:  # недопустимая геометрия и т.п.
            return idx, None, str(e)

    with ThreadPoolExecutor(_workers()) as ex:
        futs = [ex.submit(one, i, v) for i, v in enumerate(values)]
        done = 0
        for f in as_completed(futs):
            idx, s, err = f.result()
            slots[idx] = (values[idx], s, err)
            done += 1
            if progress:
                progress(done, len(values))
    res.rows = slots
    return res


# ----------------------------------------------------------------------
@dataclass
class OptResult:
    names: list
    alpha: float
    best_x: list
    best_f: float
    start_x: list
    start_f: float
    evals: list = field(default_factory=list)   # [(x, f, err)]


def optimize(params, names, bounds, alpha, max_evals=60, tol=0.02,
             progress=None, cancel=None):
    """Подбор параметров names в пределах bounds [(lo, hi), ...] на максимум
    Fkomp при заданном α (поиск по образцу: шаги ± по каждой координате,
    уменьшение шага при отсутствии улучшения). Расходящиеся и недопустимые
    варианты считаются худшими."""
    base = at_alpha(params, alpha)
    lo = np.array([b[0] for b in bounds], dtype=float)
    hi = np.array([b[1] for b in bounds], dtype=float)
    span = hi - lo
    cache = {}
    evals = []

    def f(x):
        key = tuple(np.round(x, 9))
        if key in cache:
            return cache[key]
        d = base.to_dict()
        for n, val in zip(names, x):
            d[n] = float(val)
        try:
            r = Solver(Params.from_dict(d), cancel=cancel,
                       track_history=False).run()
            v = r.variants[0]
            val = -1.0 if v.diverged or not np.isfinite(v.fkomp) else v.fkomp
            err = "расходимость" if v.diverged else None
        except Cancelled:
            raise
        except Exception as e:
            val, err = -2.0, str(e)
        cache[key] = val
        evals.append((list(map(float, x)), val, err))
        if progress:
            progress(len(evals), max_evals)
        return val

    x = np.clip(np.array([getattr(params, n) for n in names], float), lo, hi)
    fx = f(x)
    start_x, start_f = list(map(float, x)), fx
    step = 0.25 * span
    with ThreadPoolExecutor(_workers()) as ex:
        while len(evals) < max_evals and np.any(step > tol * span):
            cands = []
            for d in range(len(names)):
                for s in (+1, -1):
                    y = x.copy()
                    y[d] = np.clip(y[d] + s * step[d], lo[d], hi[d])
                    if not np.allclose(y, x):
                        cands.append(y)
            if not cands:
                break
            vals = list(ex.map(f, cands))
            best = int(np.argmax(vals))
            if vals[best] > fx + 1e-9:
                x, fx = cands[best], vals[best]
            else:
                step = step / 2
    return OptResult(names=list(names), alpha=alpha, best_x=list(map(float, x)),
                     best_f=fx, start_x=start_x, start_f=start_f, evals=evals)


# ----------------------------------------------------------------------
def refined_params(params, factor=2, iter_factor=3):
    """Параметры той же камеры на сетке, где каждый интервал разбит на
    factor частей. Номера узлов-границ пересчитываются так, чтобы границы
    остались на тех же радиусах и длинах."""
    pv = Solver(params).preview()
    g = pv.grid

    def m(j):
        return factor * (j - 1) + 1

    JN = m(g["JN"])
    JC = m(g["JC"])
    IC2 = m(g["IC2"])
    IC1 = IC2 + factor * (g["IC1"] - g["IC2"])
    IC = IC1 + (JN - JC)
    IN = IC + factor * (g["IN"] - g["IC"])
    d = params.to_dict()
    d.update(JZ=m(g["JZ"]), JZ1=m(g["JZ1"]), JA=m(g["JA"]), JA3=m(g["JA3"]),
             JA1=m(g["JA1"]), JA2=m(g["JA2"]), JN=JN, JC=JC, IC=IC, IC1=IC1,
             IC2=IC2, IN=IN, NMAX=params.NMAX * iter_factor,
             NPRINT=params.NPRINT * iter_factor)
    return Params.from_dict(d)


@dataclass
class GridCheck:
    base: object      # Results
    fine: object      # Results
    base_params: Params
    fine_params: Params

    def table(self):
        """Строки сравнения по вариантам: (α, имя, база, мелкая, отл. %)."""
        rows = []
        for a, b in zip(self.base.variants, self.fine.variants):
            ea, eb = exit_summary(a), exit_summary(b)
            for name, x, y in (("Fkomp", a.fkomp, b.fkomp),
                               ("T на выходе, K", ea["T"], eb["T"]),
                               ("CH4 на выходе", ea["CH4"], eb["CH4"]),
                               ("O2 на выходе", ea["O2"], eb["O2"]),
                               ("CO2 на выходе", ea["CO2"], eb["CO2"])):
                rel = ((y - x) / abs(x) * 100
                       if np.isfinite(x) and abs(x) > 1e-6 else np.nan)
                rows.append((a.values["ALFA"], name, x, y, rel,
                             a.diverged or b.diverged))
        return rows


def grid_check(params, factor=2, iter_factor=3, progress=None, cancel=None):
    fine_p = refined_params(params, factor, iter_factor)
    out = [None, None]

    def run(idx, p):
        def prog(nvar, nvarm, niter, nmax):
            if progress:
                progress(idx, nvar, nvarm, niter, nmax)
        out[idx] = Solver(p, progress=prog, cancel=cancel,
                          track_history=True).run()

    with ThreadPoolExecutor(2) as ex:
        fs = [ex.submit(run, 0, params), ex.submit(run, 1, fine_p)]
        for f in fs:
            f.result()
    return GridCheck(out[0], out[1], params, fine_p)


def params_replace(params, **kw):
    return dataclasses.replace(params, **kw).validate()
