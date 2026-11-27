"""Стационарная модель горения EDM."""

import numpy as np

from ..kernels import NMU, NRO3

from . import kernels as AK

COMB_NAMES = {0: "мгновенная", 1: "вихревой распад (EDM)"}

# Постоянные моделей
L_MIX = 0.07        # масштаб турбулентности, доля диаметра камеры/предкамеры
AVG_FRAC = 0.3      # доля последних итераций для осреднения


def temperature_mode(p):
    """Модель температуры, которая на самом деле используется: при EDM -
    равновесная, умноженная на долю сгоревшего (3); иначе - выбранная
    (TMODEL: 0 - исходная, 2 - равновесная)."""
    if p.COMB == 1:
        return 3
    return int(p.TMODEL)


def describe(p):
    return "стационарный; горение - %s, турбулентность - алгебраическая" % (
        COMB_NAMES[p.COMB])


class Refined:
    """Состояние уточнённых моделей для одного варианта расчёта."""

    def __init__(self, s):
        self.s = s
        p = s.p
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
        self._avg = None
        self._avg_cnt = 0
        self.averaged = 0

    def after_viscos(self):
        s = self.s
        A = s.A
        n1, n2 = s.IN + 1, s.JN + 1
        # ε/k по алгебраической вязкости: μт = Cμ·ρ·k²/ε и
        # ε = Cμ^0.75·k^1.5/l дают ε/k = Cμ^0.5·μт/(ρ·l²)
        mu = A[:n1, :n2, NMU]
        rho = np.maximum(A[:n1, :n2, NRO3], 1e-6)
        self.EK[:n1, :n2] = AK.C_MU ** 0.5 * mu / (
            rho * self.LM[:n1, :n2] ** 2)

    def after_eqn(self):
        s = self.s
        AK.edm_step(s.A, self.INT, s.AE1, s.AW1, s.AN1, s.AS1, self.EK,
                    self.edm_a, 0.0, s.IN, s.JN)
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
        средними по последним итерациям."""
        s = self.s
        self.averaged = 0
        if (s._settled is not False or self._avg is None
                or self._avg_cnt < 50 or s._stopped):
            return
        s.A[...] = self._avg / self._avg_cnt
        self.averaged = self._avg_cnt
