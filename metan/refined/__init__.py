"""Уточнённые модели горения и турбулентности.

Выбираются в разделе «Режим», как модель температуры:

* «Модель горения» (Params.COMB):
  0 - мгновенная (исходная): брутто-реакция в узле при T ≥ Tвоспл;
  1 - вихревой распад (EDM, Магнуссен - Хьертагер): скорость горения
      ограничена турбулентным перемешиванием, w = A·ρ·(ε/k)·min(gCH4, gO2/s);
  2 - равновесная по смешению: состав и температура в узле - химическое
      равновесие (9 веществ) при его доле горючих элементов.
* «Модель турбулентности» (Params.TURB):
  0 - алгебраическая (исходная);
  1 - k–ε (Лаундер - Сполдинг) с пристеночными функциями.

Решатель подключает модели в нескольких точках итерации (Solver._iterate);
при COMB = 0 и TURB = 0 они не вызываются, и расчёт - в точности как
в основной программе.
"""

import numpy as np

from .. import thermo
from ..kernels import (NMDF, NMFU1, NMFU2, NMOX1, NMOX2, NMPR1, NMPR2, NMU,
                       NRO3, NV1)
from . import kernels as AK

COMB_NAMES = {0: "мгновенная", 1: "вихревой распад (EDM)",
              2: "равновесная по смешению"}
TURB_NAMES = {0: "алгебраическая", 1: "k–ε"}

# Постоянные моделей
L_MIX = 0.07        # масштаб турбулентности, доля диаметра камеры/предкамеры
TURB_INT = 0.05     # интенсивность турбулентности на входах
MU_LAM = 1e-4       # молекулярная вязкость газа, Па·с
RELAX_MU = 0.3      # нижняя релаксация μт (k-ε)
RELAX_EQ = 0.5      # нижняя релаксация равновесного состава
RELAX_W = 0.3       # нижняя релаксация вихря при k-ε
AVG_FRAC = 0.3      # доля последних итераций для осреднения


def temperature_mode(p):
    """Модель температуры, которая на самом деле используется: при EDM -
    равновесная, умноженная на долю сгоревшего (3); при равновесном горении -
    равновесная (2); иначе - выбранная (TMODEL)."""
    comb = int(getattr(p, "COMB", 0))
    if comb == 1:
        return 3
    if comb == 2:
        return 2
    return int(p.TMODEL)


def active(p):
    return int(getattr(p, "COMB", 0)) != 0 or int(getattr(p, "TURB", 0)) != 0


def describe(p):
    return "горение - %s, турбулентность - %s" % (
        COMB_NAMES[int(p.COMB)], TURB_NAMES[int(p.TURB)])


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


