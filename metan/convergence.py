"""Оценка сходимости итераций по сетке - до расчёта.

Функция тока ψ на каждой итерации обновляется одним проходом
Гаусса-Зейделя по эллиптическому уравнению (EQN, метка 177). Скорость его
сходимости задаётся спектральным радиусом ρ итерационной матрицы: за одну
итерацию медленная часть ошибки уменьшается в 1/ρ раз. ρ зависит только от
сетки (числа узлов, неравномерности шагов, отношения Δx/Δr) и формы
области, поэтому его можно найти до расчёта.

Число итераций до установления (изменение ψ и T за итерацию < 10⁻⁵):
    n₀   = ln(10⁻³) / ln(ρ_ГЗ),  ρ_ГЗ = ρ_Я²   - для одного уравнения ψ;
    Nуст = 1.15 · 23.9 · n₀^0.703           - для всей связанной системы.
ρ_Я - спектральный радиус метода Якоби для оператора ψ (для таких
разностных схем ρ_ГЗ = ρ_Я²). Вместе с ψ устанавливаются вихрь,
температура и состав; их связь и мгновенная реакция определяют темп, и
зависимость от n₀ подобрана по расчётам на 8 сетках от 46×22 до 300×66
(фактическое число итераций 1222 … 11 804, отклонение формулы от расчёта
±11 %); множитель 1.15 - запас.
"""



import numpy as np

from .kernels import NRO3


def _jacobi_operator(pv, rho_field=True):
    """Коэффициенты уравнения для ψ (как в EQN) во внутренних узлах."""
    from .solver import Solver  # noqa: F401  (тип pv - VariantResult)
    g = pv.grid
    IN, JN = g["IN"], g["JN"]
    X1, X2 = pv.X1, pv.X2
    R = X2.copy()
    R[1] = R[2] * 0.5 if R[1] == 0 else R[1]
    A = pv.A
    rho = A[:, :, NRO3] if rho_field else np.ones(A.shape[:2])
    rho = np.where(rho > 0, rho, 1.0)
    BE = np.zeros(IN + 2)
    BW = np.zeros(IN + 2)
    for I in range(2, IN):
        DX1 = 1. / (X1[I + 1] - X1[I - 1])
        BW[I] = DX1 / (X1[I] - X1[I - 1])
        BE[I] = DX1 / (X1[I + 1] - X1[I])
    BN = np.zeros(JN + 2)
    BS = np.zeros(JN + 2)
    for J in range(2, JN):
        DX2 = 0.5 / (X2[J + 1] - X2[J - 1])
        BS[J] = (1. + R[J - 1] / R[J]) / (X2[J] - X2[J - 1]) * DX2
        BN[J] = (1. + R[J + 1] / R[J]) / (X2[J + 1] - X2[J]) * DX2
    mask = np.zeros((IN + 1, JN + 1), bool)
    for J in range(2, JN):
        IL, IM = int(pv.IMIN[J]), int(pv.IMAX[J])
        if J == g["JA3"]:
            IL = g["IC2"] + 1
        if J == g["JC"]:
            IM = g["IC"] - 1
        mask[max(IL, 2):min(IM, IN - 1) + 1, J] = True
    cE = np.zeros_like(rho[:IN + 1, :JN + 1])
    cW, cN, cS = cE.copy(), cE.copy(), cE.copy()
    I, J = np.nonzero(mask)
    r = R[J]
    p = rho[I, J]
    cE[I, J] = 4. / (rho[I + 1, J] + p) / r ** 2 * BE[I]
    cW[I, J] = 4. / (rho[I - 1, J] + p) / r ** 2 * BW[I]
    cN[I, J] = 16. / (rho[I, J + 1] + p) / (R[J + 1] + r) ** 2 * BN[J]
    cS[I, J] = 16. / (rho[I, J - 1] + p) / (R[J - 1] + r) ** 2 * BS[J]
    d = cE + cW + cN + cS
    d[d == 0] = 1.
    return mask, cE / d, cW / d, cN / d, cS / d


