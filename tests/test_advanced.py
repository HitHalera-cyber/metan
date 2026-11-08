"""Экспериментальная вкладка «Уточнённая модель» (metan/advanced)."""
import numpy as np
import pytest

from metan import Params
from metan.advanced import model as M


def small(**kw):
    d = dict(ALFA=1.0, NVARM=1, NMAX=80, IN=46, JN=22)
    d.update(kw)
    return Params(**d)


@pytest.mark.parametrize("comb,turb", [("instant", "algebraic"),
                                       ("edm", "algebraic"),
                                       ("equil", "algebraic"),
                                       ("edm", "keps")])
def test_models_run(comb, turb):
    opt = M.AdvOptions(combustion=comb, turbulence=turb)
    v = M.run(small(), opt, track_history=False).variants[0]
    assert not v.diverged
    assert 0.0 <= v.fkomp <= 1.0 + 1e-9
    assert np.all(np.isfinite(v.A[2:-1, 2:-1, :]))
    assert v.extra["model"] == opt.describe()


def test_instant_algebraic_is_base_solver():
    """Без уточнений вкладка считает так же, как основная программа
    (с равновесной температурой)."""
    from metan import Solver
    p = small(TMODEL=2)
    a = Solver(p).run().variants[0]
    b = M.run(p, M.AdvOptions(combustion="instant", turbulence="algebraic",
                              tmodel=2)).variants[0]
    assert abs(a.fkomp - b.fkomp) < 1e-12


def test_equilibrium_table_limits():
    tab = M.equilibrium_table(1e6, -4681.06e3)
    assert tab is not None


def test_gci3():
    # f = 1 + h²: точный порядок 2
    r = 2 ** 0.5
    f = [1 + (h) ** 2 for h in (0.4, 0.4 / r, 0.4 / r / r)]
    g = M.gci3(*f, r)
    assert abs(g["p"] - 2) < 1e-6
    assert abs(g["ext"] - 1) < 1e-9
    assert g["kind"] == "monotone"


def test_gci3_noise():
    g = M.gci3(0.7858, 0.7873, 0.7894, 2 ** 0.5)
    assert g["kind"] == "noise" and g["gci"] < 2
