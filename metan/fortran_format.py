"""Форматированный вывод в стиле FORMAT-дескрипторов Фортрана (gfortran).

Нужен, чтобы файлы shi10.dat / shi20.dat, которые пишет Python-версия,
совпадали по виду с файлами, которые писала программа на Фортране.
"""

import math


def _overflow(w):
    return "*" * w


def fmt_e(x, w, d):
    """Дескриптор Ew.d: ' 0.1000E+07'."""
    x = float(x)
    if math.isnan(x):
        return "NaN".rjust(w)
    if math.isinf(x):
        s = ("-" if x < 0 else "") + ("Infinity" if w >= 9 else "Inf")
        return s.rjust(w) if len(s) <= w else _overflow(w)
    if x == 0.0:
        mant = "0." + "0" * d
        exp = 0
        sign = "-" if math.copysign(1.0, x) < 0 else ""
    else:
        sign = "-" if x < 0 else ""
        # d значащих цифр, мантисса вида 0.ddd
        s = "%.*e" % (d - 1, abs(x))
        m, e = s.split("e")
        digits = m.replace(".", "")
        exp = int(e) + 1
        mant = "0." + digits
    if abs(exp) <= 99:
        es = "E%+03d" % exp
    elif abs(exp) <= 999:
        es = "%+04d" % exp
    else:
        return _overflow(w)
    s = sign + mant + es
    if len(s) > w:
        # gfortran опускает ведущий ноль, если не хватает места
        s = sign + mant[1:] + es
        if len(s) > w:
            return _overflow(w)
    return s.rjust(w)


def fmt_f(x, w, d):
    """Дескриптор Fw.d."""
    x = float(x)
    if math.isnan(x):
        return "NaN".rjust(w)
    if math.isinf(x):
        s = "-Inf" if x < 0 else "Inf"
        return s.rjust(w) if len(s) <= w else _overflow(w)
    s = "%.*f" % (d, x)
    if len(s) > w and s.startswith("0."):
        s = s[1:]
    elif len(s) > w and s.startswith("-0."):
        s = "-" + s[2:]
    if len(s) > w:
        return _overflow(w)
    return s.rjust(w)


def fmt_i(n, w):
    """Дескриптор Iw."""
    s = "%d" % int(n)
    if len(s) > w:
        return _overflow(w)
    return s.rjust(w)
