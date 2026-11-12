"""Программный интерфейс: расчёт камеры как модуль другой программы.

Пример (Python):

    from metan import api
    out = api.run({"P": 1e6, "ALFA": 1.0, "DKR": 8.0})
    out["variants"][0]["phi_k"]          # полнота сгорания φк

Другие языки и программы - через JSON:

    python -m metan --json-in вход.json --json-out результат.json
    Metan.exe --cli --json-in вход.json --json-out результат.json

вход.json - словарь параметров (имена - как в Params, см. --dump-params);
результат.json - словарь, который возвращает run().

Термодинамическое ядро подключается через metan.thermo.set_backend() -
например, ядро программы «Астра» вместо встроенного расчёта.
"""

import json
import math

from . import __version__


def _num(x):
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else x


def run(params=None, progress=None, cancel=None):
    """Расчёт. params - Params, словарь параметров или None (по умолчанию).
    Возвращает словарь (JSON-совместимый): версия, параметры, время расчёта,
    результаты по вариантам α."""
    from .analysis import exit_summary
    from .params import Params
    from .refined import describe
    from .solver import Solver
    if params is None:
        p = Params()
    elif isinstance(params, Params):
        p = params
    else:
        d = Params().to_dict()
        d.update(params)
        p = Params.from_dict(d)
    res = Solver(p, progress=progress, cancel=cancel,
                 track_history=False).run()
    out = dict(program="Metan", version=__version__, model=describe(p),
               params=p.to_dict(), elapsed_s=_num(res.elapsed),
               variants=[])
    for v in res.variants:
        ex = exit_summary(v)
        val = v.values
        row = dict(
            alpha=_num(val["ALFA"]), Km=_num(val["KM"]),
            beta=_num(val["BETA"]), mass_flow=_num(val["Ms"]),
            phi_k=_num(v.fkomp), phi_beta=_num(v.extra.get("FIbeta", "nan")),
            T_exit=_num(ex["T"]),
            exit_mass_fractions={k: _num(x) for k, x in ex.items()
                                 if k != "T"},
            iterations=int(v.NITER), settled=v.settled,
            diverged=bool(v.diverged))
        u = v.extra.get("unsteady")
        if u is not None:
            row["unsteady"] = dict(
                residence_time_s=_num(u["tau"]), dt_s=_num(u["dt"]),
                steps=int(u["steps"]), phi_k_std=_num(u["fk_std"]),
                phi_k_t=[_num(x) for x in u["fk_t"]],
                t_s=[_num(x) for x in u["t"]])
        out["variants"].append(row)
    return out


def run_json(in_path, out_path):
    """Параметры из JSON-файла, результат - в JSON-файл."""
    with open(in_path, encoding="utf-8") as fh:
        params = json.load(fh) if in_path else {}
    out = run(params)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return out
