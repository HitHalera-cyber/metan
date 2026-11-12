"""Запуск десктопной программы двойным щелчком (Windows).

Metan.exe --cli [аргументы]  - расчёт без окна (как python -m metan).
"""
import sys

if __name__ == "__main__":
    # заставка идёт в отдельном процессе: в собранном .exe он запускается
    # тем же Metan.exe, и его нужно сразу передать multiprocessing
    import multiprocessing
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from metan.cli import main as cli_main
        raise SystemExit(cli_main(sys.argv[2:]))
    from metan.app import main
    raise SystemExit(main())
