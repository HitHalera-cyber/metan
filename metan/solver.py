"""Главная программа (RK2.FOR), GRID (RK5.FOR), INIT (RK1.FOR), PRINT1 (RK7.FOR).

Использование:
    from metan import Params, Solver
    res = Solver(Params()).run()
    res.write_files("папка")
"""

import os
import time
from dataclasses import dataclass, field

import numpy as np

from . import kernels as K
from .fortran_format import fmt_e, fmt_f, fmt_i
from .kernels import (NW, NF, NMFU1, NMOX1, NMPR1, NMPR2, NMDF, NMOX2,
                      NMFU2, NMU1, NRO3, NT, NV1, NMU2, N3)
from .params import Params

# Наименования переменных массива A (для графиков и экспорта)
VAR_NAMES = {
    NW: "Вихрь ω",
    NF: "Функция тока ψ",
    NMFU1: "CH4 (массовая доля)",
    NMOX1: "O2 (массовая доля)",
    NMPR1: "CO2 (массовая доля)",
    NMPR2: "H2O (массовая доля)",
    NMDF: "H2 (массовая доля)",
    NMOX2: "CO (массовая доля)",
    NMFU2: "OH (массовая доля)",
    NMU1: "Энтальпия",
    K.NMU: "Турбулентная вязкость",
    NRO3: "Плотность, кг/м³",
    NT: "Температура, K",
    NV1: "Скорость V1 (осевая), м/с",
    K.NV2: "Скорость V2 (радиальная), м/с",
    NMU2: "Закрутка r·W",
}


class Cancelled(Exception):
    pass


@dataclass
class VariantResult:
    """Результаты одного варианта (одного значения ALFA)."""
    NVAR: int
    values: dict                    # P, ALFA, KM, BETA, Ms, ... (как в shi10.dat)
    grid: dict                      # JZ, JZ1, ..., IN
    geometry: dict                  # Dks, Lks, ... (в метрах)
    NITER: int
    fkomp_kind: str                 # "OK" или "GOR"
    fkomp: float
    extra: dict                     # величины, которые оригинал считал, но не печатал
    A: np.ndarray                   # поля A[i, j, k] после расчёта
    X1: np.ndarray
    X2: np.ndarray
    IMIN: np.ndarray
    IMAX: np.ndarray
    diverged: bool = False
    # История сходимости: {"iter": [...], "omega": [...], "psi": [...],
    # "T": [...], "CH4": [...]} - макс. изменение за итерацию (отн.)
    history: dict = field(default_factory=dict)
    # Кадры для анимации: [(NITER, A float32), ...]
    snapshots: list = field(default_factory=list)


@dataclass
class Results:
    params: Params
    variants: list = field(default_factory=list)
    text10: list = field(default_factory=list)   # строки shi10.dat
    text20: list = field(default_factory=list)   # строки shi20.dat
    elapsed: float = 0.0

    def write_files(self, outdir="."):
        os.makedirs(outdir, exist_ok=True)
        p10 = os.path.join(outdir, self.params.out10)
        p20 = os.path.join(outdir, self.params.out20)
        with open(p10, "w", newline="\n") as fh:
            fh.write("".join(s + "\n" for s in self.text10))
        with open(p20, "w", newline="\n") as fh:
            fh.write("".join(s + "\n" for s in self.text20))
        return p10, p20


