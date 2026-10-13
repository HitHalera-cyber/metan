"""Прежняя (классическая) версия интерфейса Metan."""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from metan.cli import main as cli_main
        raise SystemExit(cli_main(sys.argv[2:]))
    from metan.gui_classic import main
    raise SystemExit(main())
