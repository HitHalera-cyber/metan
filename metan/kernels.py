"""Вычислительное ядро: построчный перевод подпрограмм VISCOS (RK4.FOR),
VELDIS и CONVEC (RK5.FOR), EQN (RK3.FOR), SORCE (RK6.FOR), BOUND (RK7.FOR).

Соглашения:
  * индексация как в Фортране - с 1 (элемент 0 массивов не используется);
  * A[i, j, k] - то же, что A(I,J,K) в Фортране;
  * порядок обхода узлов и все ветвления (GO TO) сохранены, т.к. схема
    Гаусса-Зейделя зависит от порядка обновления узлов.

Если установлен numba, функции компилируются в машинный код (скорость
порядка Фортрана). Без numba программа работает, но очень медленно.
"""

import math
import sys

try:
    from numba import njit as _njit

    # В собранном .exe исходников нет, кэш numba там не работает.
    _CACHE = not getattr(sys, "frozen", False)

    def jit(f):
        return _njit(cache=_CACHE, nogil=True)(f)

    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    def jit(f):
        return f

    HAVE_NUMBA = False

# Номера переменных в массиве A (COMMON/CNUMBR/, DATA в RK1.FOR)
NW = 1      # напряжённость вихря
NF = 2      # функция тока
NMFU1 = 3   # CH4
NMOX1 = 4   # O2
NMPR1 = 5   # CO2
NMPR2 = 6   # H2O
NMDF = 7    # H2
NMOX2 = 8   # CO
NMFU2 = 9   # OH
NMU1 = 10   # энтальпия
NMU = 11    # турбулентная вязкость
NRO3 = 12   # плотность
NT = 13     # температура
NV1 = 14    # скорость (осевая)
NV2 = 15    # скорость (радиальная)
NMU2 = 16   # закрутка (r*W)
NK = 17
N3 = 17


@jit
def fpow(x, y):
    """x**y для дробного y; для x < 0 даёт NaN, как Фортран."""
    if x < 0.0:
        return math.nan
    return x ** y