def jacobi_radius(pv, iters=2000, tol=1e-9):
    """Спектральный радиус метода Якоби (степенной метод)."""
    mask, e, w, n, s = _jacobi_operator(pv)
    # начальное приближение - гладкая «первая мода»: так степенной метод
    # сходится за сотни итераций даже на больших сетках
    ii = np.arange(mask.shape[0])[:, None]
    jj = np.arange(mask.shape[1])[None, :]
    x = np.where(mask, np.sin(np.pi * ii / mask.shape[0])
                 * np.sin(np.pi * jj / mask.shape[1]) + 1e-3, 0.0)
    x /= np.linalg.norm(x)
    lam = 0.
    for k in range(iters):
        y = np.zeros_like(x)
        y[1:-1, 1:-1] = (e[1:-1, 1:-1] * x[2:, 1:-1] + w[1:-1, 1:-1] * x[:-2, 1:-1]
                         + n[1:-1, 1:-1] * x[1:-1, 2:] + s[1:-1, 1:-1] * x[1:-1, :-2])
        y[~mask] = 0.
        nrm = np.linalg.norm(y)
        if nrm == 0:
            return 0.
        new = nrm
        x = y / nrm
        if abs(new - lam) < tol * new and k > 50:
            lam = new
            break
        lam = new
    return float(lam)


def estimate(params, eps=1e-3):
    """dict(rho=ρ_ГЗ, n_req=N_уст) для параметров расчёта (до расчёта)."""
    from .solver import Solver
    pv = Solver(params).preview()
    rj = jacobi_radius(pv)
    rgs = rj * rj
    if rgs >= 1:
        return dict(rho=rgs, n_req=float("inf"))
    n0 = np.log(eps) / np.log(rgs)
    from .refined import temperature_mode
    k = MODEL_FACTOR.get(temperature_mode(params), 1.0)
    return dict(rho=rgs, n_req=float(FIT_C * SAFETY * k * n0 ** FIT_P),
                n0=float(n0))


# ----------------------------------------------------------------------
# Турбулентное число Рейнольдса камеры - критерий устойчивости
#
#     Reт = 4·ṁ / (π·Dк·μ̄т),
#
# μ̄т - средняя турбулентная вязкость в камере (за предкамерой). Чем
# меньше вязкость, тем сильнее течение в зоне обратных токов за уступом
# склонно колебаться; выше предела стационарное решение не находится,
# сколько ни увеличивай число итераций. Пределы - по расчётам с вязкостью,
# уменьшенной в 1…3.3 раза (pк 0.5…2 МПа, α 0.8…1, Dк 24…30 мм, сетки
# 46×22 и 100×44): устанавливалось при Reт ≤ 76…102, не устанавливалось
# при Reт ≥ 96…133. Алгебраическая вязкость программы даёт Reт ≈ 30…50
# при любом давлении (вязкость пропорциональна плотности).
RE_STABLE, RE_UNSTABLE = 75.0, 130.0


def reynolds_of(v, params):
    """Reт по полю расчёта (VariantResult)."""
    from .kernels import NMU
    g = v.grid
    mu = v.A[g["IC2"] + 1:g["IN"], 2:g["JN"], NMU]
    mu = mu[mu > 0]
    ms = v.values.get("Ms", 0.0)
    if mu.size == 0 or not ms:
        return float("nan")
    return float(4 * ms / (np.pi * params.DKS * 1e-3 * mu.mean()))


def reynolds(params, iters=100):
    """Оценка Reт до расчёта: 100 итераций на сетке 46×22 той же камеры
    (доли секунды; отличие от установившегося значения 2…15 %)."""
    import dataclasses
    from .solver import Solver
    q = dataclasses.replace(params, NVARM=1, NMAX=iters, STOP_TOL=0,
                            IN=min(params.IN, 46), JN=min(params.JN, 22))
    try:
        q.validate()
    except Exception:
        q = dataclasses.replace(params, NVARM=1, NMAX=iters, STOP_TOL=0)
    res = Solver(q, track_history=False).run()
    return reynolds_of(res.variants[0], q)


def stability(re):
    """'ok' / 'edge' / 'bad' по Reт."""
    if not re == re:
        return None
    return "ok" if re <= RE_STABLE else ("edge" if re < RE_UNSTABLE else "bad")


FIT_C, FIT_P, SAFETY = 23.9, 0.703, 1.15
# Поправка на модель температуры: формула подобрана для исходной модели;
# сглаженная сходится так же, равновесная - в 1.16-1.37 раза дольше
# (сетки 46×22 … 150×60: 1479, 4092, 4337, 6443 итерации против 1222,
# 2714, 2910, 5088).
# EDM и равновесное горение (46×22, α = 1) устанавливаются за 1142 и 1148
# итераций - как равновесная температура, с запасом.
MODEL_FACTOR = {0: 1.0, 1: 1.0, 2: 1.35, 3: 1.35}
