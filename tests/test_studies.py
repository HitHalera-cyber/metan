import numpy as np

from metan import Params, Solver, analysis, studies
from metan.kernels import NT


def small(**kw):
    d = dict(NVARM=2, NMAX=60, NPRINT=20)
    d.update(kw)
    return Params(**d)


def test_history_and_snapshots():
    r = Solver(small(), snapshot_every=20).run()
    v = r.variants[0]
    assert len(v.history["iter"]) == 60
    assert set(v.history) >= {"psi", "T", "CH4", "omega"}
    assert [it for it, _ in v.snapshots] == [1, 20, 40, 60]


def test_preview_matches_run_grid():
    p = small()
    pv = Solver(p).preview()
    r = Solver(p).run()
    assert pv.grid == r.variants[0].grid
    assert np.allclose(pv.X1, r.variants[0].X1)


def test_series_and_summary():
    s = studies.run_series(small(), "DKR", [7.0, 8.0])
    assert [row[0] for row in s.rows] == [7.0, 8.0]
    x, y = s.curve("fkomp", 1)
    assert len(x) == 2 and np.all(np.isfinite(y))
    assert s.alphas() == [0.8, 1.0] or np.allclose(s.alphas(), [0.8, 1.0])


def test_series_bad_geometry_reported():
    s = studies.run_series(small(), "DKR", [30.0])   # больше Dks
    assert s.rows[0][1] is None and s.rows[0][2]


def test_optimize_runs():
    o = studies.optimize(small(), ["DKR"], [(7.0, 9.0)], alpha=0.8, max_evals=5)
    assert o.best_f >= o.start_f
    assert 7.0 <= o.best_x[0] <= 9.0


def test_refined_params_keep_geometry():
    p = Params()
    f = studies.refined_params(p)
    a, b = Solver(p).preview(), Solver(f).preview()
    for key_a in ("JZ", "JZ1", "JA", "JA3", "JA1", "JA2", "JN"):
        assert np.isclose(a.X2[a.grid[key_a]], b.X2[b.grid[key_a]])
    for key in ("IC2", "IC1", "IC", "IN"):
        assert np.isclose(a.X1[a.grid[key]], b.X1[b.grid[key]])
    assert b.grid["JN"] == 2 * a.grid["JN"] - 1


def test_analysis():
    r = Solver(small()).run()
    v = r.variants[0]
    ex = analysis.exit_summary(v)
    assert 293 <= ex["T"] <= 4500
    x, rr, D = analysis.difference(v, v, NT)
    assert np.nanmax(np.abs(np.ma.filled(D, 0))) == 0
    w = r.variants[1]
    x, rr, D = analysis.difference(v, w, NT)
    assert D.shape == (len(rr), len(x))
