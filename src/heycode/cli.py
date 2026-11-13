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
    serve = sub.add_parser("serve", help="sobe a ponte local (FastAPI + MCP em /mcp)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    sub.add_parser("hook", help="ponto de entrada dos hooks dos agentes: heycode hook [approve] [--agent A]")
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


def _cmd_serve(args: argparse.Namespace) -> int:
    import socket

    from heycode import config, paths

    config.apply_env(config.load_env_file(paths.config_file()))
    try:  # porta ocupada: avisa claramente em vez de um traceback do uvicorn
        with socket.socket() as probe:
            probe.bind((args.host, args.port))
    except OSError as exc:
        print(f"Porta {args.port} em {args.host} indisponível ({exc}); outra ponte já está rodando?", file=sys.stderr)
        return 1
    import uvicorn

    uvicorn.run("heycode.app:app", host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "hook":  # caminho quente: so biblioteca padrao e falha aberta
        from heycode import hook

        return hook.run(argv[1:])
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
    if args.command == "serve":
        return _cmd_serve(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
