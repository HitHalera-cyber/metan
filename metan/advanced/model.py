"""Уточнённая модель: решатель с подключаемыми моделями.

Модели (их можно сочетать):
* горение: "instant" - мгновенная брутто-реакция при T ≥ Tвоспл (исходная);
  "edm" - вихревой распад (скорость горения ограничена турбулентным
  перемешиванием); "equil" - равновесие по смешению: состав и температура
  в узле - химическое равновесие при его элементном составе;
* турбулентность: "algebraic" - формула исходной программы; "keps" -
  стандартная модель k-ε с пристеночными функциями;
* температура: TMODEL 0/1/2 основной программы (при "equil" - всегда 2).

Модуль подключается к решателю через точки _hook_* (metan/solver.py) и
не меняет расчёт основной программы. Удалить уточнённую модель: удалить
папку metan/advanced и строку с AdvancedPage в metan/app/main.py.
"""

import dataclasses
from dataclasses import dataclass

import numpy as np

from .. import thermo
from ..kernels import (NMDF, NMFU1, NMFU2, NMOX1, NMOX2, NMPR1, NMPR2, NMU,
                       NMU1, NRO3, NT, NV1)
from ..solver import Solver
from . import kernels as AK

COMBUSTION = {"instant": "мгновенная (исходная)",
              "edm": "вихревой распад (EDM)",
              "equil": "равновесие по смешению"}
TURBULENCE = {"algebraic": "алгебраическая (исходная)",
              "keps": "k–ε"}


@dataclass
class AdvOptions:
    combustion: str = "instant"
    turbulence: str = "algebraic"
    tmodel: int = 2               # равновесная температура
    edm_a: float = 4.0            # константа Магнуссена A
    edm_b: float = 0.0            # B (ограничение по продуктам), 0 - без него
    l_mix: float = 0.07           # масштаб турбулентности, доля диаметра
    turb_int: float = 0.05        # интенсивность турбулентности на входах
    mu_lam: float = 1e-4          # молекулярная вязкость газа, Па·с
    relax_mu: float = 0.3         # нижняя релаксация μт (k-ε)
    relax_eq: float = 0.5         # нижняя релаксация равновесного состава
    relax_w: float = 0.3          # нижняя релаксация вихря (при k-ε)
    avg_frac: float = 0.3         # доля последних итераций для осреднения

    def short(self):
        """Краткое имя для таблиц и легенд."""
        c = {"instant": "мгновенное", "edm": "EDM", "equil": "равновесное"}
        t = {"algebraic": "алгебр.", "keps": "k–ε"}
        name = "%s + %s" % (c[self.combustion], t[self.turbulence])
        if self.combustion == "instant" and self.tmodel != 2:
            name += ", T " + {0: "исх.", 1: "сглаж."}[self.tmodel]
        return name

    def describe(self):
        return "горение - %s; турбулентность - %s; температура - %s" % (
            COMBUSTION[self.combustion], TURBULENCE[self.turbulence],
            {0: "исходная", 1: "сглаженная", 2: "равновесная",
             3: "по степени выгорания"}[
                {"equil": 2, "edm": 3}.get(self.combustion, self.tmodel)])


# ----------------------------------------------------------------------
_EQ_CACHE = {}


def equilibrium_table(P, h_fuel, n=401):
    """Равновесные состав (9 веществ) и T по доле горючих элементов f."""
    key = (float(P), float(h_fuel), n)
    if key in _EQ_CACHE:
        return _EQ_CACHE[key]
    fs = np.linspace(0., 1., n)
    Ys = np.zeros((n, len(thermo.SPECIES)))
    Ts = np.zeros(n)
    order = np.argsort(np.abs(fs - 0.2))
    done = {}
    for k in order:
        f = fs[k]
        near = min(done, key=lambda q: abs(q - f)) if done else None
        T0 = done[near] if near is not None else 3000.
        try:
            if f <= 0. or f >= 1.:
                raise np.linalg.LinAlgError
            T, Y, _ = thermo.equilibrium_HP(f * h_fuel, P,
                                            thermo.elements_of(f), T0)
        except np.linalg.LinAlgError:
            # чистый O2 или чистый CH4 - реагировать нечему
            Y = np.zeros(len(thermo.SPECIES))
            Y[0], Y[1] = f, 1. - f
            T = 293.
        Ys[k], Ts[k] = Y, T
        done[f] = T
    _EQ_CACHE[key] = (fs, Ys, Ts)
    return _EQ_CACHE[key]