class Refined:
    """Состояние уточнённых моделей для одного варианта расчёта."""

    def __init__(self, s):
        self.s = s
        p = s.p
        self.comb = int(p.COMB)
        self.turb = int(p.TURB)
        self.edm_a = float(p.EDM_A)
        IN, JN = s.IN, s.JN
        shape = (IN + 2, JN + 2)
        INT = np.zeros(shape, dtype=np.bool_)
        for J in range(2, s.JNM + 1):
            IL, IM = int(s.IMIN[J]), int(s.IMAX[J])
            if J == s.JA3:
                IL = s.IC2 + 1
            if J == s.JC:
                IM = s.IC - 1
            INT[IL:IM + 1, J] = True
        self.INT = INT
        X2 = s.X2
        self.LM = np.zeros(shape)
        for I in range(1, IN + 1):
            self.LM[I, :] = L_MIX * 2 * (X2[s.JA3] if I <= s.IC2 else X2[JN])
        self.EK = np.zeros(shape)
        if self.turb == 1:
            self._keps_init()
        if self.comb == 2:
            fs, Ys, Ts = equilibrium_table(p.P, p.H)
            self._eq = (fs, Ys)
        self._mu_prev = None
        self._avg = None
        self._avg_cnt = 0
        self.averaged = 0

    # ------------------------------------------------------------------
    def _keps_init(self):
        s = self.s
        A, IN, JN, INT = s.A, s.IN, s.JN, self.INT
        X1, X2 = s.X1, s.X2
        shape = INT.shape
        K = np.zeros(shape)
        E = np.zeros(shape)
        KIN = np.zeros(shape)
        EIN = np.zeros(shape)
        BTYPE = np.zeros(shape, dtype=np.int64)       # 0 - не граница
        BSRC = np.zeros(shape + (2,), dtype=np.int64)
        YW = np.zeros(shape)
        cm = AK.C_MU
        vchar = max(abs(s.VINP), abs(s.VINS), abs(s.VINS1), 1.0)
        k0 = 1.5 * (TURB_INT * vchar) ** 2
        l0 = L_MIX * 2 * X2[JN]
        K[:] = k0
        E[:] = cm ** 0.75 * k0 ** 1.5 / l0
        # входы (как в INIT): центральная струя и щель горючего при I = 1,
        # щель окислителя при I = IC2
        inlets = []
        for J in range(1, s.JZ + 1):
            inlets.append((1, J, 2 * X2[s.JZ]))
        for J in range(s.JZ1, s.JA + 1):
            inlets.append((1, J, 2 * (X2[s.JA] - X2[s.JZ1])))
        for J in range(s.JA1, s.JA2 + 1):
            inlets.append((s.IC2, J, 2 * (X2[s.JA2] - X2[s.JA1])))
        inlet = np.zeros(shape, dtype=np.bool_)
        for I, J, dh in inlets:
            v = abs(A[I, J, NV1])
            k = max(1.5 * (TURB_INT * v) ** 2, 1e-4)
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

    def state(self):
        """Что нужно сохранить, чтобы «Продолжить» досчитывал с того же
        места (k и ε)."""
        if self.turb == 1:
            return dict(K=self.K.copy(), E=self.E.copy(),
                        mu=None if self._mu_prev is None
                        else self._mu_prev.copy())
        return None

    def restore(self, st):
        if st and self.turb == 1 and st["K"].shape == self.K.shape:
            self.K[...] = st["K"]
            self.E[...] = st["E"]
            self._mu_prev = st["mu"]

    # ------------------------------------------------------------------
    def after_viscos(self):
        s = self.s
        A = s.A
        n1, n2 = s.IN + 1, s.JN + 1
        if self.turb == 1:
            # нижняя релаксация вязкости: резкие изменения μт раскачивают
            # связанную систему уравнений
            old = A[:n1, :n2, NMU].copy() if self._mu_prev is None \
                else self._mu_prev
            AK.keps_viscosity(A, self.INT, self.K, self.E, s.IN, s.JN,
                              MU_LAM, 50.0)
            if s.NITER > 3:
                A[:n1, :n2, NMU] = old + RELAX_MU * (A[:n1, :n2, NMU] - old)
            self._mu_prev = A[:n1, :n2, NMU].copy()
            self.EK = self.E / np.maximum(self.K, 1e-8)
        elif self.comb == 1:
            # ε/k по алгебраической вязкости: μт = Cμ·ρ·k²/ε и
            # ε = Cμ^0.75·k^1.5/l дают ε/k = Cμ^0.5·μт/(ρ·l²)
            mu = A[:n1, :n2, NMU]
            rho = np.maximum(A[:n1, :n2, NRO3], 1e-6)
            self.EK[:n1, :n2] = AK.C_MU ** 0.5 * mu / (
                rho * self.LM[:n1, :n2] ** 2)

    def after_convec(self):
        s = self.s
        if self.turb != 1 or s.NITER < 3:
            return
        AK.production(s.A, self.INT, s.X1, s.X2, s.R, self.PK,
                      s.IN, s.JN, int(s.NCORD))
        AK.keps_step(s.A, self.INT, s.AE, s.AW, s.AN, s.AS,
                     s.AE1, s.AW1, s.AN1, s.AS1, self.PK,
                     self.K, self.E, self.YW, s.IN, s.JN, 0.6, 1e-6, 1e-4)
        AK.keps_bounds(self.K, self.E, self.INT, self.BTYPE, self.BSRC,
                       self.KIN, self.EIN, s.IN, s.JN)

    def after_eqn(self):
        s = self.s
        if self.comb == 1:
            AK.edm_step(s.A, self.INT, s.AE1, s.AW1, s.AN1, s.AS1, self.EK,
                        self.edm_a, 0.0, s.IN, s.JN)
        elif self.comb == 2:
            self._equilibrium_composition()
        # накопление полей для осреднения (если решение не установится)
        limit = getattr(s, "_limit", s.p.NMAX)
        window = int(AVG_FRAC * s.p.NMAX)
        if s.NITER > limit - window:
            if self._avg is None:
                self._avg = np.zeros_like(s.A)
                self._avg_cnt = 0
            self._avg += s.A
            self._avg_cnt += 1

    def end(self):
        """Если решение не установилось (колеблется), поля заменяются
        средними по последним итерациям - как осреднение по времени."""
        s = self.s
        self.averaged = 0
        if (s._settled is not False or self._avg is None
                or self._avg_cnt < 50 or s._stopped):
            return
        s.A[...] = self._avg / self._avg_cnt
        self.averaged = self._avg_cnt

    def _equilibrium_composition(self):
        """Состав в каждом узле - равновесный при его доле горючих
        элементов f (атомы O и H, которых нет среди 7 веществ модели,
        отнесены к O2 и H2 - элементный баланс сохраняется)."""
        s = self.s
        A = s.A
        n1, n2 = s.IN + 1, s.JN + 1
        idx = (NMFU1, NMOX1, NMPR1, NMPR2, NMOX2, NMDF, NMFU2)
        Y = A[:n1, :n2, :][:, :, list(idx)]
        prod = Y[:, :, 2:].sum(axis=2)
        fuel = Y[:, :, 0] + 0.2034 * prod
        tot = Y.sum(axis=2)
        mask = (tot > 0) & np.isfinite(tot)
        f = np.where(mask, fuel / np.where(mask, tot, 1), 0.)
        f = np.nan_to_num(np.clip(f, 0., 1.))
        fs, Ys = self._eq
        n = len(fs) - 1
        q = f * n
        k0 = np.clip(q.astype(int), 0, n - 1)
        w = (q - k0)[:, :, None]
        Yeq = Ys[k0] * (1 - w) + Ys[k0 + 1] * w           # 9 веществ
        g = {sp: Yeq[:, :, i] for i, sp in enumerate(thermo.SPECIES)}
        new = {NMFU1: g["CH4"], NMOX1: g["O2"] + g["O"], NMPR1: g["CO2"],
               NMPR2: g["H2O"], NMOX2: g["CO"], NMDF: g["H2"] + g["H"],
               NMFU2: g["OH"]}
        for k, v in new.items():
            old = A[:n1, :n2, k]
            A[:n1, :n2, k] = np.where(mask, old + RELAX_EQ * (v * tot - old),
                                      old)
