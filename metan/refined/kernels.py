"""Вычислительные ядра уточнённых моделей горения и турбулентности (numba).

* edm_step   - горение с конечной скоростью по модели вихревого распада
               (Eddy Dissipation, Магнуссен - Хьертагер);
* keps_step  - один проход Гаусса-Зейделя для k и ε (стандартная k-ε,
               Лаундер - Сполдинг) с пристеночными функциями;
* production - порождение турбулентности Pk.

Обозначения массивов и порядок обхода узлов - как в metan/kernels.py.
"""

from ..kernels import (NMDF, NMFU1, NMFU2, NMOX1, NMOX2, NMPR1, NMPR2, NMU,
                       NMU2, NRO3, NV1, NV2, jit)

# Массовые доли продуктов на 1 кг сгоревшего CH4 для брутто-реакции модели
# 24 CH4 + 47 O2 -> 8 CO2 + 16 CO + 2 H2 + 30 H2O + 32 OH (как в EQN)
S_O2 = 47. * 32. / (24. * 16.)          # 3.9166 кг O2 на 1 кг CH4
P_CO2 = 8. * 44. / (24. * 16.)
P_CO = 16. * 28. / (24. * 16.)
P_H2 = 4. / (24. * 16.)
P_H2O = 30. * 18. / (24. * 16.)
P_OH = 32. * 17. / (24. * 16.)

C_MU, C1, C2, SIG_K, SIG_E, KAPPA = 0.09, 1.44, 1.92, 1.0, 1.3, 0.41


@jit
def edm_step(A, INT, AE1, AW1, AN1, AS1, EK, CA, CB, IN, JN):
    """Горение: в узле сгорает доля q = Da/(1+Da) от того, что может
    сгореть, Da = CA·ρ·(ε/k)/aP. Это точное решение уравнения переноса
    горючего с линейным стоком w = CA·ρ·(ε/k)·min(YF, YO/s) при той же
    разностной схеме (aP - сумма коэффициентов узла). CB - ограничение по
    продуктам (Магнуссен: B·YP/(1+s)), CB <= 0 - не учитывать."""
    burned = 0.
    for J in range(2, JN):
        for I in range(2, IN):
            if not INT[I, J]:
                continue
            aP = AE1[I, J] + AW1[I, J] + AN1[I, J] + AS1[I, J]
            if aP <= 0.:
                continue
            rho = A[I, J, NRO3]
            yf = A[I, J, NMFU1]
            yo = A[I, J, NMOX1]
            lim = yf if yo >= S_O2 * yf else yo / S_O2
            if CB > 0.:
                yp = (A[I, J, NMPR1] + A[I, J, NMOX2] + A[I, J, NMDF]
                      + A[I, J, NMPR2] + A[I, J, NMFU2])
                lp = CB * yp / (1. + S_O2)
                # без продуктов реакция не начнётся - нужен «запал»
                if lp < lim:
                    lim = lp
            if lim <= 1e-14:
                continue
            Da = CA * rho * EK[I, J] / aP
            dF = lim * Da / (1. + Da)
            A[I, J, NMFU1] = yf - dF
            A[I, J, NMOX1] = yo - S_O2 * dF
            if A[I, J, NMOX1] < 0.:
                A[I, J, NMOX1] = 0.
            A[I, J, NMPR1] += P_CO2 * dF
            A[I, J, NMOX2] += P_CO * dF
            A[I, J, NMDF] += P_H2 * dF
            A[I, J, NMPR2] += P_H2O * dF
            A[I, J, NMFU2] += P_OH * dF
            burned += dF
    return burned


@jit
def production(A, INT, X1, X2, R, PK, IN, JN, NCORD):
    """Порождение турбулентной энергии Pk = μт·Φ (Φ - диссипативная функция
    осесимметричного течения с закруткой), центральные разности."""
    for J in range(2, JN):
        for I in range(2, IN):
            PK[I, J] = 0.
            if not INT[I, J]:
                continue
            dx = X1[I + 1] - X1[I - 1]
            dr = X2[J + 1] - X2[J - 1]
            dudx = (A[I + 1, J, NV1] - A[I - 1, J, NV1]) / dx
            dudr = (A[I, J + 1, NV1] - A[I, J - 1, NV1]) / dr
            dvdx = (A[I + 1, J, NV2] - A[I - 1, J, NV2]) / dx
            dvdr = (A[I, J + 1, NV2] - A[I, J - 1, NV2]) / dr
            r = R[J]
            if r <= 0.:
                continue
            w_p = A[I, J + 1, NMU2] / R[J + 1]
            w_m = A[I, J - 1, NMU2] / R[J - 1] if R[J - 1] > 0. else 0.
            w_e = A[I + 1, J, NMU2] / r
            w_w = A[I - 1, J, NMU2] / r
            dwdx = (w_e - w_w) / dx
            # r·d(w/r)/dr
            rdw = r * ((w_p / R[J + 1] - (w_m / R[J - 1] if R[J - 1] > 0. else 0.))
                       / dr) if NCORD == 2 else (w_p - w_m) / dr
            vr = A[I, J, NV2] / r if NCORD == 2 else 0.
            phi = (2. * (dudx * dudx + dvdr * dvdr + vr * vr)
                   + (dudr + dvdx) ** 2 + dwdx * dwdx + rdw * rdw)
            PK[I, J] = A[I, J, NMU] * phi