class AdvSolver(Solver):
    """Решатель основной программы + уточнённые модели (через хуки)."""

    def __init__(self, params, options=None, **kw):
        self.opt = options or AdvOptions()
        # при вихревом распаде температура - по степени выгорания (TMODEL 3)
        tm = {"equil": 2, "edm": 3}.get(self.opt.combustion, self.opt.tmodel)
        params = dataclasses.replace(params, TMODEL=tm)
        super().__init__(params, **kw)
        self._react = 1 if self.opt.combustion == "instant" else 0
        # при k-ε вязкость в 5-10 раз меньше алгебраической, и схема
        # исходной программы без нижней релаксации вихря не сходится
        if self.opt.turbulence == "keps":
            self._w_relax = self.opt.relax_w

    # ------------------------------------------------------------ подготовка
    def _hook_start(self):
        A = self.A
        IN, JN = self.IN, self.JN
        n1, n2 = IN + 1, JN + 1
        # расчётные узлы - как в цикле переноса EQN
        INT = np.zeros((n1 + 1, n2 + 1), dtype=np.bool_)
        for J in range(2, self.JNM + 1):
            IL, IM = int(self.IMIN[J]), int(self.IMAX[J])
            if J == self.JA3:
                IL = self.IC2 + 1
            if J == self.JC:
                IM = self.IC - 1
            INT[IL:IM + 1, J] = True
        self.INT = INT
        X1, X2 = self.X1, self.X2
        # характерный размер: диаметр предкамеры / камеры
        d_pk = 2 * X2[self.JA3]
        d_k = 2 * X2[JN]
        self.LM = np.zeros((n1 + 1, n2 + 1))
        for I in range(1, IN + 1):
            self.LM[I, :] = self.opt.l_mix * (d_pk if I <= self.IC2 else d_k)
        self.EK = np.zeros((n1 + 1, n2 + 1))
        if self.opt.turbulence == "keps":
            self._keps_init()
        if self.opt.combustion == "equil":
            fs, Ys, Ts = equilibrium_table(self.p.P, self.p.H)
            self._eq = (fs, Ys)
        self.burned = 0.
        self._mu_prev = None
        self._avg = None
        self._avg_cnt = 0

    def _keps_init(self):
        A, IN, JN, INT = self.A, self.IN, self.JN, self.INT
        X1, X2 = self.X1, self.X2
        n1, n2 = IN + 1, JN + 1
        shape = (n1 + 1, n2 + 1)
        K = np.zeros(shape)
        E = np.zeros(shape)
        KIN = np.zeros(shape)
        EIN = np.zeros(shape)
        BTYPE = np.zeros(shape, dtype=np.int64)       # 0 - не граница
        BSRC = np.zeros(shape + (2,), dtype=np.int64)
        YW = np.zeros(shape)
        ti = self.opt.turb_int
        cm = AK.C_MU
        vchar = max(abs(self.VINP), abs(self.VINS), abs(self.VINS1), 1.0)
        k0 = 1.5 * (ti * vchar) ** 2
        l0 = self.opt.l_mix * 2 * X2[JN]
        K[:] = k0
        E[:] = cm ** 0.75 * k0 ** 1.5 / l0
        # входы (как в INIT): центральная струя и щель горючего при I = 1,
        # щель окислителя при I = IC2
        inlets = []
        for J in range(1, self.JZ + 1):
            inlets.append((1, J, 2 * X2[self.JZ]))
        for J in range(self.JZ1, self.JA + 1):
            inlets.append((1, J, 2 * (X2[self.JA] - X2[self.JZ1])))
        for J in range(self.JA1, self.JA2 + 1):
            inlets.append((self.IC2, J, 2 * (X2[self.JA2] - X2[self.JA1])))
        inlet = np.zeros(shape, dtype=np.bool_)
        for I, J, dh in inlets:
            v = abs(A[I, J, NV1])
            k = max(1.5 * (ti * v) ** 2, 1e-4)
            KIN[I, J] = k
            EIN[I, J] = cm ** 0.75 * k ** 1.5 / max(0.07 * dh, 1e-6)
            inlet[I, J] = True
        # внешние узлы и пристеночные расчётные узлы
        for J in range(2, JN):
            for I in range(2, IN):
                if not INT[I, J]:
                    continue
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, b = I + di, J + dj
                    if INT[a, b] or BTYPE[a, b]:
                        continue
                    if inlet[a, b]:
                        BTYPE[a, b] = 1
                    else:
                        BTYPE[a, b] = 2
                        BSRC[a, b] = (I, J)
                        if b != 1 and a != IN:       # стенка, не ось и не выход
                            y = abs(X1[a] - X1[I]) if di else abs(X2[b] - X2[J])
                            y = 0.5 * y
                            YW[I, J] = y if YW[I, J] == 0 else min(YW[I, J], y)
        self.K, self.E, self.KIN, self.EIN = K, E, KIN, EIN
        self.BTYPE, self.BSRC, self.YW = BTYPE, BSRC, YW
        self.PK = np.zeros(shape)

    # ------------------------------------------------------------ шаги
    def _hook_after_viscos(self):
        A = self.A
        if self.opt.turbulence == "keps":
            # нижняя релаксация вязкости: резкие изменения μт раскачивают
            # связанную систему уравнений
            n1, n2 = self.IN + 1, self.JN + 1
            old = A[:n1, :n2, NMU].copy() if self._mu_prev is None \
                else self._mu_prev
            AK.keps_viscosity(A, self.INT, self.K, self.E, self.IN, self.JN,
                              self.opt.mu_lam, 50.0)
            if self.NITER > 3:
                A[:n1, :n2, NMU] = old + self.opt.relax_mu * (A[:n1, :n2, NMU] - old)
            self._mu_prev = A[:n1, :n2, NMU].copy()
            k = np.maximum(self.K, 1e-8)
            self.EK = self.E / k
        else:
            # ε/k по алгебраической вязкости: μт = Cμ·ρ·k²/ε и ε = Cμ^0.75·k^1.5/l
            # дают ε/k = Cμ^0.5·μт/(ρ·l²)
            n1, n2 = self.IN + 1, self.JN + 1
            mu = A[:n1, :n2, NMU]
            rho = np.maximum(A[:n1, :n2, NRO3], 1e-6)
            self.EK = np.zeros_like(self.LM)
            self.EK[:n1, :n2] = AK.C_MU ** 0.5 * mu / (rho * self.LM[:n1, :n2] ** 2)

    def _hook_after_convec(self):
        if self.opt.turbulence != "keps" or self.NITER < 3:
            return
        A = self.A
        AK.production(A, self.INT, self.X1, self.X2, self.R, self.PK,
                      self.IN, self.JN, int(self.NCORD))
        AK.keps_step(A, self.INT, self.AE, self.AW, self.AN, self.AS,
                     self.AE1, self.AW1, self.AN1, self.AS1, self.PK,
                     self.K, self.E, self.YW, self.IN, self.JN, 0.6,
                     1e-6, 1e-4)
        AK.keps_bounds(self.K, self.E, self.INT, self.BTYPE, self.BSRC,
                       self.KIN, self.EIN, self.IN, self.JN)

    def _hook_end(self):
        """Если решение не установилось (колеблется), поля заменяются
        средними по последним итерациям - как осреднение по времени."""
        self._avg_n = 0
        base = (self.opt.combustion == "instant"
                and self.opt.turbulence == "algebraic")
        if (base or self._settled is not False or self._avg is None
                or self._avg_cnt < 50):
            return
        self.A[...] = self._avg / self._avg_cnt
        self._avg_n = self._avg_cnt

    def _variant(self, res, preview=False):
        out = super()._variant(res, preview)
        if not preview and res.variants:
            res.variants[-1].extra["averaged"] = getattr(self, "_avg_n", 0)
            res.variants[-1].extra["model"] = self.opt.describe()
        return out

    def _accumulate(self):
        p = self.p
        limit = getattr(self, "_limit", p.NMAX)
        window = int(self.opt.avg_frac * p.NMAX)
        if self.NITER > limit - window:
            if self._avg is None:
                self._avg = np.zeros_like(self.A)
                self._avg_cnt = 0
            self._avg += self.A
            self._avg_cnt += 1

    def _hook_after_eqn(self):
        A = self.A
        if self.opt.combustion == "edm":
            self.burned = AK.edm_step(A, self.INT, self.AE1, self.AW1,
                                      self.AN1, self.AS1, self.EK,
                                      self.opt.edm_a, self.opt.edm_b,
                                      self.IN, self.JN)
        elif self.opt.combustion == "equil":
            self._equilibrium_composition()
        self._accumulate()

    def _equilibrium_composition(self):
        """Состав в каждом узле - равновесный при его доле горючих
        элементов f (атомы O и H, которых нет среди 7 веществ модели,
        отнесены к O2 и H2 - элементный баланс сохраняется)."""
        A = self.A
        n1, n2 = self.IN + 1, self.JN + 1
        idx = (NMFU1, NMOX1, NMPR1, NMPR2, NMOX2, NMDF, NMFU2)
        Y = A[:n1, :n2, :][:, :, list(idx)]
        prod = Y[:, :, 2:].sum(axis=2)
        fuel = Y[:, :, 0] + 0.2034 * prod
        tot = Y.sum(axis=2)
        f = np.where(tot > 0, fuel / np.where(tot > 0, tot, 1), 0.)
        f = np.clip(f, 0., 1.)
        fs, Ys = self._eq
        n = len(fs) - 1
        q = f * n
        k0 = np.minimum(q.astype(int), n - 1)
        w = (q - k0)[:, :, None]
        Yeq = Ys[k0] * (1 - w) + Ys[k0 + 1] * w           # 9 веществ
        sp = thermo.SPECIES
        g = {s: Yeq[:, :, i] for i, s in enumerate(sp)}
        mask = tot > 0
        new = {NMFU1: g["CH4"], NMOX1: g["O2"] + g["O"], NMPR1: g["CO2"],
               NMPR2: g["H2O"], NMOX2: g["CO"], NMDF: g["H2"] + g["H"],
               NMFU2: g["OH"]}
        r = self.opt.relax_eq
        for k, v in new.items():
            old = A[:n1, :n2, k]
            A[:n1, :n2, k] = np.where(mask, old + r * (v * tot - old), old)


