"""Десктопная программа Metan (оформление «Инженерный пульт», CustomTkinter)."""


def main(mode="light"):
    from .main import main as _main
    return _main(mode)
