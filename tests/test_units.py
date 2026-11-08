import json

import pytest

from metan import Params
from metan.fortran_format import fmt_e, fmt_f, fmt_i


def test_fmt_e():
    assert fmt_e(1.0e6, 11, 4) == " 0.1000E+07"
    assert fmt_e(-0.00425, 11, 3) == " -0.425E-02"
    assert fmt_e(0.0, 11, 3) == "  0.000E+00"
    assert fmt_e(1e-20, 11, 3) == "  0.100E-19"


def test_fmt_f_i():
    assert fmt_f(0.8, 6, 2) == "  0.80"
    assert fmt_f(1882.4, 6, 1) == "1882.4"
    assert fmt_f(123456.0, 6, 1) == "******"
    assert fmt_i(45, 3) == " 45"


def test_params_roundtrip(tmp_path):
    p = Params(ALFA=0.7, NVARM=2)
    f = tmp_path / "p.json"
    p.save(f)
    q = Params.load(f)
    assert q == p
    assert json.loads(f.read_text(encoding="utf-8"))["ALFA"] == 0.7


def test_params_validation():
    with pytest.raises(ValueError):
        Params(JZ=10, GRID_AUTO=0).validate()
    with pytest.raises(ValueError):
        Params(JN=8).validate()
    with pytest.raises(ValueError):
        Params.from_dict({"NOPE": 1})


def test_alfa_list():
    assert Params().alfa_list() == [1.0]
    assert Params.fortran().alfa_list() == [0.8, 1.0, 1.2, 1.4, 1.6]


def test_auto_grid():
    from metan.params import auto_grid
    g = auto_grid(Params())
    p = Params()
    assert 1 < g["JZ"] < g["JZ1"] < g["JA"] < g["JA3"] < g["JA1"] < g["JA2"] < p.JN
    assert 1 < g["IC2"] < g["IC1"] < g["IC"] < p.IN
    # шире щель - больше узлов на неё
    g2 = auto_grid(Params(DELOK=1.2))
    assert g2["JA2"] - g2["JA1"] >= g["JA2"] - g["JA1"]


def test_derived_nodes_default_is_fortran_grid():
    from metan.params import auto_grid
    g = auto_grid(Params(GRID_AUTO=2))
    assert (g["JC"], g["IC"], g["IC1"]) == (6, 45, 29)
    assert auto_grid(Params(GRID_AUTO=2, DKR=10))["JC"] > g["JC"]
    with pytest.raises(ValueError):
        Params(GRID_AUTO=2, JZ=7).validate()     # границы не по порядку


def test_fine_grid_converges():
    # раньше на сетке 80x40 появлялся интервал нулевой ширины у горла
    import numpy as np
    from metan import Solver
    p = Params(IN=80, JN=40, GRID_AUTO=1, NMAX=300)
    v = Solver(p).run().variants[0]
    assert not v.diverged
    assert np.diff(v.X2[1:41]).min() > 0


def test_convergence_estimate_grows_with_grid():
    from metan.convergence import estimate
    a = estimate(Params())
    b = estimate(Params(IN=100, JN=44, GRID_AUTO=1))
    assert 0 < a["rho"] < b["rho"] < 1
    assert 500 < a["n_req"] < 3000 and b["n_req"] > 2 * a["n_req"]


def test_auto_stop():
    from metan import Solver
    v = Solver(Params(NMAX=5000), track_history=False).run().variants[0]
    assert v.settled is True and 600 < v.NITER < 3000
    f = Solver(Params.fortran(NVARM=1), track_history=False).run().variants[0]
    assert f.settled is None and f.NITER == 1000