def run(params, options, **kw):
    """Расчёт уточнённой моделью; возвращает Results основной программы."""
    return AdvSolver(params, options, **kw).run()


# ----------------------------------------------------------------------
def gci3(f3, f2, f1, r):
    """GCI по трём сеткам с отношением шагов r (f1 - самая мелкая)."""
    e21, e32 = f1 - f2, f2 - f3
    out = dict(f3=f3, f2=f2, f1=f1, p=np.nan, ext=np.nan, gci=np.nan)
    scale = max(abs(f1), 1e-12)
    if abs(e21) < 1e-6 * scale:
        out.update(kind="converged", gci=0.0, ext=f1)
    elif max(abs(e21), abs(e32)) < 0.01 * scale and (
            e32 * e21 < 0 or abs(e32) <= abs(e21)):
        # разности меньше 1 % и не убывают закономерно - это уже шум
        # итераций, а не влияние сетки
        out.update(kind="noise", gci=1.25 * max(abs(e21), abs(e32)) / scale * 100)
    elif e32 * e21 < 0:
        out.update(kind="oscillating", gci=1.25 * abs(e21) / scale * 100)
    elif abs(e32) <= abs(e21):
        out.update(kind="diverging", gci=3.0 * abs(e21) / scale * 100)
    else:
        p = np.log(abs(e32 / e21)) / np.log(r)
        out.update(kind="monotone", p=p, ext=f1 + e21 / (r ** p - 1),
                   gci=1.25 * abs(e21 / f1) / (r ** p - 1) * 100)
    return out


