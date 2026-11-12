"""Программный интерфейс и подключаемое термодинамическое ядро."""
import json

import numpy as np

from metan import api, thermo
from metan.params import Params
from metan.solver import Solver


def test_api_run_json_serializable():
    out = api.run({"ALFA": 1.0, "NMAX": 200})
    s = json.dumps(out)
    assert "phi_k" in s and out["variants"][0]["alpha"] == 1.0


def test_thermo_backend_switch():
    """Другое ядро подставляется вместо встроенного (например, «Астра»)."""
    calls = []

    class Fake:
        name = "проверочное"

        def adiabatic_table(self, P, h_fuel, h_ox=0.0, n=401):
            calls.append(P)
            f = np.linspace(0, 1, n)
            return f, np.full(n, 2000.0), np.full(n, 2.0), f * h_fuel

    try:
        thermo.set_backend(Fake())
        v = Solver(Params(TMODEL=2, NMAX=50)).run().variants[0]
    finally:
        thermo.set_backend(None)
    assert calls, "ядро не вызывалось"
    assert np.nanmax(v.A[2:-2, 2:-2, 13]) < 2600   # T около 2000 K
