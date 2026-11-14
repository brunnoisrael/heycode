from .rules import _command, is_destructive, is_routine


def decidir(agent: str, project: str, tool_name: str, tool_input: dict | None, store) -> str:
    """Retorna "allow" | "deny" | "ask_voz" | "ask_teclado". Falha aberto: erro -> ask_teclado."""
    try:
        mode = store.get_policy(agent, project)["mode"]
        if mode == "auto":
            return "allow"
        if mode not in ("manual", "decisoes"):
            return "ask_teclado"
        if tool_name == "Bash" and is_destructive(_command(tool_input)):
            return "ask_teclado"
        if mode == "decisoes" and is_routine(tool_name, tool_input):
            return "allow"
        return "ask_voz"
    except Exception:
        return "ask_teclado"
