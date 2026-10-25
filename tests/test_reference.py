"""Сверка Python-версии с программой на Фортране.

Эталоны в tests/data получены из исходных RK1-RK7.FOR (met21_ispr):
    ref64_*: gfortran -std=legacy -fdefault-real-8 *.FOR   (двойная точность)
    ref32_*: gfortran -std=legacy *.FOR                    (как в оригинале, REAL*4)
"""

import os

import numpy as np
import pytest

from metan import Params, Solver

DATA = os.path.join(os.path.dirname(__file__), "data")


def _read(name):
    with open(os.path.join(DATA, name)) as fh:
        return fh.read().splitlines()


def _fields(lines):
    rows = [l.split() for l in lines if not l.startswith("0")]
    return np.array([[float(x) for x in r] for r in rows])


@pytest.fixture(scope="module")
def res64():
    return Solver(Params(model="original")).run()


@pytest.fixture(scope="module")
def res32():
    return Solver(Params(precision="float32", model="original")).run()


def test_float64_protocol_identical(res64):
    assert res64.text10 == _read("ref64_shi10.dat")


def test_float64_fields_identical(res64):
    assert res64.text20 == _read("ref64_shi20.dat")


def test_float32_protocol_identical(res32):
    # включая расходимость вариантов 2-5 (NITER=2203), как в оригинале
    assert res32.text10 == _read("ref32_shi10.dat")


def test_float32_first_variant_fields_close(res32):
    n = 46 * 22
    ref = _fields(_read("ref32_shi20.dat"))[:n]
    got = _fields(res32.text20)[:n]
    for k in range(6):
        scale = np.max(np.abs(ref[:, k]))
        assert np.max(np.abs(ref[:, k] - got[:, k])) <= 1e-3 * scale


def test_results_structure(res64):
    assert len(res64.variants) == 5
    v = res64.variants[0]
    assert v.fkomp_kind == "OK" and abs(v.fkomp - 0.98333) < 1e-5
    assert not any(x.diverged for x in res64.variants)
