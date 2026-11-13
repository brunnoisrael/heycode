import re

NEVER_BY_VOICE = [
    r"\brm\b", r"\bsudo\b", r"git\s+push", r"git\s+reset", r"git\s+clean", r"--force", r"\s-f\b",
    r"\bdd\b", r"mkfs", r"chmod\s+-R", r"chown\s+-R", r"\|\s*(sh|bash)\b", r"drop\s+(table|database)",
    r"deploy", r"kubectl\s+delete", r"terraform\s+(apply|destroy)", r"\bshutdown\b|\breboot\b",
    # Windows e outros (ADR 0012)
    r"Remove-Item", r"\b(rmdir|rd)\s+/s", r"\bdel\s", r"-Force\b", r"-delete\b",
    r"git\s+checkout\s+--", r"git\s+branch\b.*\s-D\b", r"git\s+stash\s+drop",
    r"\|\s*(python|node|iex|powershell)\b", r"Invoke-Expression", r"\biex\s", r"npm\s+publish",
    r"Format-Volume", r"shutil\.rmtree", r"Stop-Process",
    # a ponte e seus segredos nunca sao alvo de comando do agente
    r"BRIDGE_SECRET", r"BRIDGE_CONTROL_SECRET", r"127\.0\.0\.1:8765", r"localhost:8765", r"/mode",
]

_ROUTINE_TOOLS = frozenset({"Read", "Grep", "Glob", "Edit", "Write", "MultiEdit"})

# Lista branca de Bash: o comando inteiro tem de casar (ADR 0012).
_ROUTINE_BASH = re.compile(
    r"^(?:git\s+(?:status|diff|log|show|branch|add|commit)|ls|dir|cat|type|pwd|echo|pytest"
    r"|python\s+-m\s+pytest|npm\s+test|npm\s+run\s+test|node\s+--test)(?:\s[^;&|<>`$\r\n]*)?$",
    re.I,
)
# Metacaracteres de encadeamento, redirecionamento e substituicao tiram o comando da lista branca.
_SHELL_META = re.compile(r"[;&|<>`\r\n]|\$\(|\$\{")


def is_destructive(command) -> bool:
    if not isinstance(command, str):
        return False
    return any(re.search(p, command, re.I) for p in NEVER_BY_VOICE)


def _command(tool_input) -> str:
    cmd = tool_input.get("command") if isinstance(tool_input, dict) else None
    return cmd if isinstance(cmd, str) else ""


def is_routine(tool_name: str, tool_input: dict | None) -> bool:
    if tool_name in _ROUTINE_TOOLS:
        return True
    if tool_name != "Bash":
        return False
    cmd = _command(tool_input).strip()
    if not cmd or is_destructive(cmd) or _SHELL_META.search(cmd):
        return False
    return _ROUTINE_BASH.match(cmd) is not None
