"""Motivo legivel de uma execucao que falhou (ADR 0017).

`failure_reason` tira a mensagem de erro da saida do agente: o objeto de `claude -p --output-format json`
ou os eventos de `codex exec --json`. Devolve None quando nao reconhece a saida; quem chama cai na cauda
do stdout. `spoken_reason` decide o que desse resumo pode ser lido em voz alta. Nenhuma das duas levanta.
"""
import json
import re

SPOKEN_MAX = 200
_JSON_LIKE = re.compile(r"[{}]|\"\s*:")


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _dig(obj) -> str | None:
    """Mensagem dentro de um objeto de erro: {"error": {"message": ...}}, {"error": "..."} ou {"message": ...}."""
    if not isinstance(obj, dict):
        return None
    err = obj.get("error")
    if isinstance(err, dict) and isinstance(err.get("message"), str) and err["message"].strip():
        return err["message"]
    if isinstance(err, str) and err.strip():
        return err
    msg = obj.get("message")
    return msg if isinstance(msg, str) and msg.strip() else None


def _unwrap(text: str, depth: int = 0) -> str:
    """Troca um JSON de erro embutido no texto pela mensagem que ele carrega (ate 4 niveis)."""
    start = text.find("{")
    if start < 0 or depth >= 4:
        return text
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return text
    inner = _dig(obj)
    if not inner:
        return text
    return f"{text[:start].strip()} {_unwrap(inner, depth + 1)}".strip()


def _json_lines(output: str):
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            yield data


def _claude_reason(output: str) -> str | None:
    data = None
    try:
        data = json.loads(output.strip())
    except ValueError:
        pass
    if not isinstance(data, dict):
        data = next((d for d in reversed(list(_json_lines(output)))
                     if d.get("type") == "result" or "is_error" in d or "result" in d), None)
    if data is None:
        return None
    result = data.get("result")
    if isinstance(result, str) and result.strip():
        return _unwrap(result)
    errors = data.get("errors")
    if isinstance(errors, list):
        texts = [e for e in errors if isinstance(e, str) and e.strip()]
        if texts:
            return _unwrap(" ".join(texts))
    inner = _dig(data)
    if inner:
        return _unwrap(inner)
    subtype = data.get("subtype")
    if isinstance(subtype, str) and subtype.strip() and subtype != "success":
        return subtype
    return None


def _codex_reason(output: str) -> str | None:
    failed = error = item = None
    for data in _json_lines(output):
        kind = data.get("type")
        if kind == "turn.failed":
            failed = _dig(data) or failed
        elif kind == "error":
            error = _dig(data) or error
        elif kind == "item.completed" and isinstance(data.get("item"), dict) \
                and data["item"].get("type") == "error":
            item = _dig(data["item"]) or item  # aviso do codex: so vale se nao houver erro de turno
    reason = failed or error or item
    return _unwrap(reason) if reason else None


def failure_reason(agent: str, output: str) -> str | None:
    """Mensagem de erro dada pelo agente, em uma linha, ou None se a saida nao for reconhecida."""
    try:
        if agent == "claude":
            reason = _claude_reason(output)
        elif agent == "codex":
            reason = _codex_reason(output)
        else:
            reason = None
        reason = _one_line(reason) if reason else ""
        return reason or None
    except Exception:  # o parser nunca quebra a finalizacao da run
        return None


def spoken_reason(summary: str | None, limit: int = SPOKEN_MAX) -> str:
    """Trecho do resumo de falha que pode ser falado: ultima linha, sem JSON cru, com tamanho limitado.

    Devolve "" quando nao ha nada legivel. A mascara de segredos fica com quem fala (`say`).
    """
    try:
        lines = [ln for ln in (summary or "").splitlines() if ln.strip()]
        if not lines:
            return ""
        text = _one_line(lines[-1])
        if not text or _JSON_LIKE.search(text):
            return ""
        return text[:limit].rstrip() + ("..." if len(text) > limit else "")
    except Exception:
        return ""
