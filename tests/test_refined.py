"""Совместимость старых параметров и сеточные исследования."""
from metan import Params, Solver, studies
import numpy as np


def test_old_combustion_params_load_as_instantaneous():
    old = {"UNSTEADY": 1, "COMB": 1, "EDM_A": 3.0, "T_AVG": 1.0,
           "DT_STEPS": 40, "INNER": 20, "NMAX": 60}
    params = Params.from_dict(old)
    assert params == Params(NMAX=60)
    for name in ("COMB", "EDM_A", "UNSTEADY"):
        assert name not in params.to_dict()
    saved = Solver(params).run().variants[0]
    current = Solver(Params(NMAX=60)).run().variants[0]
    assert np.array_equal(saved.A, current.A)


def test_old_temperature_param_loads_as_original():
    assert Params.from_dict({"TMODEL": 1, "COMB": 2}).TMODEL == 0


def test_gci3():
    r = 2 ** 0.5
    f = [1 + h ** 2 for h in (0.4, 0.4 / r, 0.4 / r / r)]
    g = studies.gci3(*f, r)
    assert abs(g["p"] - 2) < 1e-6 and g["kind"] == "monotone"
    g = studies.gci3(0.7858, 0.7873, 0.7894, r)
    assert g["kind"] == "noise" and g["gci"] < 2


def test_grid_study_small():
    st = studies.grid_study(Params(NMAX=300, STOP_TOL=0), start=(46, 22),
                            levels=3)
    assert len(st.results) == 3 and len(st.gcis) == 1
    assert st.params[1].IN == 65 and st.params[2].IN == 92
