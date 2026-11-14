"""`heycode command ...`: unico lugar onde comandos locais sao criados, ligados, editados ou removidos (ADR 0051).

Mostra sempre o que vai rodar e pede confirmacao antes de gravar. O relay, o painel e a Alexa nunca passam por aqui.
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from heycode import commands as cm
from heycode.relay.shortcuts import normalize

YES = ("s", "sim", "y", "yes")


def add_parsers(sub: argparse._SubParsersAction) -> None:
    command = sub.add_parser("command", help="comandos locais por voz: scripts e webhooks (definidos só aqui)")
    actions = command.add_subparsers(dest="action", metavar="ação", required=True)

    actions.add_parser("list", help="lista os comandos cadastrados")

    add = actions.add_parser(
        "add",
        help="cadastra um comando",
        description="Exemplos:\n"
        "  heycode command add 'reiniciar app' --risk confirmar --script -- systemctl --user restart app\n"
        "  heycode command add 'acender luz' --risk confirmar --webhook https://casa.exemplo.com/luz --method POST",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add.add_argument("name", help="nome falado (2 a 40 caracteres)")
    add.add_argument("--risk", required=True, choices=cm.RISKS, help="leitura (roda direto), confirmar ou pin")
    add.add_argument("--alias", action="append", default=[], help="apelido falado (até 5)")
    add.add_argument("--description", default="", help="o que faz (é lido em voz alta ao pedir a confirmação)")
    add.add_argument("--timeout", type=int, default=None, help="segundos (script 1-300, webhook 1-30)")
    kind = add.add_mutually_exclusive_group(required=True)
    kind.add_argument("--script", action="store_true", help="roda um programa, SEM shell: use -- antes do programa")
    kind.add_argument("--webhook", metavar="URL", help="chama uma URL fixa (https)")
    add.add_argument("--cwd", default=None, help="(script) pasta de trabalho absoluta")
    add.add_argument("--env-pass", action="append", default=[], metavar="VAR", help="(script) variável a repassar")
    add.add_argument("--method", default="GET", choices=["GET", "POST"], help="(webhook)")
    add.add_argument("--body", default=None, help="(webhook POST) corpo JSON fixo")
    add.add_argument("--header", action="append", default=[], metavar="'Nome: valor|env:VAR'", help="(webhook)")
    add.add_argument("--yes", action="store_true", help="não pergunta antes de gravar")
    add.add_argument("argv", nargs="*", help="(script) programa e argumentos, depois de --")

    for name, text in (("enable", "liga um comando"), ("disable", "desliga um comando")):
        actions.add_parser(name, help=text).add_argument("name")
    remove = actions.add_parser("remove", help="remove um comando")
    remove.add_argument("name")
    remove.add_argument("--yes", action="store_true")
    test = actions.add_parser("test", help="roda um comando aqui, sem a Alexa (você é o dono: sem PIN)")
    test.add_argument("name")


def _env(home: Path) -> dict:
    from heycode import config

    return {**os.environ, **config.load_env_file(home / "config.env")}


def _raw(path: Path) -> list[dict]:
    """Registro como esta no disco (sem validar); recusa arquivo corrompido para nunca sobrescreve-lo."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data["commands"])
    except (ValueError, KeyError, TypeError) as exc:
        raise cm.CommandError(f"{path} está corrompido ({exc}); corrija ou apague o arquivo") from exc


def _cmdline(argv: list[str]) -> str:
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


def _describe(raw: dict) -> list[str]:
    lines = [f"  nome:    {raw['name']}" + (f"  (apelidos: {', '.join(raw['aliases'])})" if raw.get("aliases") else "")]
    lines.append(f"  tipo:    {raw['type']}    risco: {raw['risk']}")
    if raw["type"] == "script":
        lines.append(f"  roda:    {_cmdline(raw['argv'])}  (sem shell: cada item é um argumento)")
        if raw.get("cwd"):
            lines.append(f"  pasta:   {raw['cwd']}")
        lines.append(f"  limite:  {raw.get('timeout', 60)} s")
        if raw.get("env_pass"):
            lines.append(f"  repassa: {', '.join(raw['env_pass'])}")
    else:
        lines.append(f"  chama:   {raw['method']} {raw['url']}")
        if raw.get("body") is not None:
            lines.append(f"  corpo:   {json.dumps(raw['body'], ensure_ascii=False)}")
        for key, value in (raw.get("headers") or {}).items():
            lines.append(
                f"  header:  {key}: " + (value if value.startswith("env:") else "(valor literal, não exibido)")
            )
    return lines


