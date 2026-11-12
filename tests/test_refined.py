"""Уточнённые модели горения и турбулентности, сеточное исследование."""
import numpy as np
import pytest

from metan import Params, Solver, studies


@pytest.mark.parametrize("comb,turb", [(1, 0), (0, 0)])
def test_models_run(comb, turb):
    p = Params(COMB=comb, TURB=turb, NMAX=120)
    v = Solver(p, track_history=False).run().variants[0]
    assert not v.diverged
    assert 0.0 <= v.fkomp <= 1.0 + 1e-9
    assert np.all(np.isfinite(v.A[2:-2, 2:-2, :]))
    assert ("model" in v.extra) == (comb != 0)


def test_base_unchanged_by_refined_code():
    """COMB = 0, TURB = 0 - точно основная программа."""
    p = Params(NMAX=200)
    a = Solver(p).run().variants[0]
    b = Solver(Params(NMAX=200, COMB=0, TURB=0, EDM_A=2.0)).run().variants[0]
    assert np.array_equal(a.A, b.A)


def test_edm_settles_and_burns_less():
    v = Solver(Params(COMB=1)).run().variants[0]
    assert v.settled
    assert 0.6 < v.fkomp < 0.9


def test_unsteady_run():
    """Нестационарный расчёт: установление, шаги по времени, осреднение."""
    p = Params(UNSTEADY=1, T_AVG=1.0, DT_STEPS=40, INNER=20, NMAX=600)
    v = Solver(p).run().variants[0]
    u = v.extra["unsteady"]
    assert not v.diverged
    assert u["steps"] == 120 and u["averaged_steps"] == 40
    assert 0.5 < v.fkomp <= 1.0 and 0.3e-3 < u["tau"] < 2e-3
    assert "k–ε" in v.extra["model"]


def test_old_param_files():
    """Сглаженная температура и равновесное горение убраны: в старых
    файлах заменяются исходными моделями."""
    p = Params.from_dict({"TMODEL": 1, "COMB": 2})
    assert p.TMODEL == 0 and p.COMB == 0


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
