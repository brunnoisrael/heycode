"""Monta a linha de comando de cada agente headless (ADR 0007, 0012).

No Codex e no Claude o prompt vem depois de `--`, para que texto iniciado por `-` nao vire opcao.
"""

DEFAULT_COMMANDS = {"codex": ["codex"], "claude": ["claude"], "aider": ["aider"]}


def build_command(agent: str, prompt: str, cwd: str, mode: str, out_file: str,
                  commands: dict | None = None) -> list[str]:
    if agent not in DEFAULT_COMMANDS:
        raise ValueError(f"agente desconhecido: {agent!r}")
    base = list((commands or {}).get(agent, DEFAULT_COMMANDS[agent]))
    auto = mode == "auto"
    if agent == "codex":
        sandbox = "danger-full-access" if auto else "workspace-write"
        return base + ["exec", "-C", cwd, "-s", sandbox, "--json", "-o", out_file,
                       "--skip-git-repo-check", "--", prompt]
    if agent == "claude":
        cmd = base + ["-p", "--output-format", "json"]
        if auto:
            cmd.append("--dangerously-skip-permissions")
        return cmd + ["--", prompt]
    if agent == "aider":
        return base + ["--message", prompt, "--yes-always", "--no-pretty", "--no-auto-commits"]
    raise ValueError(f"agente desconhecido: {agent!r}")
