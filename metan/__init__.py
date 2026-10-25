"""metan - Python-версия программы расчёта горения метана в камере
(перевод с Фортрана программы met21, файлы RK1-RK7.FOR)."""

from .params import Params
from .solver import Solver, Results, VariantResult, Cancelled, VAR_NAMES

__version__ = "1.2.0"
__all__ = ["Params", "Solver", "Results", "VariantResult", "Cancelled",
           "VAR_NAMES"]
