"""Равновесный расчёт (metan/thermo.py) - сверка с программой Cantera
(GRI-Mech 3.0, равновесие HP, 1 МПа, CH4/O2 при 293 K)."""
import numpy as np

from metan import Params, Solver, thermo

# f (доля CH4), T, основные массовые доли - получены в Cantera 3.x
REF = [(0.10, 2996.8, {"O2": 0.4886, "CO2": 0.2365, "H2O": 0.1989}),
       (0.20, 3352.7, {"CO2": 0.2504, "H2O": 0.3458, "CO": 0.1898, "OH": 0.073}),
       (0.30, 3036.2, {"H2O": 0.3815, "CO": 0.4406, "H2": 0.0302})]


def test_equilibrium_matches_cantera():
    for f, Tref, comp in REF:
        Y0 = np.zeros(len(thermo.SPECIES))
        Y0[0], Y0[1] = f, 1 - f
        h = thermo.h_mass(293.0, Y0)
        T, Y, _ = thermo.equilibrium_HP(h, 1e6, thermo.elements_of(f))
        assert abs(T - Tref) < 1.0
        for sp, y in comp.items():
            assert abs(Y[thermo.SPECIES.index(sp)] - y) < 2e-3


def test_temperature_models_run():
    for tm in (1, 2):
        v = Solver(Params(TMODEL=tm, NMAX=4000), track_history=False).run().variants[0]
        assert v.settled and 0.9 < v.fkomp <= 1.0
