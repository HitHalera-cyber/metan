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
        Params(JZ=10).validate()
    with pytest.raises(ValueError):
        Params.from_dict({"NOPE": 1})


def test_alfa_list():
    assert [round(a, 6) for a in Params().alfa_list()] == [0.8, 1.0, 1.2, 1.4, 1.6]
