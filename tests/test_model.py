"""Исправленные формулы Fkomp/FIbeta (model=corrected)."""
import numpy as np

from metan import Params, Solver


def test_fields_do_not_depend_on_model():
    a = Solver(Params(NVARM=2, NMAX=60, model="original")).run()
    b = Solver(Params(NVARM=2, NMAX=60, model="corrected")).run()
    assert a.text20 == b.text20
    for va, vb in zip(a.variants, b.variants):
        assert np.array_equal(va.A, vb.A)


def test_corrected_coefficients_physical():
    r = Solver(Params(ALFA=0.4, DALFA=0.2, NVARM=6)).run()
    for v in r.variants:
        assert 0.0 <= v.fkomp <= 1.0
        assert 0.0 < v.extra["eta"] <= 1.0
        # в оригинале при alfa = 1.2..1.6 получалось FIbeta = 1.025..1.074
        assert v.extra["FIbeta"] < 1.0
        a = v.values["ALFA"]
        assert v.fkomp_kind == ("GOR" if a * 4 / 3.9166 >= 1 else "OK")