# ----------------------------------------------------------------------
# SUBROUTINE VISCOS  (RK4.FOR)
# ----------------------------------------------------------------------
@jit
def viscos(A, X1, R, IMIN, IMAX, PKS,
           IN, JN, JA, JZ, JZ1, JA1, JA2, JA3, JC, IC1, IC2,
           VINP, VINS, ROP, ROS, VINS1):
    RL = 0.1
    # DO 100: отрицательные концентрации -> 0
    for K in range(3, 10):
        for J in range(1, JN + 1):
            IL = IMIN[J]
            IM = IMAX[J] + 1
            if J < JA1 and J > JA:
                IL = IMIN[J] - 1
            if J < JZ1 and J > JZ:
                IL = IMIN[J] - 1
            if J > JA2:
                IL = IMIN[J] - 1
            for I in range(IL, IM + 1):
                if A[I, J, K] < 0.0:
                    A[I, J, K] = 0.0
    # DO 121: нормировка суммы массовых долей
    for J in range(1, JN + 1):
        IL = IMIN[J]
        IM = IMAX[J] + 1
        if J <= JC:
            IM = IN
        if J < JA1 and J > JA:
            IL = IMIN[J] - 1
        if J < JZ1 and J > JZ:
            IL = IMIN[J] - 1
        if J > JA2:
            IL = IMIN[J] - 1
        for I in range(IL, IM + 1):
            CM = (A[I, J, NMFU1] + A[I, J, NMFU2] + A[I, J, NMOX1]
                  + A[I, J, NMOX2] + A[I, J, NMPR1] + A[I, J, NMPR2]
                  + A[I, J, NMDF])
            if CM <= 0.0:
                continue
            A[I, J, NMFU1] = A[I, J, NMFU1] / CM
            A[I, J, NMFU2] = A[I, J, NMFU2] / CM
            A[I, J, NMOX1] = A[I, J, NMOX1] / CM
            A[I, J, NMOX2] = A[I, J, NMOX2] / CM
            A[I, J, NMPR1] = A[I, J, NMPR1] / CM
            A[I, J, NMPR2] = A[I, J, NMPR2] / CM
            A[I, J, NMDF] = A[I, J, NMDF] / CM
    # DO 20: температура и плотность
    for J in range(1, JN + 1):
        IL = IMIN[J]
        IM = IMAX[J] + 1
        if J <= JC:
            IM = IN
        if J < JA1 and J > JA:
            IL = IMIN[J] - 1
        if J < JZ1 and J > JZ:
            IL = IMIN[J] - 1
        if J > JA2:
            IL = IMIN[J] - 1
        for I in range(IL, IM + 1):
            AZK = (A[I, J, NMPR1] + A[I, J, NMOX2] + A[I, J, NMDF]
                   + A[I, J, NMPR2] + A[I, J, NMFU2])
            ZOKD = AZK * 0.7966 + A[I, J, NMOX1]
            ZGD = AZK * 0.2034 + A[I, J, NMFU1]
            if ZGD < 0.005:
                ZGD = 0.005
            XXX = ZOKD / ZGD / 3.9166
            # В оригинале здесь по XXX выбирались коэффициенты полинома
            # AA..EA и считалась YYY - равновесная температура. YYY
            # использовалась только в закомментированном PRINT, на
            # результат не влияет, поэтому не вычисляется.
            TQ = (3.332 * A[I, J, NMFU1] + 14.743 * A[I, J, NMDF]
                  + 1.081 * A[I, J, NMPR1] + 0.3868 * A[I, J, NMOX1]
                  + 2.059 * A[I, J, NMPR2]
                  + 1.105 * A[I, J, NMOX2] + 1.753 * A[I, J, NMFU2])
            TZ = (A[I, J, NMU1] + 4681.06 * A[I, J, NMFU1]
                  - A[I, J, NMFU2] * 2299.57
                  + A[I, J, NMOX2] * 3949.64 + 8950. * A[I, J, NMPR1]
                  + 13445.55 * A[I, J, NMPR2])
            if TZ < 0.0:
                TZ = 0.0
            if not (TQ <= 1.e-10):
                A[I, J, NT] = TZ / TQ + 293.
                if XXX > 0.8:
                    A[I, J, NT] = A[I, J, NT] * 1.1
                if XXX >= 0.2 and XXX <= 0.8:
                    A[I, J, NT] = A[I, J, NT] * 1.2
            # 50
            if A[I, J, NT] < 293.:
                A[I, J, NT] = 293.
            if A[I, J, NT] > 4500.:
                A[I, J, NT] = 4500.
            Z = A[I, J, NRO3]
            ROQ = A[I, J, NT] * (A[I, J, NMFU1] / 16. + A[I, J, NMOX1] / 32.
                                 + A[I, J, NMDF] / 2.
                                 + A[I, J, NMOX2] / 28. + A[I, J, NMPR1] / 44.
                                 + A[I, J, NMPR2] / 18.
                                 + A[I, J, NMFU2] / 17.)
            if ROQ != 0.0:
                ROZ = (A[I, J, NMOX1] + A[I, J, NMOX2] + A[I, J, NMDF]
                       + A[I, J, NMFU1]
                       + A[I, J, NMPR1] + A[I, J, NMPR2] + A[I, J, NMFU2])
                ROX = PKS[I] / 8314.4
                A[I, J, NRO3] = ROX * ROZ / ROQ
                A[I, J, NRO3] = Z + (A[I, J, NRO3] - Z) * RL
            # 60
            if A[I, J, NRO3] < 0.00001:
                A[I, J, NRO3] = 0.00001
    # Турбулентная вязкость
    RK4 = 0.0
    for J in range(2, JA3 + 1):
        RK4 = RK4 + 3.1416 * (A[IC2, J, NF] - A[IC2, J - 1, NF]) * \
            (A[IC2, J, NV1] ** 2 + A[IC2, J, NMU2] ** 2)
    for J in range(1, JN + 1):
        IL = IMIN[J]
        IM = IMAX[J] + 1
        if J == JC:
            IM = IN
        for I in range(IL, IM + 1):
            RZ1 = fpow(2. * R[JN], 0.666) / fpow(X1[IC1], 0.333)
            if I <= IC2:
                RZ1 = fpow(2 * R[JA3], 0.666) / fpow(X1[IC1], 0.333)
            RK = 3.1416 * (R[JA2] ** 2. - R[JA1] ** 2.) * ROS * VINS ** 3.
            RK1 = (3.1416 * (R[JA] - R[JZ1]) * (R[JA] + R[JZ1]) * ROP * VINP
                   * VINP ** 2
                   + 3.1416 * R[JZ] ** 2. * A[1, 2, NRO3] * VINS1 ** 3.)
            if I > IC2:
                RK2 = RK + RK4
            else:
                RK2 = RK1
            A[I, J, NMU] = 0.012 * RZ1 * fpow(A[I, J, NRO3], 0.666) * \
                fpow(RK2, 0.333)
            A[I, J, NMU] = A[I, J, NMU] * 2.


