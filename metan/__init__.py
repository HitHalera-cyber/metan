"""metan - Python-версия программы расчёта горения метана в камере
(перевод с Фортрана программы met21, файлы RK1-RK7.FOR)."""

__version__ = "1.9.0"
__all__ = ["Params", "Solver", "Results", "VariantResult", "Cancelled",
           "VAR_NAMES"]


def __getattr__(name):
    # ленивый импорт: процесс заставки загружает только metan.app.splash,
    # без numba и решателя - поэтому окно заставки появляется сразу
    if name == "Params":
        from .params import Params
        return Params
    if name in ("Solver", "Results", "VariantResult", "Cancelled",
                "VAR_NAMES"):
        from . import solver
        return getattr(solver, name)
    raise AttributeError("module 'metan' has no attribute %r" % name)
