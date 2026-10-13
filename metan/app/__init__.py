"""Десктопная программа Metan (оформление «Инженерный пульт», CustomTkinter)."""


def main(mode=None):
    from .main import main as _main
    return _main(mode)