@jit
def keps_step(A, INT, AE, AW, AN, AS, AE1, AW1, AN1, AS1, PK, K, E, YW,
              IN, JN, RELAX, KMIN, EMIN):
    """Один проход Гаусса-Зейделя для k и ε. Конвекция - те же
    коэффициенты против потока, что у остальных величин (AE..AS),
    диффузия - (AE1 − AE)/σ. Узлы у стенки (YW > 0): ε задаётся
    пристеночной функцией ε = Cμ^0.75·k^1.5/(κ·y)."""
    cm75 = C_MU ** 0.75
    for J in range(2, JN):
        for I in range(2, IN):
            if not INT[I, J]:
                continue
            rho = A[I, J, NRO3]
            k0 = K[I, J]
            e0 = E[I, J]
            ek = e0 / k0 if k0 > KMIN else e0 / KMIN
            # --- k
            ce = AE[I, J] + (AE1[I, J] - AE[I, J]) / SIG_K
            cw = AW[I, J] + (AW1[I, J] - AW[I, J]) / SIG_K
            cn = AN[I, J] + (AN1[I, J] - AN[I, J]) / SIG_K
            cs = AS[I, J] + (AS1[I, J] - AS[I, J]) / SIG_K
            num = (ce * K[I + 1, J] + cw * K[I - 1, J] + cn * K[I, J + 1]
                   + cs * K[I, J - 1] + PK[I, J])
            den = ce + cw + cn + cs + rho * ek
            if den > 0.:
                kn = num / den
                kn = k0 + RELAX * (kn - k0)
                K[I, J] = kn if kn > KMIN else KMIN
            # --- ε
            if YW[I, J] > 0.:
                E[I, J] = cm75 * K[I, J] ** 1.5 / (KAPPA * YW[I, J])
                continue
            ce = AE[I, J] + (AE1[I, J] - AE[I, J]) / SIG_E
            cw = AW[I, J] + (AW1[I, J] - AW[I, J]) / SIG_E
            cn = AN[I, J] + (AN1[I, J] - AN[I, J]) / SIG_E
            cs = AS[I, J] + (AS1[I, J] - AS[I, J]) / SIG_E
            num = (ce * E[I + 1, J] + cw * E[I - 1, J] + cn * E[I, J + 1]
                   + cs * E[I, J - 1] + C1 * ek * PK[I, J])
            den = ce + cw + cn + cs + C2 * rho * ek
            if den > 0.:
                en = num / den
                en = e0 + RELAX * (en - e0)
                E[I, J] = en if en > EMIN else EMIN


@jit
def keps_bounds(K, E, INT, BTYPE, BSRC, KIN, EIN, IN, JN):
    """Граничные значения k, ε во внешних узлах: вход - заданы, ось и
    выход - как в соседнем расчётном узле, стенка - k как в соседнем узле
    (нулевой поток), ε - как в соседнем (он задан пристеночной функцией)."""
    for J in range(1, JN + 1):
        for I in range(1, IN + 1):
            t = BTYPE[I, J]
            if t == 0:
                continue
            if t == 1:                       # вход
                K[I, J] = KIN[I, J]
                E[I, J] = EIN[I, J]
            else:                            # ось, выход, стенка
                si = BSRC[I, J, 0]
                sj = BSRC[I, J, 1]
                K[I, J] = K[si, sj]
                E[I, J] = E[si, sj]


@jit
def keps_viscosity(A, INT, K, E, IN, JN, MU_LAM, MU_MAX):
    for J in range(1, JN + 1):
        for I in range(1, IN + 1):
            if E[I, J] <= 0.:
                continue
            mu = C_MU * A[I, J, NRO3] * K[I, J] * K[I, J] / E[I, J] + MU_LAM
            A[I, J, NMU] = mu if mu < MU_MAX else MU_MAX
