"""Командная строка.

    python -m metan                      # расчёт с параметрами по умолчанию
    python -m metan -p params.json -o out
    python -m metan --set ALFA=0.7 --set NVARM=3 --precision float32
    python -m metan --dump-params params.json   # сохранить параметры по умолчанию
    python -m metan gui                  # десктопная программа
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
        from .gui import main as gui_main
        return gui_main()

    ap = argparse.ArgumentParser(prog="metan",
                                 description="Расчёт горения метана (перевод met21 с Фортрана)")
    ap.add_argument("-p", "--params", help="JSON-файл с параметрами")
    ap.add_argument("-o", "--outdir", default=".", help="папка для shi10.dat / shi20.dat")
    ap.add_argument("--set", action="append", default=[], metavar="ИМЯ=ЗНАЧЕНИЕ",
                    help="изменить параметр (можно несколько раз)")
    ap.add_argument("--precision", choices=["float64", "float32"],
                    help="точность (по умолчанию float64)")
    ap.add_argument("--dump-params", metavar="ФАЙЛ",
                    help="записать параметры в JSON и выйти")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args(argv)

    d = Params().to_dict()
    if a.params:
        d.update(Params.load(a.params).to_dict())
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

    from .solver import Solver
    res = Solver(params, progress=None if a.quiet else _progress).run()
    if not a.quiet:
        sys.stderr.write("\n")
    p10, p20 = res.write_files(a.outdir)
    if not a.quiet:
        for v in res.variants:
            print("Вариант %d: ALFA=%.2f  NITER=%d  Fkomp(%s)=%.5f%s" % (
                v.NVAR, v.values["ALFA"], v.NITER, v.fkomp_kind, v.fkomp,
                "  (расходимость!)" if v.diverged else ""))
        print("Время расчёта: %.1f с" % res.elapsed)
        print("Записано:", p10, p20)
    return 0
