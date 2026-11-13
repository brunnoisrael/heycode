"""Interface de linha de comando do HeyCode (argparse, sem dependencias novas)."""

import argparse
import sys
from pathlib import Path

from heycode import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heycode", description="HeyCode: controle por voz de agentes de codigo")
    parser.add_argument("--version", action="version", version=f"heycode {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="comando")
    init = sub.add_parser("init", help="cria o diretório do usuário e os segredos (não sobrescreve nada)")
    init.add_argument("--import-legacy", metavar="DIR", help="importa bridge.db e .env de um clone antigo")
    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    from heycode import config, paths

    home = paths.home()
    if args.import_legacy:
        src = Path(args.import_legacy)
        if not src.is_dir():
            print(f"Pasta do clone antigo não encontrada: {src}", file=sys.stderr)
            return 1
        res = config.import_legacy(src, home)
        for name in res["copied"]:
            print(f"importado: {name}")
        for name in res["skipped"]:
            print(f"já existe, mantido: {name}")
        for name in res["missing"]:
            print(f"não encontrado no clone antigo: {name}")
    res = config.init_home(home)
    print(f"Diretório do HeyCode: {home}")
    for key in res["created"]:
        print(f"criado: {key}")
    for key in res["kept"]:
        print(f"já existe, mantido: {key}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --version, --help e erros de uso
        return exc.code if isinstance(exc.code, int) else 1
    if args.command is None:
        parser.print_usage()
        return 2
    if args.command == "init":
        return _cmd_init(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
