"""Командная строка.

    python -m metan                      # расчёт с параметрами по умолчанию
    python -m metan -p params.json -o out
    python -m metan --set ALFA=0.7 --set NVARM=3 --precision float32
    python -m metan --dump-params params.json   # сохранить параметры по умолчанию
    python -m metan gui                  # десктопная программа (новая)
    python -m metan --fortran            # данные точно как в исходной программе
"""

import argparse
import sys

from .params import Params


def _progress(nvar, nvarm, niter, nmax):
    sys.stderr.write("\rВариант %d/%d, итерация %d/%d   " % (nvar, nvarm, niter, nmax))
    sys.stderr.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "gui":
        from .app import main as gui_main
        return gui_main("dark" if "--dark" in argv else
                        ("light" if "--light" in argv else None))

    ap = argparse.ArgumentParser(prog="metan",
                                 description="Расчёт горения метана (перевод met21 с Фортрана)")
    ap.add_argument("-p", "--params", help="JSON-файл с параметрами")
    ap.add_argument("-o", "--outdir", default=".", help="папка для shi10.dat / shi20.dat")
    ap.add_argument("--set", action="append", default=[], metavar="ИМЯ=ЗНАЧЕНИЕ",
                    help="изменить параметр (можно несколько раз)")
    ap.add_argument("--precision", choices=["float64", "float32"],
                    help="точность (по умолчанию float64)")
    ap.add_argument("--fortran", action="store_true",
                    help="данные и формулы точно как в исходной программе met21 "
                         "(5 вариантов α, узлы сетки из BLOCK DATA)")
    ap.add_argument("--dump-params", metavar="ФАЙЛ",
                    help="записать параметры в JSON и выйти")
    ap.add_argument("--json-in", metavar="ФАЙЛ",
                    help="параметры из JSON (программный интерфейс metan.api)")
    ap.add_argument("--json-out", metavar="ФАЙЛ",
                    help="результаты в JSON (для другой программы)")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args(argv)

    d = (Params.fortran() if a.fortran else Params()).to_dict()
    if a.params:
        d.update(Params.load(a.params).to_dict())
    if a.json_in:
        import json
        with open(a.json_in, encoding="utf-8") as fh:
            d.update(json.load(fh))
    for s in a.set:
        if "=" not in s:
            ap.error("--set ожидает ИМЯ=ЗНАЧЕНИЕ, получено: %s" % s)
        k, v = s.split("=", 1)
        d[k.strip()] = v.strip()
    if a.precision:
        d["precision"] = a.precision
    try:
        params = Params.from_dict(d)
    except ValueError as e:
        ap.error(str(e))

    if a.dump_params:
        params.save(a.dump_params)
        print("Параметры записаны в", a.dump_params)
        return 0

    if a.json_out:
        from . import api
        import json
        out = api.run(params, progress=None if a.quiet else _progress)
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        if not a.quiet:
            sys.stderr.write("\nЗаписано: %s\n" % a.json_out)
        return 0

    from .solver import Solver
    res = Solver(params, progress=None if a.quiet else _progress).run()
    if not a.quiet:
        sys.stderr.write("\n")
    p10, p20 = res.write_files(a.outdir)
    if not a.quiet:
        for v in res.variants:
            print("Вариант %d: α=%.2f  N=%d  φк=%.5f%s" % (
                v.NVAR, v.values["ALFA"], v.NITER, v.fkomp,
                "  (расходимость!)" if v.diverged else ""))
        print("Время расчёта: %.1f с" % res.elapsed)
        print("Записано:", p10, p20)
    return 0