# ----------------------------------------------------------------------
# SUBROUTINE VELDIS  (RK5.FOR)
# ----------------------------------------------------------------------
@jit
def veldis(A, X1, X2, R, IMIN, IMAX, VS, FKS, UKS,
           INM, JNM, JA3, JC, IC, IC2, NITER):
    """Скорости и источник вихря. Возвращает NITER (может вырасти на 1000)."""
    for J in range(2, JNM + 1):
        H2 = (X2[J] - X2[J - 1]) / (X2[J + 1] - X2[J])
        RX2 = R[J] * (X2[J + 1] - X2[J - 1])
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            H1 = (X1[I - 1] - X1[I]) / (X1[I + 1] - X1[I])
            RX1 = R[J] * (X1[I + 1] - X1[I - 1])
            A[I, J, NV1] = (A[I, J + 1, NF] - A[I, J, NF]) * H2 + \
                (A[I, J, NF] - A[I, J - 1, NF]) / H2
            A[I, J, NV1] = A[I, J, NV1] / RX2 / A[I, J, NRO3]
            A[I, J, NV2] = (A[I + 1, J, NF] - A[I, J, NF]) * H1 + \
                (A[I, J, NF] - A[I - 1, J, NF]) / H1
            A[I, J, NV2] = A[I, J, NV2] / RX1 / A[I, J, NRO3]
            # Признак расходимости: досрочное завершение варианта
            if NITER >= 85 and abs(A[I, J, NV1]) >= 27000.:
                NITER = NITER + 1000
    DELX2 = X2[2] - X2[1]
    for I in range(2, INM + 1):
        A[I, 1, NV1] = (A[I, 2, NF] - A[I, 1, NF]) / DELX2 / A[I, 1, NRO3] \
            / 0.5 / R[2]
    for J in range(2, JNM + 1):
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            VS[I, J] = 0.5 * (A[I, J, NV1] * A[I, J, NV1]
                              + A[I, J, NV2] * A[I, J, NV2])
            FKS[I, J] = (A[I, J, NMU2] / R[J]) ** 2 * A[I, J, NRO3]
    for J in range(2, JNM + 1):
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            DIF1 = ((VS[I + 1, J] - VS[I, J]) * (X1[I] - X1[I - 1])
                    / (X1[I + 1] - X1[I]) + (VS[I, J] - VS[I - 1, J])
                    * (X1[I + 1] - X1[I])
                    / (X1[I] - X1[I - 1])) / (X1[I + 1] - X1[I - 1])
            DIF2 = ((VS[I, J + 1] - VS[I, J]) * (X2[J] - X2[J - 1])
                    / (X2[J + 1] - X2[J]) + (VS[I, J] - VS[I, J - 1])
                    * (X2[J + 1] - X2[J])
                    / (X2[J] - X2[J - 1])) / (X2[J + 1] - X2[J - 1])
            DIF3 = ((A[I + 1, J, NRO3] - A[I, J, NRO3]) * (X1[I] - X1[I - 1])
                    / (X1[I + 1] - X1[I])
                    + (A[I, J, NRO3] - A[I - 1, J, NRO3])
                    * (X1[I + 1] - X1[I])
                    / (X1[I] - X1[I - 1])) / (X1[I + 1] - X1[I - 1])
            DIF4 = ((A[I, J + 1, NRO3] - A[I, J, NRO3]) * (X2[J] - X2[J - 1])
                    / (X2[J + 1] - X2[J])
                    + (A[I, J, NRO3] - A[I, J - 1, NRO3])
                    * (X2[J + 1] - X2[J])
                    / (X2[J] - X2[J - 1])) / (X2[J + 1] - X2[J - 1])
            DIF5 = ((FKS[I + 1, J] - FKS[I, J]) * (X1[I] - X1[I - 1])
                    / (X1[I + 1] - X1[I]) + (FKS[I, J] - FKS[I - 1, J])
                    * (X1[I + 1] - X1[I])
                    / (X1[I] - X1[I - 1])) / (X1[I + 1] - X1[I - 1])
            S1 = DIF1 * DIF4
            S2 = DIF2 * DIF3
            UKS[I, J] = R[J] * (S1 - S2) - DIF5
    return NITER


# ----------------------------------------------------------------------
# SUBROUTINE CONVEC  (RK5.FOR)
# ----------------------------------------------------------------------
@jit
def convec(A, X1, X2, R, IMIN, IMAX, BE, BW, BN, BS,
           AE, AW, AN, AS, AE1, AW1, AN1, AS1,
           JNM, JA3, JC, IC, IC2):
    for J in range(2, JNM + 1):
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            DV = R[J] * (X1[I + 1] - X1[I - 1]) * (X2[J + 1] - X2[J - 1])
            G1PW = (A[I, J + 1, NF] - A[I, J - 1, NF] + A[I - 1, J + 1, NF]
                    - A[I - 1, J - 1, NF]) / DV
            G1PE = (A[I, J + 1, NF] - A[I, J - 1, NF] + A[I + 1, J + 1, NF]
                    - A[I + 1, J - 1, NF]) / DV
            G2PS = (A[I - 1, J, NF] - A[I + 1, J, NF] + A[I - 1, J - 1, NF]
                    - A[I + 1, J - 1, NF]) / DV
            G2PN = (A[I - 1, J, NF] - A[I + 1, J, NF] + A[I - 1, J + 1, NF]
                    - A[I + 1, J + 1, NF]) / DV
            AE[I, J] = 0.5 * (abs(G1PE) - G1PE)
            AW[I, J] = 0.5 * (abs(G1PW) + G1PW)
            AN[I, J] = 0.5 * (abs(G2PN) - G2PN)
            AS[I, J] = 0.5 * (abs(G2PS) + G2PS)
            BPP = A[I, J, NMU]
            BBE = (A[I + 1, J, NMU] + BPP) * BE[I]
            BBW = (A[I - 1, J, NMU] + BPP) * BW[I]
            BBN = (A[I, J + 1, NMU] + BPP) * BN[J]
            BBS = (A[I, J - 1, NMU] + BPP) * BS[J]
            AE1[I, J] = AE[I, J] + BBE
            AW1[I, J] = AW[I, J] + BBW
            AN1[I, J] = AN[I, J] + BBN
            AS1[I, J] = AS[I, J] + BBS


