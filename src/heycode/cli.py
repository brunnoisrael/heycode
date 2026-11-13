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
    for name, text in (
        ("install-service", "instala o serviço em segundo plano (dry-run por padrão)"),
        ("uninstall-service", "remove o serviço (dry-run por padrão)"),
    ):
        sub.add_parser(name, help=text).add_argument("--apply", action="store_true", help="executa de verdade")
    rot = sub.add_parser("rotate-secret", help="gera novo segredo com backup (dry-run por padrão)")
    rot.add_argument("--apply", action="store_true", help="executa de verdade")
    rot.add_argument("--control", action="store_true", help="rotaciona o segredo de controle (Lambda)")
    doctor = sub.add_parser("doctor", help="diagnóstico por camada (sai com 1 se houver falha)")
    doctor.add_argument("--json", action="store_true", help="saída em JSON")
    pair = sub.add_parser("pair", help="pareia este computador a uma conta do relay HeyCode")
    pair.add_argument("code", help="código de 8 caracteres emitido pelo app do relay")
    pair.add_argument("--relay", required=True, metavar="URL", help="endereço do relay (https://...)")
    pair.add_argument("--name", default=None, help="nome deste computador (padrão: nome da máquina)")
    pair.add_argument("--yes", action="store_true", help="não pergunta se o código de verificação confere")
    pair.add_argument("--force", action="store_true", help="gera uma identidade nova mesmo se já existir uma")
    auto = sub.add_parser("relay-auto", help="liga ou desliga o modo automático por voz no modo compartilhado")
    auto.add_argument("state", choices=["on", "off"])
    auto.add_argument("--yes", action="store_true", help="não pergunta a confirmação ao ligar")
    from heycode import commands_cli

    commands_cli.add_parsers(sub)
    sub.add_parser("connect", help="mantém a conexão de saída com o relay (reconecta sozinho)")
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