class Solver:
    """Расчёт по программе met21 (RK1-RK7.FOR).

    progress(nvar, nvarm, niter, nmax) вызывается во время итераций;
    cancel() -> True прерывает расчёт (исключение Cancelled).
    """

    def __init__(self, params=None, progress=None, cancel=None,
                 progress_every=10, track_history=True, snapshot_every=0):
        self.p = (params or Params()).validate()
        self.progress = progress
        self.cancel = cancel
        self.progress_every = progress_every
        self.track_history = track_history
        self.snapshot_every = snapshot_every
        self.F = np.float32 if self.p.precision == "float32" else np.float64

    # ------------------------------------------------------------------
    def _alloc(self):
        p, F = self.p, self.F
        dt = F
        self.IN, self.JN = p.IN, p.JN
        self.INM, self.JNM = p.IN - 1, p.JN - 1
        n1, n2 = p.IN + 1, p.JN + 1
        self.A = np.zeros((n1, n2, N3 + 1), dtype=dt)
        for name in ("AE", "AW", "AN", "AS", "VS", "FKS", "TKS",
                     "AE1", "AW1", "AN1", "AS1", "UKS"):
            setattr(self, name, np.zeros((n1, n2), dtype=dt))
        self.BE = np.zeros(n1, dtype=dt)
        self.BW = np.zeros(n1, dtype=dt)
        self.BN = np.zeros(n2, dtype=dt)
        self.BS = np.zeros(n2, dtype=dt)
        self.X1 = np.zeros(n1, dtype=dt)
        self.X2 = np.zeros(n2, dtype=dt)
        self.R = np.zeros(n2, dtype=dt)
        self.PKS = np.zeros(n1, dtype=dt)
        self.RSDU = np.zeros(13, dtype=dt)
        self.IMIN = np.zeros(n2, dtype=np.int64)
        self.IMAX = np.zeros(n2, dtype=np.int64)
        # Целочисленные индексы (DATA в RK1.FOR)
        self.JZ, self.JZ1, self.JA, self.JA3 = p.JZ, p.JZ1, p.JA, p.JA3
        self.JA1, self.JA2, self.JC, self.IC = p.JA1, p.JA2, p.JC, p.IC
        self.IC1, self.IC2 = p.IC1, p.IC2
        self.JB1 = p.JN
        self.JB = p.JN - 1
        self.JC1 = p.JC + 1
        self.NCORD = p.NCORD
        # Вещественные величины (тип - выбранной точности)
        self.P, self.H = F(p.P), F(p.H)
        self.ROM1, self.AKT = F(p.ROM1), F(p.AKT)
        self.ZMF2N, self.ZMO2N = F(p.ZMF2N), F(p.ZMO2N)
        self.ALFA = F(p.ALFA)
        self.DALFA = F(p.DALFA)
        for name in ("DKR", "DCMB", "DOGOR", "DELGOR", "DKAR", "DOOK", "DELOK",
                     "DKS", "DELKAR", "ALKS", "ALKD", "TGY"):
            setattr(self, name, F(getattr(p, name)))
        # Перезаписываются до использования; начальные значения из DATA
        self.VINP, self.VINS = F(9.329155), F(26.03549)
        self.ROP, self.ROS = F(6.458), F(12.916)
        self.VINS1 = F(2.e-3)

    # ------------------------------------------------------------------
    def grid(self):
        """SUBROUTINE GRID (RK5.FOR)."""
        X1, X2, R = self.X1, self.X2, self.R
        JZ, JZ1, JA, JA3, JA1, JA2 = (self.JZ, self.JZ1, self.JA, self.JA3,
                                      self.JA1, self.JA2)
        IN, JN, IC2 = self.IN, self.JN, self.IC2
        X2[JZ] = self.DCMB / 2.
        X2[JZ1] = self.DOGOR / 2.
        X2[JA] = self.DELGOR + X2[JZ1]
        X2[JA3] = self.DKAR / 2.
        X2[JA1] = self.DOOK / 2.
        X2[JA2] = self.DELOK + X2[JA1]
        X2[JN] = self.DKS / 2.
        X1[IC2] = self.DELKAR
        X1[self.IC1] = X1[IC2] + self.ALKS
        X1[self.IC] = self.ALKD
        for J in range(2, JZ + 1):
            X2[J] = X2[J - 1] + X2[JZ] / (JZ - 1)
        for J in range(JZ + 1, JZ1 + 1):
            X2[J] = X2[J - 1] + (X2[JZ1] - X2[JZ]) / (JZ1 - JZ)
        for J in range(JZ1 + 1, JA + 1):
            X2[J] = X2[J - 1] + (X2[JA] - X2[JZ1]) / (JA - JZ1)
        for J in range(JA + 1, JA3 + 1):
            X2[J] = X2[J - 1] + (X2[JA3] - X2[JA]) / (JA3 - JA)
        for J in range(JA3 + 1, JA1 + 1):
            X2[J] = X2[J - 1] + (X2[JA1] - X2[JA3]) / (JA1 - JA3)
        for J in range(JA1 + 1, JA2 + 1):
            X2[J] = X2[J - 1] + (X2[JA2] - X2[JA1]) / (JA2 - JA1)
        for J in range(JA2 + 1, JN + 1):
            X2[J] = X2[J - 1] + (X2[JN] - X2[JA2]) / (JN - JA2)
        # Поиск узла критического сечения: первый J, где X2(J) >= DKR/2
        J = JN + 1
        for jj in range(2, JN + 1):
            XX2 = self.DKR / 2. - X2[jj]
            if XX2 <= 0.:
                J = jj
                break
        if J > JN:
            raise ValueError("GRID: критическое сечение Dkr/2 не попадает в "
                             "сетку по радиусу (Dkr больше Dks?)")
        JJ = J
        KJ = JJ - self.JC
        self.JC = JJ
        self.IC = self.IC - KJ
        self.JB1 = JN
        self.JB = self.JB1 - 1
        self.JC1 = self.JC + 1
        X2[self.JC] = self.DKR / 2.
        self.IC1 = self.IC - (JN - self.JC)
        IC, IC1 = self.IC, self.IC1
        if not (IC2 < IC1 < IC < IN):
            raise ValueError("GRID: получилось IC2=%d, IC1=%d, IC=%d, IN=%d; "
                             "нужно IC2 < IC1 < IC < IN. Проверьте IC и JN."
                             % (IC2, IC1, IC, IN))
        for I in range(2, IC2 + 1):
            X1[I] = X1[I - 1] + X1[IC2] / (IC2 - 1)
        X1[IC1] = X1[IC2] + self.ALKS
        for I in range(IC2 + 1, IC1 + 1):
            X1[I] = X1[I - 1] + (X1[IC1] - X1[IC2]) / (IC1 - IC2)
        for I in range(IC1 + 1, IC + 1):
            LK = JN - I + IC1
            X1[I] = X1[IC1] + (X2[JN] - X2[LK]) / self.TGY
        for I in range(IC + 1, IN + 1):
            XZ1 = self.F(1.)
            if self.NVAR != 1:
                XZ1 = self.F(1.e-3)
            X1[I] = X1[I - 1] + XZ1 / (IN - IC)
        if self.NVAR == 1:
            # мм -> м (только в первом варианте; дальше размеры уже в метрах)
            for J in range(1, JN + 1):
                X2[J] = X2[J] * 0.001
            for I in range(1, IN + 1):
                X1[I] = X1[I] * 0.001
        if self.NCORD == 1:
            R[1:JN + 1] = 1.
        else:
            R[1:JN + 1] = X2[1:JN + 1]
        for I in range(2, self.INM + 1):
            DX1 = 1. / (X1[I + 1] - X1[I - 1])
            self.BW[I] = DX1 / (X1[I] - X1[I - 1])
            self.BE[I] = DX1 / (X1[I + 1] - X1[I])
        for J in range(2, self.JNM + 1):
            DX2 = 0.5 / (X2[J + 1] - X2[J - 1])
            self.BS[J] = (1. + R[J - 1] / R[J]) / (X2[J] - X2[J - 1]) * DX2
            self.BN[J] = (1. + R[J + 1] / R[J]) / (X2[J + 1] - X2[J]) * DX2
        for name in ("AE", "AW", "AN", "AS", "AE1", "AW1", "AN1", "AS1",
                     "UKS", "VS", "FKS", "TKS"):
            getattr(self, name)[:] = 0.
        self.A[:] = 0.

    # ------------------------------------------------------------------
    def init(self):
        """SUBROUTINE INIT (RK1.FOR): граничные и начальные условия."""
        A, R, X2 = self.A, self.R, self.X2
        IMIN, IMAX = self.IMIN, self.IMAX
        IN, JN, JNM = self.IN, self.JN, self.JNM
        JZ, JZ1, JA, JA1, JA2, JA3 = (self.JZ, self.JZ1, self.JA, self.JA1,
                                      self.JA2, self.JA3)
        JC, JC1, JB, IC, IC2 = self.JC, self.JC1, self.JB, self.IC, self.IC2
        VINS, VINP, ROS, ROP, VINS1 = (self.VINS, self.VINP, self.ROS,
                                       self.ROP, self.VINS1)
        H, P, NCORD = self.H, self.P, self.NCORD

        for J in range(1, JA3 + 1):
            IMIN[J] = 2
        for J in range(JA3 + 1, JN + 1):
            IMIN[J] = IC2 + 1
        for J in range(1, JC + 1):
            IMAX[J] = IN - 1
        for J in range(JC1, JN + 1):
            IMAX[J] = IC - 1 + JC - J
        # DO 64: вход окислителя
        for J in range(JA1, JA2 + 1):
            A[IC2, J, NV1] = VINS
            A[IC2, J, NMFU1] = 0.0
            A[IC2, J, NRO3] = ROS
            A[IC2, J, NMOX1] = self.ZMO2N
            A[IC2, J, NT] = 298.
            A[IC2, J, NMU1] = 0.0
            if NCORD == 2:
                A[IC2, J, NF] = ROS * VINS * (R[J] - R[JA2]) * 0.5 * (R[J] + R[JA2])
            if NCORD == 1:
                A[IC2, J, NF] = A[IC2, JA2, NF] - ROS * VINS * (X2[JA2] - X2[J])
        A[IC2, JA2, NV1] = 0.
        for J in range(JA3, JA1 + 1):
            A[IC2, J, NF] = A[IC2, JA1, NF]
        for I in range(1, IC2 + 1):
            A[I, JA3, NF] = A[IC2, JA3, NF]
        A[IC2, JA1, NV1] = 0.
        for J in range(JA, JA3 + 1):
            A[1, J, NF] = A[1, JA3, NF]
        # DO 61: вход горючего
        for J in range(JZ1, JA + 1):
            A[1, J, NV1] = VINP
            A[1, J, NMU2] = VINP * R[J] ** 2 / R[JA] * 1.5
            A[1, J, NMOX1] = 0.0
            A[1, J, NMFU1] = self.ZMF2N
            A[1, J, NRO3] = ROP
            A[1, J, NT] = 298.
            A[1, J, NMU1] = H
            if NCORD == 2:
                A[1, J, NF] = A[1, JA, NF] + ROP * VINP * (R[J] - R[JA]) * 0.5 * \
                    (R[J] + R[JA])
            if NCORD == 1:
                A[1, J, NF] = A[1, JA, NF] + ROP * VINP * (X2[J] - X2[JA])
        A[1, JA, NV1] = 0.
        A[1, JZ1, NV1] = 0.
        for J in range(JZ, JZ1 + 1):
            A[1, J, NF] = A[1, JZ1, NF]
        # DO 3011: центральная струя
        for J in range(1, JZ + 1):
            A[1, J, NT] = 298.
            A[1, J, NV1] = VINS1
            A[1, J, NMOX1] = 1.
            A[1, J, NRO3] = 1. / (A[1, J, NMFU1] / 16. + A[1, J, NMOX1] / 32.
                                  + A[1, J, NMPR1] / 44. + A[1, J, NMOX2] / 28.
                                  + A[1, J, NMPR2] / 18. + A[1, J, NMFU2] / 17.
                                  + A[1, J, NMDF] / 2.)
            A[1, J, NRO3] = P * A[1, J, NRO3] / 8314.4 / A[1, J, NT]
            if NCORD == 2:
                A[1, J, NF] = A[1, JZ, NF] + VINS1 * A[1, J, NRO3] * \
                    (R[J] - R[JZ]) * 0.5 * (R[J] + R[JZ])
        for I in range(1, IN + 1):
            A[I, 1, NF] = A[1, 1, NF]
        A[1, JZ, NV1] = 0.

        def irange(J, il_shift):
            IL = IMIN[J] + il_shift
            IM = IMAX[J] + 1
            if J <= JC:
                IM = IN
            if J == JC1 or J == JB:
                IM = IMAX[J] + 1
            return range(IL, IM + 1)

        for J in range(JZ1, JA + 1):                     # DO 465
            for I in irange(J, 0):
                A[I, J, NMFU1] = 1.0
                A[I, J, NMOX1] = 0.0
                A[I, J, NRO3] = ROP
                A[I, J, NT] = 298.
                A[I, J, NMU1] = H
        for J in range(JA + 1, JA1):                     # DO 65
            for I in irange(J, -1):
                A[I, J, NMOX1] = 1.0
                A[I, J, NMFU2] = 0.0
                A[I, J, NRO3] = ROS
                A[I, J, NT] = 298.
                A[I, J, NMFU1] = 0.0
                A[I, J, NMU1] = H / 100.
        for J in range(JA1, JN + 1):                     # DO 165
            for I in irange(J, 0):
                A[I, J, NMFU1] = 0.0
                A[I, J, NT] = 298.
                A[I, J, NRO3] = ROS
                A[I, J, NMFU2] = 0.0
                A[I, J, NMOX1] = 1.0
                A[I, J, NMU1] = H / 100.
        for J in range(1, JZ + 1):                       # DO 308
            for I in irange(J, 0):
                A[I, J, NMOX1] = A[1, J, NMOX1]
                A[I, J, NRO3] = A[1, J, NRO3]
                A[I, J, NMU1] = A[1, J, NMU1]
                A[I, J, NMPR1] = A[1, J, NMPR1]
                A[I, J, NMPR2] = A[1, J, NMPR2]
                A[I, J, NMFU1] = A[1, J, NMFU1]
                A[I, J, NT] = self.ROM1 + 10.
        for J in range(JZ + 1, JZ1):                     # DO 310
            for I in irange(J, -1):
                A[I, J, NMOX1] = 0.0
                A[I, J, NMFU1] = 1.0
                A[I, J, NRO3] = ROP
                A[I, J, NMU1] = H
                A[I, J, NT] = 298.
        for J in range(2, JA3):                          # DO 301
            IL = IMIN[J]
            IM = IMAX[J]
            if J == JC:
                IM = IC - 1
            for I in range(IL, IM + 1):
                A[I, J, NF] = A[1, J, NF]
        for J in range(JA3, JNM + 1):                    # DO 33
            IL = IMIN[J]
            IM = IMAX[J]
            if J == JC:
                IM = IC - 1
            if J == JA3:
                IL = IC2 + 1
            for I in range(IL, IM + 1):
                A[I, J, NF] = A[IC2, J, NF]

    # ------------------------------------------------------------------
    def _iterate(self):
        """Итерационный цикл варианта (метка 1 в RK2.FOR)."""
        p = self.p
        self.NITER = 0
        last_cb = 0.0
        self._hist = {"iter": [], "omega": [], "psi": [], "T": [], "CH4": []}
        self._snaps = []
        prev = self.A[:, :, (NW, NF, NT, NMFU1)].copy() if self.track_history \
            else None
        while True:
            self.NITER += 1
            K.viscos(self.A, self.X1, self.R, self.IMIN, self.IMAX, self.PKS,
                     self.IN, self.JN, self.JA, self.JZ, self.JZ1, self.JA1,
                     self.JA2, self.JA3, self.JC, self.IC1, self.IC2,
                     self.VINP, self.VINS, self.ROP, self.ROS, self.VINS1)
            self.NITER = K.veldis(self.A, self.X1, self.X2, self.R, self.IMIN,
                                  self.IMAX, self.VS, self.FKS, self.UKS,
                                  self.INM, self.JNM, self.JA3, self.JC,
                                  self.IC, self.IC2, self.NITER)
            K.convec(self.A, self.X1, self.X2, self.R, self.IMIN, self.IMAX,
                     self.BE, self.BW, self.BN, self.BS,
                     self.AE, self.AW, self.AN, self.AS,
                     self.AE1, self.AW1, self.AN1, self.AS1,
                     self.JNM, self.JA3, self.JC, self.IC, self.IC2)
            K.eqn(self.A, self.X1, self.X2, self.R, self.IMIN, self.IMAX,
                  self.BE, self.BW, self.BN, self.BS,
                  self.AE, self.AW, self.AN, self.AS,
                  self.AE1, self.AW1, self.AN1, self.AS1,
                  self.UKS, self.FKS, self.TKS, self.RSDU,
                  self.IN, self.INM, self.JN, self.JNM, self.JA, self.JA1,
                  self.JA2, self.JA3, self.JB, self.JB1, self.JC, self.JC1,
                  self.JZ, self.JZ1, self.IC, self.IC1, self.IC2,
                  self.NITER, p.NPRINT, self.NVAR, self.NCORD, self.ROM1,
                  self.IC2 + 1)
            if self.track_history:
                self._record(prev)
            if (self.snapshot_every and self.NITER <= p.NMAX
                    and (self.NITER % self.snapshot_every == 0
                         or self.NITER == 1)):
                self._snaps.append((self.NITER, self.A.astype(np.float32)))
            if self.cancel is not None and self.cancel():
                raise Cancelled()
            if self.progress is not None and (
                    self.NITER % self.progress_every == 0
                    or self.NITER >= p.NMAX):
                now = time.monotonic()
                if now - last_cb > 0.05 or self.NITER >= p.NMAX:
                    last_cb = now
                    self.progress(self.NVAR, p.NVARM, min(self.NITER, p.NMAX),
                                  p.NMAX)
            if self.NITER >= p.NMAX:
                break

    _HKEYS = (("omega", 0), ("psi", 1), ("T", 2), ("CH4", 3))

    def _record(self, prev):
        cur = self.A[:, :, (NW, NF, NT, NMFU1)]
        h = self._hist
        h["iter"].append(self.NITER)
        for name, n in self._HKEYS:
            a, b = cur[:, :, n], prev[:, :, n]
            scale = float(np.max(np.abs(a)))
            d = float(np.max(np.abs(a - b)))
            h[name].append(d / scale if scale > 0 else d)
        prev[...] = cur

    # ------------------------------------------------------------------
    def preview(self):
        """Сетка и начальное поле 1-го варианта без расчёта (для проверки
        геометрии). Возвращает VariantResult с NITER=0."""
        with np.errstate(all="ignore"):
            self._alloc()
            self.NVAR = 1
            return self._variant(None, preview=True)

    # ------------------------------------------------------------------
    def run(self):
        t0 = time.monotonic()
        p = self.p
        res = Results(params=p)
        with np.errstate(all="ignore"):
            self._alloc()
            self.NVAR = 0
            while True:
                self.NVAR += 1
                self._variant(res)
                if self.NVAR == p.NVARM:      # IF(NVAR.NE.NVARM) GO TO 90
                    break
        res.elapsed = time.monotonic() - t0
        return res

    # ------------------------------------------------------------------
    def _variant(self, res, preview=False):
        """Один проход от метки 90 до GO TO 90 в RK2.FOR."""
        F = self.F
        A, X1, X2, R, PKS = self.A, self.X1, self.X2, self.R, self.PKS
        IN, JN, INM = self.IN, self.JN, self.INM
        P, AKT = self.P, self.AKT

        self.ALFA = self.ALFA + self.DALFA
        ALFA = self.ALFA
        self.grid()
        JC, IC, IC1, IC2 = self.JC, self.IC, self.IC1, self.IC2
        JZ, JZ1, JA, JA1, JA2, JA3, JB1 = (self.JZ, self.JZ1, self.JA,
                                           self.JA1, self.JA2, self.JA3,
                                           self.JB1)

        C = 3.14 * self.DOOK * self.DELOK
        S1 = 0.785 * self.DCMB ** 2
        G1 = 3.14 * self.DOGOR * self.DELGOR
        # Давление по длине камеры и сопла (одномерная газодинамика)
        for I in range(1, IN + 1):
            PKS[I] = P
            if I < IC1:
                continue
            JL = JC + IC - I
            DSS = X2[JL] * 2
            FSS = 3.14 / 4. * DSS ** 2
            FSKR = 3.14 * X2[JC] ** 2
            FOS = FSS / FSKR
            if FOS <= 1.:
                FOS = F(1.)
            FA2 = 1. / FOS
            APR = (2. / (AKT + 1.)) ** (AKT / (AKT - 1.)) * P
            AP2 = APR / P
            AP1 = F(1.)
            NIT = 0
            while True:
                NIT += 1
                Z1 = AP1
                Z2 = AP2
                APQ = (Z1 + Z2) / 2.
                ZAP1 = (2. / (AKT + 1)) ** ((AKT + 1.) / (2. * (AKT - 1.)))
                ZAP2 = ((AKT - 1.) / 2.) ** 0.5
                ZAP3 = (1. / APQ) ** (1. / AKT)
                ZAP4 = (1. - APQ ** ((AKT - 1.) / AKT)) ** 0.5
                FA1 = 1. / (ZAP1 * ZAP2 * ZAP3 / ZAP4)
                FZ = FA2 - FA1
                if abs(FZ) <= 1.e-6:
                    break
                if NIT > 1.e+4:
                    break
                if FA2 <= FA1:
                    AP2 = APQ
                if FA2 >= FA1:
                    AP1 = APQ
            PKS[I] = APQ * P
            if I > IC:
                PKS[I] = PKS[IC]
        APZ = P - PKS[IC1]
        for I in range(2, IC1 + 1):
            PKS[I] = P - APZ * X1[I] / X1[IC1]

        # Стехиометрический комплекс BETA(ALFA)
        BETA = F(0.)
        if ALFA <= 1.:
            BETA = 1794. + 491.252 * ALFA - 475.9317 * ALFA ** 2
        if ALFA > 1.:
            BETA = 2154.733 - 402.252 * ALFA + 54.1698 * ALFA ** 2
        if ALFA < 0.6:
            BETA = 1917. - 2500. * (0.6 - ALFA)
        if BETA < 600.:
            BETA = F(600.)
        # (таблица ALFA/BETA по меткам 91-99 в оригинале обходится GO TO 145)

        # 145: расходы и скорости на входе
        self.DKR = 2. * X2[JC]
        AKM = 4. * ALFA
        FKR = self.DKR ** 2 * 3.14 / 4.
        AMS = P * FKR / BETA
        AMG = AMS / (1 + AKM)
        AMO = AMG * AKM
        AMO2 = AMO
        self.ROS = ROS = P / 77427.4
        self.ROP = ROP = P / 154855.7
        AKW = S1 / (C + S1)
        AMS1 = AKW * AMO
        self.VINS1 = VINS1 = AMS1 / (ROS * 3.14 * R[JZ] ** 2)
        AMO1 = AMS1
        AMG1 = F(0.)
        self.VINS = VINS = (AMO - AMO1) / ROS / (3.14 * (R[JA2] ** 2 - R[JA1] ** 2))
        self.VINP = VINP = (AMG - AMG1) / ROP / (3.14 * (R[JA] ** 2 - R[JZ1] ** 2))
        # Геометрия в метрах (используется GRID в следующих вариантах)
        self.DKS = X2[JB1] * 2.
        self.ALKS = X1[IC1] - X1[IC2]
        self.ALKD = X1[IC]
        ALPRIW = (R[JA3] ** 2 * X1[IC2]
                  + (R[JB1] ** 2 - R[JC] ** 2) * (X1[IC1] - X1[IC2])
                  + (R[JB1] ** 2 - R[JC] ** 2) * (X1[IC] - X1[IC1]) / 3.
                  + R[JC] ** 2 * (X1[IC] - X1[IC2])) / R[JC] ** 2
        self.TGY = (X2[JN] - X2[JC]) / (X1[IC] - X1[IC1])
        self.DKAR = X2[JA3] * 2.
        self.DELKAR = X1[IC2]
        self.DOOK = X2[JA1] * 2.
        self.DELOK = X2[JA2] - X2[JA1]
        self.DOGOR = X2[JZ1] * 2.
        self.DELGOR = X2[JA] - X2[JZ1]
        self.DCMB = X2[JZ] * 2.

        self.init()
        VR = A[1, JZ1 + 1, NMU2] / R[JZ1 + 1]
        if preview:
            return VariantResult(
                NVAR=1, values=dict(P=float(P), ALFA=float(ALFA), KM=float(AKM),
                                    BETA=float(BETA), Ms=float(AMS),
                                    Mok=float(AMO), Mgor=float(AMG),
                                    Vgor=float(VINP), Vok=float(VINS),
                                    Vcmw=float(VINS1)),
                grid=dict(JZ=JZ, JZ1=JZ1, JA=JA, JA1=JA1, JA2=JA2, JA3=JA3,
                          JC=JC, JN=JN, IC=IC, IC1=IC1, IC2=IC2, IN=IN),
                geometry=dict(Dks=float(self.DKS), Lks=float(self.ALKS),
                              Dkr=float(self.DKR), tgY=float(self.TGY),
                              Dprk=float(self.DKAR), Lprk=float(self.DELKAR),
                              Dook=float(self.DOOK), DELOK=float(self.DELOK),
                              DOGOR=float(self.DOGOR), DELGOR=float(self.DELGOR),
                              Dcmw=float(self.DCMB), Lpriw=float(ALPRIW),
                              Fod=float(C), Fcmb=float(S1), Fgor=float(G1),
                              Kwosp=float(AKW)),
                NITER=0, fkomp_kind="", fkomp=float("nan"), extra={},
                A=A.copy(), X1=X1.copy(), X2=X2.copy(), IMIN=self.IMIN.copy(),
                IMAX=self.IMAX.copy())

        out = res.text10
        out.append("0" + " " * 25 + "RASHET N" + fmt_i(self.NVAR, 4))
        out.append(
            " P=" + fmt_e(P, 11, 4) + " ALFA=" + fmt_f(ALFA, 6, 2)
            + " KM=" + fmt_f(AKM, 6, 2) + " BETA=" + fmt_f(BETA, 6, 1)
            + " Ms=" + fmt_e(AMS, 11, 4) + " Mok=" + fmt_e(AMO, 11, 4)
            + " Mgor=" + fmt_e(AMG, 11, 4) + " Vgor=" + fmt_f(VINP, 6, 1)
            + " Vok=" + fmt_f(VINS, 6, 1) + " ROg=" + fmt_f(ROP, 6, 1)
            + " ROok=" + fmt_f(ROS, 6, 1) + " Vokr=" + fmt_f(VR, 6, 1)
            + " Vcmw=" + fmt_f(VINS1, 6, 1) + " Mcmw=" + fmt_e(AMS1, 11, 4))
        out.append(
            " JZ=" + fmt_i(JZ, 3) + " JZ1=" + fmt_i(JZ1, 3)
            + " JA= " + fmt_i(JA, 3) + " JA1=" + fmt_i(JA1, 3)
            + " JA2=" + fmt_i(JA2, 3) + " JA3=" + fmt_i(JA3, 3)
            + " JC=" + fmt_i(JC, 3) + " JN=" + fmt_i(JN, 3)
            + " IC=" + fmt_i(IC, 3) + " IC1=" + fmt_i(IC1, 3)
            + " IC2=" + fmt_i(IC2, 3) + " IN=" + fmt_i(IN, 3))
        geom = [("Dks", self.DKS), ("Lks", self.ALKS), ("Lkd", self.ALKD),
                ("Dkr", self.DKR), ("tgY", self.TGY), ("Dprk", self.DKAR),
                ("Lprk", self.DELKAR), ("Dook", self.DOOK),
                ("DELOK", self.DELOK), ("DOGOR", self.DOGOR),
                ("DELGOR", self.DELGOR), ("Dcmw", self.DCMB),
                ("Lpriw", ALPRIW), ("Fod", C), ("Fcmb", S1), ("Fgor", G1),
                ("Kwosp", AKW)]
        line = ""
        for name, val in geom:
            if name == "tgY":
                line += " tgY=" + fmt_f(val, 6, 1)
            else:
                line += " " + name + "=" + fmt_e(val, 11, 4)
        out.append(line)

        self._iterate()
        out.append(" " * 25 + "NITER=" + fmt_i(self.NITER, 4))

        # 1000: коэффициент полноты сгорания
        JC17 = JC - 1
        extra = {}
        if not (ALFA <= 1.):
            ZGCP = F(0.)
            ZHP = F(0.)
            for J in range(2, JC17 + 1):
                ZHP = ZHP + A[IN, J, NMU1] * (A[IN, J + 1, NF] - A[IN, J - 1, NF]) / 2.
                ZGCP = ZGCP + A[IN, J, NMFU1] * (A[IN, J + 1, NF] - A[IN, J - 1, NF]) / 2.
            ZGCP = ZGCP + A[IN, 1, NMFU1] * (A[IN, 2, NF] - A[IN, 1, NF]) / 2. + \
                A[IN, JC, NMFU1] * (A[IN, JC, NF] - A[IN, JC17, NF]) / 2.
            ZGCP = ZGCP / ((A[1, JA, NF] - A[1, JZ1, NF]) + 0.013833 *
                           (A[1, JZ, NF] - A[1, 1, NF]))
            ZHP = ZHP / (A[1, JC, NF] - A[1, 1, NF])
            if abs(ZGCP) > 1:
                ZGCP = F(1.)
            fk = (1. - abs(ZGCP)) ** 0.5
            kind = "GOR"
            extra["ZHP"] = float(ZHP)
            out.append(" ************* KOEF Fkomp (GOR) =" + fmt_f(fk, 8, 5)
                       + " **********")
        else:
            ZGCP = F(0.)
            for J in range(2, JC17 + 1):
                ZGCP = ZGCP + A[IN, J, NMFU1] * (A[IN, J + 1, NF] - A[IN, J - 1, NF]) / 2.
            ZGCP = ZGCP + A[IN, 1, NMFU1] * (A[IN, 2, NF] - A[IN, 1, NF]) / 2. + \
                A[IN, JC, NMFU1] * (A[IN, JC, NF] - A[IN, JC17, NF]) / 2.
            AMZ = AMG - AMO2 / 4.
            ZGCP = (ZGCP - AMZ / 6.28) / ((AMG - AMZ) / 6.28)
            if abs(ZGCP) > 1.:
                ZGCP = F(1.)
            fk = (1. - abs(ZGCP)) ** 0.5
            kind = "OK"
            out.append(" ************* KOEF Fkomp (OK) =" + fmt_f(fk, 8, 5)
                       + "***********")

        # 29: FIbeta - расчётный комплекс по выходному сечению
        Z = F(0.)
        BETAJ = F(0.)
        for J in range(2, JC + 1):
            IL = INM
            ZO = (A[IL, J - 1, NMOX1] + 4.27 * A[IL, J - 1, NMPR1]
                  + 3.35 * A[IL, J - 1, NMOX2] + 376. * A[IL, J - 1, NMDF]
                  + 2.785 * A[IL, J - 1, NMPR2] + 2.765 * A[IL, J - 1, NMFU2])
            ZG = (A[IL, J - 1, NMFU1] + 1.09 * A[IL, J - 1, NMPR1]
                  + 0.857 * A[IL, J - 1, NMOX2] + 96. * A[IL, J - 1, NMDF]
                  + 0.711 * A[IL, J - 1, NMPR2] + 0.706 * A[IL, J - 1, NMFU2])
            ALFAJ = ZO / ZG / 3.9166
            if ALFAJ <= 1.:
                BETAJ = 1794. + 491.252 * ALFAJ - 475.9317 * ALFAJ ** 2
            if ALFAJ > 1.:
                BETAJ = 2154. - 402.252 * ALFAJ + 54.1698 * ALFAJ ** 2
            if ALFAJ < 0.6:
                BETAJ = 1917. - 2500. * (0.6 - ALFAJ)
            if BETAJ < 600.:
                BETAJ = F(600.)
            ZF = (A[IL, J, NF] - A[IL, J - 1, NF]) / (A[IL, JC, NF] - A[IL, 1, NF])
            Z = Z + BETAJ * ZF
        FICM = Z / BETA

        self._print1(res.text20)

        FIOP = A[1, JA, NF] - A[1, JZ1, NF] + 0.013833 * (A[1, JZ, NF] - A[1, 1, NF])
        FIOS = A[IC2, JA2, NF] - A[IC2, JA1, NF] + 0.986167 * \
            (A[1, JZ, NF] - A[1, 1, NF])
        FIOP = FIOP * 3.1416 * 2.
        FIOS = FIOS * 3.1416 * 2.
        DOP = FIOS / FIOP
        extra.update(FIbeta=float(FICM), FIOP=float(FIOP), FIOS=float(FIOS),
                     DOP=float(DOP))

        values = dict(P=float(P), ALFA=float(ALFA), KM=float(AKM),
                      BETA=float(BETA), Ms=float(AMS), Mok=float(AMO),
                      Mgor=float(AMG), Vgor=float(VINP), Vok=float(VINS),
                      ROg=float(ROP), ROok=float(ROS), Vokr=float(VR),
                      Vcmw=float(VINS1), Mcmw=float(AMS1))
        grid = dict(JZ=JZ, JZ1=JZ1, JA=JA, JA1=JA1, JA2=JA2, JA3=JA3, JC=JC,
                    JN=JN, IC=IC, IC1=IC1, IC2=IC2, IN=IN)
        res.variants.append(VariantResult(
            NVAR=self.NVAR, values=values, grid=grid,
            geometry={k: float(v) for k, v in geom}, NITER=self.NITER,
            fkomp_kind=kind, fkomp=float(fk), extra=extra,
            A=A.copy(), X1=X1.copy(), X2=X2.copy(),
            IMIN=self.IMIN.copy(), IMAX=self.IMAX.copy(),
            diverged=self.NITER > self.p.NMAX,
            history={k: np.asarray(v) for k, v in self._hist.items()},
            snapshots=self._snaps))

    def _print1(self, out):
        """SUBROUTINE PRINT1 (RK7.FOR): поля K=1..4 и координаты в shi20.dat."""
        A, X1, X2 = self.A, self.X1, self.X2
        out.append("0" + " " * 5 + "".join(fmt_i(k, 2) + " " * 9
                                            for k in range(2, 7))
                   + "X1(I)" + " " * 6 + "X2(J)")
        for J in range(1, self.JN + 1):
            for I in range(1, self.IN + 1):
                out.append("  " + "".join(fmt_e(A[I, J, k], 11, 3)
                                          for k in range(1, 5))
                           + fmt_e(X1[I], 11, 3) + fmt_e(X2[J], 11, 3))
