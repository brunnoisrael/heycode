import re

NEVER_BY_VOICE = [
    r"\brm\b", r"\bsudo\b", r"git\s+push", r"git\s+reset", r"git\s+clean", r"--force", r"\s-f\b",
    r"\bdd\b", r"mkfs", r"chmod\s+-R", r"chown\s+-R", r"\|\s*(sh|bash)\b", r"drop\s+(table|database)",
    r"deploy", r"kubectl\s+delete", r"terraform\s+(apply|destroy)", r"\bshutdown\b|\breboot\b",
]

_ROUTINE_TOOLS = frozenset({"Read", "Grep", "Glob", "Edit", "Write", "MultiEdit"})


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
    return tool_name == "Bash" and not is_destructive(_command(tool_input))