@jit
def _rel_change(new, old):
    """Относительное изменение RS, как в метках 15/16, 25/26, 65/66."""
    RS = 0.0
    if abs(new) >= 1.e-20:
        RS = 1. - old / new
    elif abs(old) >= 1.e-20:
        RS = 1. - new / old
    if abs(new) < 1.e-20 and abs(old) < 1.e-20:
        RS = 0.
    return RS


# ----------------------------------------------------------------------
# SUBROUTINE EQN  (RK3.FOR); SORCE (RK6.FOR) встроена
# ----------------------------------------------------------------------
@jit
def eqn(A, X1, X2, R, IMIN, IMAX, BE, BW, BN, BS,
        AE, AW, AN, AS, AE1, AW1, AN1, AS1, UKS, FKS, TKS, RSDU,
        IN, INM, JN, JNM, JA, JA1, JA2, JA3, JB, JB1, JC, JC1, JZ, JZ1,
        IC, IC1, IC2, NITER, NPRINT, NVAR, NCORD, ROM1, IGN_I2):
    # IGN_I2 - последний узел зоны поджига по длине (в оригинале 11 = IC2+1)
    # ---------- уравнение для вихря (NW) ----------
    if not (NITER <= NPRINT and NVAR == 1):
        RL = 0.1
        for J in range(2, JNM + 1):
            IL = IMIN[J]
            IM = IMAX[J]
            if J == JA3:
                IL = IC2 + 1
            if J == JC:
                IM = IC - 1
            for I in range(IL, IM + 1):
                corner = ((J == JA and I == 2)
                          or (J == JA1 and I == IC2 + 1)
                          or (J == JA2 and I == IC2 + 1)
                          or (J == JA3 and I == IC2 + 1)
                          or (J == JZ and I == 2)
                          or (J == JZ1 and I == 2))
                if (not corner) and JB1 != JN and J == JB1 - 1 and I == IC2:
                    corner = True  # метка 113 (тот же код, что 111)
                Z = A[I, J, NW]
                if not corner:
                    SOURCE = UKS[I, J]  # SORCE, K=NW
                    RSO = R[J] * R[J]
                    BBE = 2. * RSO * BE[I]
                    BBW = 2. * RSO * BW[I]
                    BBS = (R[J - 1] * R[J - 1] + RSO) * BS[J]
                    BBN = (R[J + 1] * R[J + 1] + RSO) * BN[J]
                    AAE = RSO * AE[I, J]
                    AAW = RSO * AW[I, J]
                    AAN = RSO * AN[I, J]
                    AAS = RSO * AS[I, J]
                    ANUM = ((AAE + A[I + 1, J, NMU] * BBE) * A[I + 1, J, NW]
                            + (AAW + A[I - 1, J, NMU] * BBW) * A[I - 1, J, NW]
                            + (AAN + A[I, J + 1, NMU] * BBN) * A[I, J + 1, NW]
                            + (AAS + A[I, J - 1, NMU] * BBS) * A[I, J - 1, NW]
                            + SOURCE)
                    ADNM = AAE + AAW + AAN + AAS + A[I, J, NMU] * \
                        (BBE + BBW + BBN + BBS)
                    if ADNM != 0.:
                        A[I, J, NW] = ANUM / ADNM
                        A[I, J, NW] = Z + (A[I, J, NW] - Z) * RL
                else:
                    # метки 111 / 113: вихрь на угловых точках
                    RISO = 1. / R[J] / R[J]
                    ROP3 = A[I, J, NRO3]
                    BBE = 4. / (A[I + 1, J, NRO3] + ROP3) * RISO * BE[I]
                    BBW = 4. / (A[I - 1, J, NRO3] + ROP3) * RISO * BW[I]
                    BBN = 16. / (A[I, J + 1, NRO3] + ROP3) / \
                        ((R[J + 1] + R[J]) ** 2.) * BN[J]
                    BBS = 16. / (A[I, J - 1, NRO3] + ROP3) / \
                        ((R[J - 1] + R[J]) ** 2.) * BS[J]
                    ANUM = (BBE * A[I + 1, J, NF] + BBW * A[I - 1, J, NF]
                            + BBN * A[I, J + 1, NF] + BBS * A[I, J - 1, NF])
                    ADNM = BBE + BBW + BBN + BBS
                    A[I, J, NW] = A[I, J, NF] * ADNM - ANUM
                    A[I, J, NW] = Z + (A[I, J, NW] - Z) * RL
                # 114
                RS = _rel_change(A[I, J, NW], Z)
                if abs(RS) > abs(RSDU[NW]):
                    RSDU[NW] = RS
                if NITER >= 20:
                    A[I, J, NW] = Z + (A[I, J, NW] - Z) * 1.0
                if A[I, J, NW] >= 1.e+14:
                    A[I, J, NW] = 1.e+14
                if A[I, J, NW] <= -1.e+14:
                    A[I, J, NW] = -1.e+14
    # 177 ---------- уравнение для функции тока (NF) ----------
    for J in range(2, JNM + 1):
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            Z = A[I, J, NF]
            if ((J == JA and I == 2)
                    or (J == JA1 and I == IC2 + 1)
                    or (J == JA2 and I == IC2 + 1)
                    or (J == JA3 and I == IC2 + 1)
                    or (J == JZ and I == 2)
                    or (J == JZ1 and I == 2)):
                A[I, J, NF] = A[I - 1, J, NF]          # 121
            elif JB1 != JN and J == JB1 - 1 and I == IC2:
                A[I, J, NF] = A[I, J + 1, NF]          # 123
            else:
                SOURCE = A[I, J, NW]                   # SORCE, K=NF
                if NITER <= NPRINT:
                    SOURCE = 0.
                RISO = 1. / R[J] / R[J]
                ROP3 = A[I, J, NRO3]
                BBE = 4. / (A[I + 1, J, NRO3] + ROP3) * RISO * BE[I]
                BBW = 4. / (A[I - 1, J, NRO3] + ROP3) * RISO * BW[I]
                BBN = 16. / (A[I, J + 1, NRO3] + ROP3) / \
                    ((R[J + 1] + R[J]) ** 2.) * BN[J]
                BBS = 16. / (A[I, J - 1, NRO3] + ROP3) / \
                    ((R[J - 1] + R[J]) ** 2.) * BS[J]
                ANUM = (BBE * A[I + 1, J, NF] + BBW * A[I - 1, J, NF]
                        + BBN * A[I, J + 1, NF] + BBS * A[I, J - 1, NF]
                        + SOURCE)
                ADNM = BBE + BBW + BBN + BBS
                if ADNM == 0.:
                    continue                           # GO TO 21
                A[I, J, NF] = ANUM / ADNM
            # 122
            RS = _rel_change(A[I, J, NF], Z)
            if abs(RS) > abs(RSDU[NF]):
                RSDU[NF] = RS
            if A[I, J, NF] >= 1.e+25:
                A[I, J, NF] = 1.e+25
            if A[I, J, NF] <= -1.e+25:
                A[I, J, NF] = -1.e+25
    # ---------- закрутка (NMU2) ----------
    for J in range(3, JNM + 1):
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            BBE = (A[I + 1, J, NMU] * R[J] ** 2 + A[I, J, NMU] * R[J] ** 2) * BE[I]
            BBW = (A[I - 1, J, NMU] * R[J] ** 2 + A[I, J, NMU] * R[J] ** 2) * BW[I]
            BBN = (A[I, J + 1, NMU] * R[J + 1] ** 2
                   + A[I, J, NMU] * R[J] ** 2) * BN[J]
            BBS = (A[I, J - 1, NMU] * R[J - 1] ** 2
                   + A[I, J, NMU] * R[J] ** 2) * BS[J]
            ANUM = ((AE[I, J] + BBE / R[J] ** 2) * A[I + 1, J, NMU2]
                    + (AW[I, J] + BBW / R[J] ** 2) * A[I - 1, J, NMU2]
                    + (AN[I, J] + BBN / R[J + 1] ** 2) * A[I, J + 1, NMU2]
                    + (AS[I, J] + BBS / R[J - 1] ** 2) * A[I, J - 1, NMU2])
            ADNM = (AE[I, J] + AW[I, J] + AN[I, J] + AS[I, J] + BBE / R[J] ** 2
                    + BBW / R[J] ** 2 + BBN / R[J + 1] ** 2
                    + BBS / R[J - 1] ** 2)
            if ADNM == 0.:
                continue
            A[I, J, NMU2] = ANUM / ADNM
    for I in range(2, INM + 1):
        A[I, 2, NMU2] = A[I, 3, NMU2] * R[2] / R[3]
    # ---------- перенос компонентов и энтальпии: K = 10, 9, ..., 3 ----------
    for II in range(3, 11):
        K = 13 - II
        for J in range(2, JNM + 1):
            IL = IMIN[J]
            IM = IMAX[J]
            if J == JA3:
                IL = IC2 + 1
            if J == JC:
                IM = IC - 1
            for I in range(IL, IM + 1):
                ADNM = AE1[I, J] + AW1[I, J] + AN1[I, J] + AS1[I, J]
                Z = A[I, J, K]
                ANUM = (AE1[I, J] * A[I + 1, J, K] + AW1[I, J] * A[I - 1, J, K]
                        + AN1[I, J] * A[I, J + 1, K]
                        + AS1[I, J] * A[I, J - 1, K])
                ANUM = ANUM + 0.0  # SORCE для K >= 3 равен 0
                if ADNM == 0.:
                    continue
                A[I, J, K] = ANUM / ADNM
                if K != NMU1:
                    continue
                RS = _rel_change(A[I, J, K], Z)
                if abs(RS) > abs(RSDU[K]):
                    RSDU[K] = RS
    # ---------- нормировка (DO 56) ----------
    for J in range(2, JNM + 1):
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            FKS[I, J] = A[I, J, NMFU1]
            TKS[I, J] = A[I, J, NMOX1]
            CM = (A[I, J, NMFU1] + A[I, J, NMFU2] + A[I, J, NMOX1]
                  + A[I, J, NMOX2] + A[I, J, NMPR1] + A[I, J, NMPR2]
                  + A[I, J, NMDF])
            if abs(CM) <= 1.e-20:
                continue
            A[I, J, NMFU1] = A[I, J, NMFU1] / CM
            A[I, J, NMFU2] = A[I, J, NMFU2] / CM
            A[I, J, NMOX1] = A[I, J, NMOX1] / CM
            A[I, J, NMOX2] = A[I, J, NMOX2] / CM
            A[I, J, NMPR1] = A[I, J, NMPR1] / CM
            A[I, J, NMPR2] = A[I, J, NMPR2] / CM
            A[I, J, NMDF] = A[I, J, NMDF] / CM
    # ---------- химическая реакция (DO 82) ----------
    for J in range(2, JNM + 1):
        IL = IMIN[J]
        IM = IMAX[J]
        if J == JA3:
            IL = IC2 + 1
        if J == JC:
            IM = IC - 1
        for I in range(IL, IM + 1):
            react = True
            if NITER == 18 and I >= 3 and I <= IGN_I2 and J > JZ and J < JA1:
                react = True        # GO TO 33: принудительное зажигание
            elif A[I, J, NT] < ROM1:
                react = False       # GO TO 304
            if react:
                # 33
                if A[I, J, NMFU1] <= 1.e-20:
                    continue        # GO TO 82
                ZNK = A[I, J, NMOX1] / A[I, J, NMFU1]
                if not (ZNK > 3.9166):
                    # недостаток окислителя
                    A[I, J, NMPR1] = A[I, J, NMPR1] + (8. * 44. / 32. / 47.) * A[I, J, NMOX1]
                    A[I, J, NMOX2] = A[I, J, NMOX2] + (16. * 28. / 32. / 47.) * A[I, J, NMOX1]
                    A[I, J, NMDF] = A[I, J, NMDF] + (4. / 32. / 47.) * A[I, J, NMOX1]
                    A[I, J, NMPR2] = A[I, J, NMPR2] + (30. * 18. / 32. / 47.) * A[I, J, NMOX1]
                    A[I, J, NMFU2] = A[I, J, NMFU2] + (32. * 17. / 32. / 47.) * A[I, J, NMOX1]
                    A[I, J, NMFU1] = A[I, J, NMFU1] - (24. * 16. / 32. / 47.) * A[I, J, NMOX1]
                    if A[I, J, NMFU1] < 1.e-20:
                        A[I, J, NMFU1] = 1.e-20
                    A[I, J, NMOX1] = 1.e-20
                else:
                    # 83: избыток окислителя
                    A[I, J, NMPR1] = A[I, J, NMPR1] + (8. * 44. / 24. / 16.) * A[I, J, NMFU1]
                    A[I, J, NMOX2] = A[I, J, NMOX2] + (28. * 16. / 24. / 16.) * A[I, J, NMFU1]
                    A[I, J, NMDF] = A[I, J, NMDF] + (4. / 24. / 16.) * A[I, J, NMFU1]
                    A[I, J, NMPR2] = A[I, J, NMPR2] + (30. * 18. / 24. / 16.) * A[I, J, NMFU1]
                    A[I, J, NMFU2] = A[I, J, NMFU2] + (32. * 17. / 24. / 16.) * A[I, J, NMFU1]
                    A[I, J, NMOX1] = A[I, J, NMOX1] - (47. * 32. / 24. / 16.) * A[I, J, NMFU1]
                    if A[I, J, NMOX1] < 1.e-20:
                        A[I, J, NMOX1] = 1.e-20
                    A[I, J, NMFU1] = 1.e-20
            # 304
            CM = (A[I, J, NMFU1] + A[I, J, NMFU2] + A[I, J, NMOX1]
                  + A[I, J, NMOX2] + A[I, J, NMPR1] + A[I, J, NMPR2]
                  + A[I, J, NMDF])
            if abs(CM) <= 1.e-20:
                continue
            A[I, J, NMFU1] = A[I, J, NMFU1] / CM
            A[I, J, NMFU2] = A[I, J, NMFU2] / CM
            A[I, J, NMOX1] = A[I, J, NMOX1] / CM
            A[I, J, NMOX2] = A[I, J, NMOX2] / CM
            A[I, J, NMPR1] = A[I, J, NMPR1] / CM
            A[I, J, NMPR2] = A[I, J, NMPR2] / CM
            A[I, J, NMDF] = A[I, J, NMDF] / CM
            if abs(FKS[I, J]) < 1.e-22:
                RS = 1.
            else:
                RS = 1. - A[I, J, NMFU1] / FKS[I, J]
            if abs(FKS[I, J]) < 1.e-22 and abs(A[I, J, NMFU1]) < 1.e-22:
                RS = 0.
            if abs(RS) >= abs(RSDU[NMFU1]):
                RSDU[NMFU1] = abs(RS)
            if abs(TKS[I, J]) < 1.e-22:
                RS = 1.
            else:
                RS = 1. - A[I, J, NMOX1] / TKS[I, J]
            if abs(TKS[I, J]) < 1.e-22 and abs(A[I, J, NMOX1]) < 1.e-22:
                RS = 0.
            if abs(RS) >= abs(RSDU[NMOX1]):
                RSDU[NMOX1] = abs(RS)
            FKS[I, J] = 0.
            TKS[I, J] = 0.
    bound(A, X1, X2, R, IMIN, IMAX,
          IN, INM, JN, JNM, JA, JA1, JA2, JA3, JB, JB1, JC, JC1, JZ, JZ1,
          IC, IC1, IC2, NITER, NPRINT, NVAR, NCORD)


