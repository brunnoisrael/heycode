"""Motivo legivel de falha (ADR 0017): saidas reais do claude 2.1.207 e do codex-cli 0.155.1."""
import json

from bridge.supervisor.failure import failure_reason, spoken_reason

CLAUDE_MSG = ("API Error: 400 Claude Code 2.1.207 does not support this model; version 2.1.290 or newer is "
              "required. Run 'claude update', or update the Claude desktop app, then try again.")
CLAUDE_ERRO = json.dumps({
    "type": "result", "subtype": "success", "is_error": True, "api_error_status": 400, "duration_ms": 1077,
    "duration_api_ms": 0, "num_turns": 1, "result": CLAUDE_MSG, "stop_reason": "stop_sequence",
    "session_id": "37c143bb-3342-4f16-9c3c-0301ec4041e3", "total_cost_usd": 0,
    "usage": {"input_tokens": 0, "output_tokens": 0, "service_tier": "standard", "iterations": []},
    "modelUsage": {}, "permission_denials": [], "terminal_reason": "api_error", "fast_mode_state": "off",
    "uuid": "f942b57e-fb63-49f3-968b-f3e17c3ffcaa"})

CODEX_MSG = "The 'gpt-6.1-terra' model is not supported when using Codex with a ChatGPT account."
_CODEX_API = json.dumps({"type": "error", "status": 400, "error": {
    "type": "invalid_request_error", "message": CODEX_MSG, "code": "model_not_found"}})
CODEX_ERRO = "\n".join([
    "Reading additional input from stdin...",
    json.dumps({"type": "thread.started", "thread_id": "01a1c39f-b920-79e1-8869-93d1e422f6b8"}),
    json.dumps({"type": "item.completed", "item": {"id": "item_0", "type": "error", "message":
                "Model metadata for `gpt-6.1-terra` not found. Defaulting to fallback metadata."}}),
    json.dumps({"type": "turn.started"}),
    json.dumps({"type": "error", "message": _CODEX_API}),
    json.dumps({"type": "turn.failed", "error": {"message": _CODEX_API}}),
])


def test_claude_json_de_erro_real():
    assert failure_reason("claude", CLAUDE_ERRO + "\n") == CLAUDE_MSG


def test_claude_json_depois_de_linhas_soltas():
    assert failure_reason("claude", "aviso qualquer\n" + CLAUDE_ERRO) == CLAUDE_MSG


def test_claude_json_embutido_no_result_vira_mensagem():
    api = json.dumps({"type": "error", "error": {"type": "invalid_request_error", "message": "prompt is too long"}})
    out = json.dumps({"type": "result", "is_error": True, "result": f"API Error: 400 {api}"})
    assert failure_reason("claude", out) == "API Error: 400 prompt is too long"


def test_claude_sem_result_usa_subtype():
    out = json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True})
    assert failure_reason("claude", out) == "error_max_turns"


def test_claude_result_em_varias_linhas_vira_uma():
    out = json.dumps({"type": "result", "is_error": True, "result": "linha um\n\n  linha dois"})
    assert failure_reason("claude", out) == "linha um linha dois"


def test_codex_eventos_de_erro_reais():
    assert failure_reason("codex", CODEX_ERRO) == CODEX_MSG


def test_codex_so_evento_error():
    out = json.dumps({"type": "error", "message": "stream disconnected"})
    assert failure_reason("codex", out) == "stream disconnected"


def test_codex_aviso_de_item_so_vale_sem_erro_de_turno():
    out = json.dumps({"type": "item.completed", "item": {"type": "error", "message": "so um aviso"}})
    assert failure_reason("codex", out) == "so um aviso"
    assert "aviso" not in failure_reason("codex", CODEX_ERRO)


def test_saida_que_nao_e_json_devolve_none():
    for agent in ("claude", "codex", "aider", "outro"):
        assert failure_reason(agent, "Traceback (most recent call last):\nValueError: x") is None
        assert failure_reason(agent, "") is None
    assert failure_reason("claude", '{"result": 5, "quebrado":') is None
    assert failure_reason("claude", "[1, 2, 3]") is None
    assert failure_reason("codex", '{"type":"turn.failed","error":null}') is None


def test_aider_nunca_e_interpretado_como_json():
    assert failure_reason("aider", CLAUDE_ERRO) is None


def test_parser_nunca_levanta():
    assert failure_reason("claude", None) is None
    assert failure_reason(None, object()) is None


def test_fala_usa_a_ultima_linha_e_limita():
    assert spoken_reason("l1\nl2\nValueError: deu ruim\n") == "ValueError: deu ruim"
    longo = spoken_reason("x" * 500)
    assert len(longo) <= 203 and longo.endswith("...")


def test_fala_nunca_le_json_cru():
    assert spoken_reason('"terminal_reason":"api_error","uuid":"abc"}') == ""
    assert spoken_reason('{"type":"turn.failed"}') == ""
    assert spoken_reason("") == "" and spoken_reason(None) == ""
    assert spoken_reason(CLAUDE_MSG) == CLAUDE_MSG
