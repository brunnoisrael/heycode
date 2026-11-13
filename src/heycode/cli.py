"""Interface de linha de comando do HeyCode (argparse, sem dependencias novas)."""

import argparse
import sys

from heycode import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heycode", description="HeyCode: controle por voz de agentes de codigo")
    parser.add_argument("--version", action="version", version=f"heycode {__version__}")
    parser.add_subparsers(dest="command", metavar="comando")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --version, --help e erros de uso
        return exc.code if isinstance(exc.code, int) else 1
    if args.command is None:
        parser.print_usage()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