def _cmd_service(args: argparse.Namespace) -> int:
    from heycode import service

    action = service.install if args.command == "install-service" else service.uninstall
    try:
        for line in action(apply=args.apply):
            print(line)
    except (RuntimeError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_rotate(args: argparse.Namespace) -> int:
    from heycode import config, paths, service

    key = "BRIDGE_CONTROL_SECRET" if args.control else "BRIDGE_SECRET"
    update = (
        "a variável BRIDGE_CONTROL_SECRET da Lambda"
        if args.control
        else "a variável BRIDGE_SECRET nos hooks e no MCP dos agentes (Claude Code, Codex) e reinicie-os"
    )
    if not args.apply:
        print(f"[dry-run] rotacionaria {key} (com backup 0600 do config.env). Use --apply para executar.")
        print(f"Depois será preciso atualizar {update}.")
        return 0
    try:
        backup = config.rotate_secret(paths.home(), key=key)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    print(f"{key} rotacionado. Backup do arquivo anterior: {backup} (apague quando não precisar mais).")
    print("Serviço reiniciado." if service.restart() else "Serviço não reiniciado (instalado? use heycode serve).")
    print(f"Atualize agora {update}.")
    return 0


def _cmd_pair(args: argparse.Namespace) -> int:
    import platform

    import httpx

    from heycode import paths, relay_client

    def confirm(verification: str) -> bool:
        print(f"Código de verificação: {verification}")
        print("Confira que o app do relay mostra o mesmo código.")
        if args.yes:
            return True
        return input("O código confere? [s/N] ").strip().lower() in ("s", "sim", "y", "yes")

    try:
        iid = relay_client.pair_with_relay(
            args.relay,
            args.code.strip().upper(),
            args.name or platform.node() or "computador",
            paths.home(),
            http=httpx,
            confirm=confirm,
            force=args.force,
        )
    except (relay_client.PairingError, httpx.HTTPError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    print(f"Pareado. Instalação {iid}. Rode `heycode connect` para manter a conexão com o relay.")
    return 0


def _cmd_relay_auto(args: argparse.Namespace) -> int:
    from heycode import paths, relay_client

    home = paths.home()
    if relay_client.load_relay_config(home) is None:
        print("Este computador ainda não foi pareado. Rode: heycode pair CÓDIGO --relay URL", file=sys.stderr)
        return 1
    if args.state == "on":
        print("O modo automático aprova TUDO sem PIN e sem expiração (ADR 0002), inclusive rm -rf e git push --force.")
        print("Ligando aqui, quem usar a skill por voz poderá pedir o modo automático.")
        if not args.yes and input("Ligar mesmo assim? [s/N] ").strip().lower() not in ("s", "sim", "y", "yes"):
            print("Mantido desligado.")
            return 1
    relay_client.set_auto_allowed(home, args.state == "on")
    print("Modo automático por voz LIBERADO neste computador." if args.state == "on"
          else "Modo automático por voz bloqueado neste computador.")
    return 0


def make_instruction_handler(store):
    """Tratador padrao: enfileira a instrucao para o agente aberto (mesma fila do ADR 0018)."""

    async def handler(payload: dict) -> dict:
        store.add_instruction(
            str(payload["text"]), agent=str(payload.get("agent") or "claude"), project=payload.get("destination")
        )
        return {"run_id": "0", "state": "done", "summary": "instrucao enfileirada para o agente"}

    return handler


def _make_bridge_executor(home, config, relay_executor):
    """Executor das chamadas do relay: segredo de controle lido so do config.env local (ADR 0045)."""
    import os

    from heycode import paths, relay_client

    env = config.load_env_file(paths.config_file())
    secret = env.get("BRIDGE_CONTROL_SECRET") or os.environ.get("BRIDGE_CONTROL_SECRET")
    if not secret:
        return None  # sem segredo de controle (heycode init) so o handler de instrucao funciona
    base = os.environ.get("BRIDGE_URL") or "http://127.0.0.1:8765"
    return relay_executor.BridgeExecutor(base, secret, auto_allowed=lambda: relay_client.auto_allowed(home))


def _cmd_connect(args: argparse.Namespace) -> int:
    import asyncio

    from heycode import paths, relay_client
    from heycode.identity.keys import load_private_key
    from heycode import config, relay_executor
    from heycode.store.db import Store

    home = paths.home()
    cfg = relay_client.load_relay_config(home)
    if cfg is None:
        print("Este computador ainda não foi pareado. Rode: heycode pair CÓDIGO --relay URL", file=sys.stderr)
        return 1
    try:
        client = relay_client.RelayClient(
            relay_client.ws_url(cfg["relay_url"]),
            cfg["installation_id"],
            load_private_key(home),
            make_instruction_handler(Store(str(paths.db_path()))),
            bridge=_make_bridge_executor(home, config, relay_executor),
        )
    except (ValueError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    print(f"Conectando ao relay {cfg['relay_url']} (Ctrl+C para sair)...")
    try:
        asyncio.run(client.run_forever())
    except KeyboardInterrupt:
        pass
    return 0


def _cmd_command(args: argparse.Namespace) -> int:
    from heycode import commands_cli, paths

    return commands_cli.run(args, paths.home(), ask=input)


def _cmd_doctor(args: argparse.Namespace) -> int:
    import json
    import os

    from heycode import doctor, paths

    checks = doctor.run_checks(dict(os.environ), paths.home())
    if args.json:
        print(json.dumps([c.__dict__ for c in checks], ensure_ascii=False, indent=2))
    else:
        layer = None
        for c in checks:
            if c.layer != layer:
                layer = c.layer
                print(chr(10) + layer)
            print(f"  [{c.status}] {c.name}: {c.detail}")
            if c.fix and c.status != "ok":
                print(f"         -> {c.fix}")
    return 1 if any(c.status == "falha" for c in checks) else 0


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
    if args.command in ("install-service", "uninstall-service"):
        return _cmd_service(args)
    if args.command == "pair":
        return _cmd_pair(args)
    if args.command == "connect":
        return _cmd_connect(args)
    if args.command == "relay-auto":
        return _cmd_relay_auto(args)
    if args.command == "command":
        return _cmd_command(args)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "rotate-secret":
        return _cmd_rotate(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