def _warnings(raw: dict) -> list[str]:
    out = []
    if raw["risk"] == "leitura":
        out.append("atenção: risco leitura roda sem pedir confirmação quando a Alexa reconhecer o nome.")
    if raw["type"] == "script":
        exe = raw["argv"][0]
        if not os.path.isabs(exe) and shutil.which(exe) is None:
            out.append(f"aviso: '{exe}' não foi encontrado no PATH; use o caminho completo do programa.")
    return out


def _build(args: argparse.Namespace) -> dict:
    raw: dict = {
        "name": args.name.strip(),
        "type": "script" if args.script else "webhook",
        "risk": args.risk,
        "enabled": True,
    }
    if args.alias:
        raw["aliases"] = args.alias
    if args.description:
        raw["description"] = args.description
    if args.script:
        if not args.argv:
            raise cm.CommandError("informe o programa depois de --script --, por exemplo: --script -- python tarefa.py")
        raw["argv"] = list(args.argv)
        if args.cwd:
            raw["cwd"] = args.cwd
        if args.env_pass:
            raw["env_pass"] = args.env_pass
    else:
        raw["url"], raw["method"] = args.webhook, args.method
        if args.body is not None:
            try:
                raw["body"] = json.loads(args.body)
            except ValueError as exc:
                raise cm.CommandError(f"--body não é JSON válido ({exc})") from exc
        headers = {}
        for item in args.header:
            key, sep, value = item.partition(":")
            if not sep:
                raise cm.CommandError(f"--header deve ser 'Nome: valor' (recebi {item!r})")
            headers[key.strip()] = value.strip()
        if headers:
            raw["headers"] = headers
    if args.timeout is not None:
        raw["timeout"] = args.timeout
    return raw


def _confirm(prompt: str, yes: bool, ask: Callable[[str], str]) -> bool:
    return yes or ask(prompt).strip().lower() in YES


def run(args: argparse.Namespace, home: Path, ask: Callable[[str], str] = input, out=None) -> int:
    path = home / "commands.json"
    env: Mapping[str, str] = _env(home)

    def say(text: str = "") -> None:
        print(text, file=out or sys.stdout)  # sys.stdout lido na hora, nao na importacao

    try:
        return _dispatch(args, path, env, ask, say)
    except cm.CommandError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


def _find(raws: list[dict], name: str) -> dict | None:
    return next((r for r in raws if normalize(r.get("name")) == normalize(name)), None)


def _dispatch(args, path: Path, env, ask, say) -> int:
    action = args.action
    if action == "list":
        commands = cm.load(path, env) if path.exists() else []
        if not commands:
            say("Nenhum comando cadastrado. Use: heycode command add")
            return 0
        raws = _raw(path)
        for r in raws:
            state = "ligado" if r.get("enabled", True) else "desligado"
            what = " ".join(r["argv"]) if r["type"] == "script" else f"{r['method']} {r['url']}"
            say(f"- {r['name']}  [{r['type']}, {r['risk']}, {state}]  {what}")
        return 0

    raws = _raw(path)
    if action == "add":
        new = _build(args)
        cm.parse_registry({"version": cm.VERSION, "commands": [*raws, new]}, env)  # valida tudo junto, antes de mostrar
        say("Você vai cadastrar este comando:")
        for line in _describe(new):
            say(line)
        for line in _warnings(new):
            say(line)
        say(f"Para usar por voz: “executar {new['name']}”.")
        if not _confirm("Cadastrar? [s/N] ", args.yes, ask):
            say("Nada foi gravado.")
            return 1
        cm.save(path, [*raws, new], env)
        say("Comando cadastrado.")
        return 0

    target = _find(raws, args.name)
    if target is None:
        raise cm.CommandError(f"não encontrei o comando {args.name!r}")
    if action in ("enable", "disable"):
        target["enabled"] = action == "enable"
        cm.save(path, raws, env)
        say(f"{target['name']}: {'ligado' if target['enabled'] else 'desligado'}.")
        return 0
    if action == "remove":
        say("Remover:")
        for line in _describe(target):
            say(line)
        if not _confirm("Remover? [s/N] ", args.yes, ask):
            say("Nada foi removido.")
            return 1
        cm.save(path, [r for r in raws if r is not target], env)
        say("Comando removido.")
        return 0
    if action == "test":
        runner = cm.CommandRunner(path, secrets=lambda: env)
        first = runner.start(target["name"])
        say(first["speech"])
        if first.get("pending"):
            if not _confirm("Rodar agora? [s/N] ", False, ask):
                runner.cancel()
                say("Cancelado.")
                return 1
            first = runner.confirm(pin_ok=True)  # quem esta no terminal e o dono
            say(first["speech"])
        return 0 if first.get("ok") else 1
    return 2