def grid_study(params, options, start=(100, 44), ratio=2 ** 0.5, levels=5,
               target=2.0, progress=None, cancel=None):
    """Сеточное исследование: сетки start·ratio^k, после каждой третьей и
    далее - GCI по трём последним; стоп при GCI(φк) < target %."""
    from ..convergence import estimate
    # при равновесном горении φк ≈ 1 на любой сетке - сходимость по φβ
    key = "fb" if options.combustion == "equil" else "fk"
    rows, gcis = [], []
    for k in range(levels):
        nx = int(round(start[0] * ratio ** k))
        nr = int(round(start[1] * ratio ** k))
        p = dataclasses.replace(params, IN=nx, JN=nr, NVARM=1, GRID_AUTO=1)
        try:
            n = int(1.5 * estimate(dataclasses.replace(
                p, TMODEL=2 if options.combustion == "equil"
                else options.tmodel))["n_req"]) + 1000
        except Exception:
            n = 20000
        p = dataclasses.replace(p, NMAX=max(p.NMAX, n))

        def prog(nvar, nvarm, niter, nmax, k=k):
            if progress:
                progress(k, levels, niter, nmax)
        res = run(p, options, progress=prog, cancel=cancel,
                  track_history=False)
        v = res.variants[0]
        from ..analysis import exit_summary
        rows.append(dict(IN=nx, JN=nr, fk=v.fkomp,
                         fb=v.extra.get("FIbeta", np.nan),
                         T=exit_summary(v)["T"], N=v.NITER,
                         settled=v.settled, diverged=v.diverged, res=res))
        if len(rows) >= 3:
            g = gci3(rows[-3][key], rows[-2][key], rows[-1][key], ratio)
            g["metric"] = "φβ" if key == "fb" else "φк"
            g["grids"] = tuple("%d×%d" % (r["IN"], r["JN"]) for r in rows[-3:])
            gcis.append(g)
            if g["kind"] in ("monotone", "converged", "noise") and g["gci"] < target:
                break
    return rows, gcis
