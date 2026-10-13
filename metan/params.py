"""Исходные данные расчёта.

Значения по умолчанию взяты из BLOCK DATA (RK1.FOR) и из главной
программы (RK2.FOR) варианта met21_ispr. Все параметры можно менять:
из JSON-файла, из командной строки или в окне десктопной программы.
"""

import dataclasses
import json
from dataclasses import dataclass, field, fields


def _p(default, label, unit="", group="", help="", kind=None):
    return field(default=default, metadata=dict(
        label=label, unit=unit, group=group, help=help, kind=kind))


GROUPS = [
    ("mode", "Режим"),
    ("geom", "Геометрия (мм)"),
    ("grid", "Сетка"),
    ("calc", "Расчёт и вывод"),
]


@dataclass
class Params:
    # ---------------- Режим ----------------
    P: float = _p(10.0e5, "Давление в камере P", "Па", "mode",
                  "DATA P/10.E+5/")
    ALFA: float = _p(0.6, "Начальный коэф. избытка окислителя ALFA", "", "mode",
                     "Перед каждым вариантом ALFA увеличивается на шаг, поэтому "
                     "первый вариант считается при ALFA + шаг (0.6 + 0.2 = 0.8).")
    DALFA: float = _p(0.2, "Шаг ALFA между вариантами", "", "mode",
                      "В Фортране: ALFA=ALFA+0.2 в начале каждого варианта.")
    NVARM: int = _p(5, "Число вариантов NVARM", "", "mode", "DATA NVARM/5/")
    H: float = _p(-4681.06, "Энтальпия горючего H", "", "mode", "DATA H/-4681.06/")
    ROM1: float = _p(815.0, "Температура воспламенения ROM1", "K", "mode",
                     "Реакция идёт только при T >= ROM1. DATA ROM1/815./")
    AKT: float = _p(1.2, "Показатель адиабаты AKT", "", "mode", "DATA AKT/1.2/")
    ZMF2N: float = _p(1.0, "Массовая доля CH4 в горючем ZMF2N", "", "mode",
                      "DATA ZMF2N/1.00/")
    ZMO2N: float = _p(1.0, "Массовая доля O2 в окислителе ZMO2N", "", "mode",
                      "DATA ZMO2N/1.00/")
    NCORD: int = _p(2, "Система координат NCORD", "", "mode",
                    "2 - осесимметричная (R=X2), 1 - плоская (R=1).",
                    kind=(1, 2))

    # --------- Геометрия (мм, используется в первом варианте) ---------
    DKR: float = _p(8.0, "Диаметр критического сечения Dkr", "мм", "geom")
    DCMB: float = _p(2.0, "Диаметр центральной струи Dcmw", "мм", "geom")
    DOGOR: float = _p(8.0, "Диаметр подачи горючего DOGOR", "мм", "geom")
    DELGOR: float = _p(1.0, "Ширина щели горючего DELGOR", "мм", "geom")
    DKAR: float = _p(12.0, "Диаметр предкамеры Dprk", "мм", "geom")
    DOOK: float = _p(20.0, "Диаметр подачи окислителя Dook", "мм", "geom")
    DELOK: float = _p(0.4, "Ширина щели окислителя DELOK", "мм", "geom")
    DKS: float = _p(24.0, "Диаметр камеры сгорания Dks", "мм", "geom")
    DELKAR: float = _p(10.0, "Длина предкамеры Lprk", "мм", "geom")
    ALKS: float = _p(15.0, "Длина цилиндрической части КС Lks", "мм", "geom")
    ALKD: float = _p(42.239, "Длина до критического сечения Lkd", "мм", "geom")
    TGY: float = _p(0.573, "Тангенс угла сужения сопла tgY", "", "geom")

    # ---------------- Сетка ----------------
    IN: int = _p(46, "Число узлов по оси X1 (IN)", "", "grid")
    JN: int = _p(22, "Число узлов по радиусу X2 (JN)", "", "grid")
    JZ: int = _p(4, "Узел: граница центральной струи JZ", "", "grid")
    JZ1: int = _p(6, "Узел: внутр. граница горючего JZ1", "", "grid")
    JA: int = _p(9, "Узел: внешн. граница горючего JA", "", "grid")
    JA3: int = _p(12, "Узел: стенка предкамеры JA3", "", "grid")
    JA1: int = _p(15, "Узел: внутр. граница окислителя JA1", "", "grid")
    JA2: int = _p(18, "Узел: внешн. граница окислителя JA2", "", "grid")
    JC: int = _p(6, "Узел: критическое сечение JC (нач.)", "", "grid",
                 "Уточняется в GRID по диаметру Dkr.")
    IC: int = _p(45, "Узел: критическое сечение IC (нач.)", "", "grid",
                 "Уточняется в GRID.")
    IC1: int = _p(31, "Узел: начало сужения IC1 (нач.)", "", "grid",
                  "Пересчитывается в GRID.")
    IC2: int = _p(10, "Узел: конец предкамеры IC2", "", "grid")

    # ---------------- Расчёт и вывод ----------------
    NMAX: int = _p(1000, "Число итераций на вариант NMAX", "", "calc")
    NPRINT: int = _p(200, "Итераций без вихря NPRINT", "", "calc",
                     "Пока NITER <= NPRINT (в 1-м варианте) уравнение вихря "
                     "не решается, источник в уравнении функции тока = 0.")
    precision: str = _p("float64", "Точность вычислений", "", "calc",
                        "float64 - двойная (рекомендуется); float32 - как "
                        "REAL*4 в исходной программе (воспроизводит её "
                        "ошибки округления).",
                        kind=("float64", "float32"))
    out10: str = _p("shi10.dat", "Файл протокола (unit 7)", "", "calc")
    out20: str = _p("shi20.dat", "Файл полей (unit 9)", "", "calc")

    # ------------------------------------------------------------------
    @classmethod
    def field_info(cls):
        return [(f.name, f.type, f.metadata) for f in fields(cls)]

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d):
        known = {f.name: f for f in fields(cls)}
        kw = {}
        for k, v in d.items():
            if k not in known:
                raise ValueError("Неизвестный параметр: %s" % k)
            t = known[k].type
            if t in (int, "int"):
                kw[k] = int(v)
            elif t in (float, "float"):
                kw[k] = float(v)
            else:
                kw[k] = str(v)
        p = cls(**kw)
        p.validate()
        return p

    def save(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def validate(self):
        """Проверка согласованности. Возвращает self или бросает ValueError."""
        err = []
        if not (1 < self.JZ < self.JZ1 < self.JA < self.JA3 < self.JA1
                < self.JA2 < self.JN):
            err.append("Нужно 1 < JZ < JZ1 < JA < JA3 < JA1 < JA2 < JN")
        if not (1 < self.IC2 < self.IC < self.IN):
            err.append("Нужно 1 < IC2 < IC < IN")
        if self.NCORD not in (1, 2):
            err.append("NCORD должен быть 1 или 2")
        if self.NVARM < 1:
            err.append("NVARM должен быть >= 1")
        if self.NMAX < 1:
            err.append("NMAX должен быть >= 1")
        if self.precision not in ("float64", "float32"):
            err.append("precision: float64 или float32")
        if self.P <= 0:
            err.append("P должно быть > 0")
        if self.AKT <= 1:
            err.append("AKT должен быть > 1")
        for name in ("DKR", "DCMB", "DOGOR", "DELGOR", "DKAR", "DOOK",
                     "DELOK", "DKS", "DELKAR", "ALKS", "ALKD", "TGY"):
            if getattr(self, name) <= 0:
                err.append("%s должен быть > 0" % name)
        if err:
            raise ValueError("\n".join(err))
        return self

    def alfa_list(self):
        """Значения ALFA, при которых будут считаться варианты."""
        a = self.ALFA
        out = []
        for _ in range(self.NVARM):
            a = a + self.DALFA
            out.append(a)
        return out