# ----------------------------------------------------------------------
# SUBROUTINE BOUND  (RK7.FOR)
# ----------------------------------------------------------------------
@jit
def _wall_w(A, I, J, Jm, R, DX2, WK, mode):
    """Вихрь на стенке (формулы меток 31, 141, 142, 51).

    mode: 0 - WX=F(Jm)/DX2/DX2 (метка 31), 1 - WX=F(Jm)/(DX2*DX2) (метка 51),
          2 - WX=(F(Jm)-F(J))/(DX2*DX2) (метки 141, 142).
    """
    if mode == 2:
        WX = (A[I, Jm, NF] - A[I, J, NF]) / (DX2 * DX2)
    elif mode == 1:
        WX = A[I, Jm, NF] / (DX2 * DX2)
    else:
        WX = A[I, Jm, NF] / DX2 / DX2
    WY = A[I, Jm, NW] * (R[J] - WK * DX2) * \
        (A[I, J, NRO3] * (R[J] / 6. - WK * DX2 / 8.)
         + (A[I, Jm, NRO3] - A[I, J, NRO3]) * (R[J] / 8. - WK * DX2 / 10.))
    WZ = R[J] * (A[I, J, NRO3] * (R[J] / 3. - 5. * WK * DX2 / 24.)
                 + (A[I, Jm, NRO3] - A[I, J, NRO3])
                 * (5. * R[J] / 24. - 3. * WK * DX2 / 20.))
    return -1. * (WX + WY) / WZ


