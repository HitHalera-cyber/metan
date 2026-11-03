"""Обозначения результатов в окне программы, на графиках и в отчёте.

Приняты обозначения учебников по ЖРД (Алемасов, Добровольский и др.).
Имена из Фортрана остаются в файлах shi10.dat/shi20.dat и в JSON.
"""

from .params import Params

# код результата -> (обозначение, название, единица)
RESULTS = {
    "fkomp": ("φк", "коэффициент полноты сгорания", ""),
    "eta": ("ηсг", "массовая полнота сгорания", ""),
    "FIbeta": ("φβ", "коэффициент расходного комплекса (по смешению)", ""),
    "ALFA": ("α", "коэффициент избытка окислителя", ""),
    "KM": ("Km", "массовое соотношение компонентов", ""),
    "BETA": ("β", "расходный комплекс", "м/с"),
    "Ms": ("ṁ", "расход топлива", "кг/с"),
    "Mok": ("ṁок", "расход окислителя", "кг/с"),
    "Mgor": ("ṁг", "расход горючего", "кг/с"),
    "Mcmw": ("ṁц", "расход центральной струи", "кг/с"),
    "Vgor": ("wг", "скорость горючего на входе", "м/с"),
    "Vok": ("wок", "скорость окислителя на входе", "м/с"),
    "Vcmw": ("wц", "скорость центральной струи", "м/с"),
    "Vokr": ("wокр", "окружная скорость на входе", "м/с"),
    "ROg": ("ρг", "плотность горючего на входе", "кг/м³"),
    "ROok": ("ρок", "плотность окислителя на входе", "кг/м³"),
    "NITER": ("N", "число итераций", ""),
    "exit_T": ("Tвых", "температура на выходе (среднемассовая)", "K"),
    "exit_CH4": ("gCH4 вых", "доля CH4 на выходе", ""),
    "exit_O2": ("gO2 вых", "доля O2 на выходе", ""),
    "exit_CO2": ("gCO2 вых", "доля CO2 на выходе", ""),
}

# обозначения исходных данных (код Фортрана -> обозначение)
PARAMS = {n: (m["sym"] or n, m["label"], m["unit"])
          for n, _, m in Params.field_info()}


def sym(code):
    """Обозначение величины: 'fkomp' -> 'φк', 'DKR' -> 'dкр'."""
    if code in RESULTS:
        return RESULTS[code][0]
    if code in PARAMS:
        return PARAMS[code][0]
    return code


def label(code, with_unit=True):
    """'dкр, мм' / 'φк'."""
    s = sym(code)
    u = RESULTS.get(code, PARAMS.get(code, ("", "", "")))[2]
    return "%s, %s" % (s, u) if (with_unit and u) else s


def title(code):
    """'Диаметр критического сечения dкр'."""
    t = RESULTS.get(code, PARAMS.get(code))
    if not t:
        return code
    name = t[1][0].upper() + t[1][1:]
    return "%s %s" % (name, t[0])


# Таблица переименований для руководства: (Фортран, обозначение, смысл)
def renames():
    out = []
    for n, _, m in Params.field_info():
        if m.get("hidden") or not m.get("sym"):
            continue
        out.append((n, m["sym"], m["label"]))
    for code, ftn in (("ALFA", "ALFA"), ("KM", "KM"), ("BETA", "BETA"),
                      ("Ms", "Ms"), ("Mok", "Mok"), ("Mgor", "Mgor"),
                      ("Vgor", "Vgor"), ("Vok", "Vok"), ("Vcmw", "Vcmw"),
                      ("ROg", "ROg"), ("ROok", "ROok"), ("NITER", "NITER"),
                      ("fkomp", "Fkomp"), ("FIbeta", "FIbeta")):
        s, name, _ = RESULTS[code]
        out.append((ftn, s, name))
    return out
