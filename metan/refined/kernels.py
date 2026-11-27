"""Вычислительные ядра модели горения EDM (numba).

* edm_step   - горение с конечной скоростью по модели вихревого распада
               (Eddy Dissipation, Магнуссен - Хьертагер);

Обозначения массивов и порядок обхода узлов - как в metan/kernels.py.
"""

from ..kernels import (NMDF, NMFU1, NMFU2, NMOX1, NMOX2, NMPR1, NMPR2,
                       NRO3, HAVE_NUMBA)
from ..kernels import jit as _jit_plain

if HAVE_NUMBA:
    from numba import njit as _njit
    from ..kernels import _CACHE

    def jit(f):
        # с проверкой границ массивов: ошибка индекса - сообщение, а не
        # аварийное завершение программы (эти ядра - малая часть времени)
        return _njit(cache=_CACHE, nogil=True, boundscheck=True)(f)
else:
    jit = _jit_plain

# Массовые доли продуктов на 1 кг сгоревшего CH4 для брутто-реакции модели
# 24 CH4 + 47 O2 -> 8 CO2 + 16 CO + 2 H2 + 30 H2O + 32 OH (как в EQN)
S_O2 = 47. * 32. / (24. * 16.)          # 3.9166 кг O2 на 1 кг CH4
P_CO2 = 8. * 44. / (24. * 16.)
P_CO = 16. * 28. / (24. * 16.)
P_H2 = 4. / (24. * 16.)
P_H2O = 30. * 18. / (24. * 16.)
P_OH = 32. * 17. / (24. * 16.)

C_MU = 0.09


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