@jit
def bound(A, X1, X2, R, IMIN, IMAX,
          IN, INM, JN, JNM, JA, JA1, JA2, JA3, JB, JB1, JC, JC1, JZ, JZ1,
          IC, IC1, IC2, NITER, NPRINT, NVAR, NCORD):
    JA17 = JA + 1
    JA18 = JA1 - 1
    # DO 10
    for J in range(JA17, JN + 1):
        IL = IMIN[J]
        if J == JA3:
            IL = IC2 + 1
        for K in range(3, 11):
            if J > JA18 and J <= JA2:
                continue
            A[IL - 1, J, K] = A[IL, J, K]
    # DO 11: вихрь на левой стенке
    for J in range(JA, JNM + 1):
        IL = IMIN[J]
        if J == JA3:
            IL = IC2 + 1
        if J > JA1 and J < JA2:
            continue
        WX = (A[IL, J, NF] - A[IL - 1, J, NF]) / (R[J] * X1[IL]) ** 2.
        WY = A[IL, J, NW] * (A[IL - 1, J, NRO3] / 6.
                             + (A[IL, J, NRO3] - A[IL - 1, J, NRO3]) / 8.)
        WZ = A[IL - 1, J, NRO3] / 3. + \
            5. * (A[IL, J, NRO3] - A[IL - 1, J, NRO3]) / 24.
        A[IL - 1, J, NW] = -1. * (WX + WY) / WZ
        if A[IL - 1, J, NW] >= 1.e+14:
            A[IL - 1, J, NW] = 1.e+14
        if A[IL - 1, J, NW] <= -1.e+14:
            A[IL - 1, J, NW] = -1.e+14
        if NITER <= NPRINT:
            A[IL - 1, J, NW] = 0.
    # DO 501
    for J in range(JZ, JZ1 + 1):
        WX = (A[2, J, NF] - A[1, J, NF]) / (R[J] * X1[2]) ** 2.
        WY = A[2, J, NW] * (A[1, J, NRO3] / 6.
                            + (A[2, J, NRO3] - A[1, J, NRO3]) / 8.)
        WZ = A[1, J, NRO3] / 3. + 5. * (A[2, J, NRO3] - A[1, J, NRO3]) / 24.
        A[1, J, NW] = -1. * (WX + WY) / WZ
        if A[1, J, NW] >= 1.e+14:
            A[1, J, NW] = 1.e+14
        if A[1, J, NW] <= -1.e+14:
            A[1, J, NW] = -1.e+14
        if NITER <= NPRINT and NVAR == 1:
            A[1, J, NW] = 0.
    # DO 509
    for J in range(JZ + 1, JZ1):
        for K in range(3, 11):
            A[1, J, K] = A[2, J, K]
    # DO 30
    for J in range(JC1, JB + 1):
        for K in range(3, 11):
            KK = IMAX[J] + 1
            A[KK, J, K] = A[KK, J - 1, K]
    # DO 31: вихрь на стенке сопла
    for J in range(JC1, JB + 1):
        DX2 = X2[J] - X2[J - 1]
        KK = IMAX[J] + 1
        A[KK, J, NW] = _wall_w(A, KK, J, J - 1, R, DX2, 1., 0)
        if NITER <= NPRINT:
            A[KK, J, NW] = 0.
        if A[KK, J, NW] >= 1.e+14:
            A[KK, J, NW] = 1.e+14
        if A[KK, J, NW] <= -1.e+14:
            A[KK, J, NW] = -1.e+14
    # (цикл 3001 в оригинале обходится оператором GO TO 3078)
    # DO 101
    for I in range(2, IC2 + 1):
        for K in range(3, 11):
            A[I, JA3, K] = A[I, JA3 - 1, K]
    # DO 141: вихрь на стенке предкамеры
    DX2 = X2[JA3] - X2[JA3 - 1]
    for I in range(2, IC2):
        A[I, JA3, NW] = _wall_w(A, I, JA3, JA3 - 1, R, DX2, 1., 2)
        if NITER <= NPRINT:
            A[I, JA3, NW] = 0.
        if A[I, JA3, NW] > 1.e+14:
            A[I, JA3, NW] = 1.e+14
        if A[I, JA3, NW] < -1.e+14:
            A[I, JA3, NW] = -1.e+14
    # DO 41
    IC15 = IC2 + 1
    IC57 = IC1
    for I in range(IC15, IC57 + 1):
        for K in range(3, 11):
            A[I, JN, K] = A[I, JN - 1, K]
    # DO 142: вихрь на стенке камеры
    DX2 = X2[JB1] - X2[JB1 - 1]
    for I in range(IC15, IC57 + 1):
        A[I, JB1, NW] = _wall_w(A, I, JB1, JB1 - 1, R, DX2, 1., 2)
        if NITER <= NPRINT:
            A[I, JB1, NW] = 0.
        if A[I, JB1, NW] >= 1.e+14:
            A[I, JB1, NW] = 1.e+14
        if A[I, JB1, NW] <= -1.e+14:
            A[I, JB1, NW] = -1.e+14
    # DO 50
    for I in range(IC, INM + 1):
        for K in range(3, 11):
            A[I, JC, K] = A[I, JC - 1, K]
    # DO 51: вихрь в критическом сечении и за ним
    DX2 = X2[JC] - X2[JC - 1]
    for I in range(IC, IN + 1):
        A[I, JC, NW] = _wall_w(A, I, JC, JC - 1, R, DX2, 1., 1)
        if NITER <= NPRINT:
            A[I, JC, NW] = 0.
        if A[I, JC, NW] >= 1.e+14:
            A[I, JC, NW] = 1.e+14
        if A[I, JC, NW] <= -1.e+14:
            A[I, JC, NW] = -1.e+14
    # DO 61: ось симметрии
    for I in range(2, INM + 1):
        for K in range(3, 11):
            A[I, 1, K] = A[I, 2, K]
            if NCORD == 1:
                A[I, 1, NW] = 0.
            if NCORD == 2:
                A[I, 1, NW] = A[I, 2, NW] + (X2[2] / (X2[3] - X2[2])) * \
                    (A[I, 2, NW] - A[I, 3, NW])
            if A[I, 1, NW] >= 1.e+14:
                A[I, 1, NW] = 1.e+14
            if A[I, 1, NW] <= -1.e+14:
                A[I, 1, NW] = -1.e+14
    # DO 70: выходное сечение
    for K in range(1, N3 + 1):
        for J in range(1, JC + 1):
            A[IN, J, K] = A[IN - 1, J, K]
