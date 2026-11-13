import copy

import pytest

from heycode.protocol import SUPPORTED_VERSIONS, ProtocolError, validate


def _env(**over):
    msg = {
        "v": 1,
        "id": "018f0000-0000-7000-8000-000000000000",
        "ts": 1.0,
        "installation_id": "inst-1",
        "type": "status",
        "payload": {"state": "running"},
        "sig": "x",
    }
    msg.update(over)
    return msg


def test_envelope_valido_passa():
    validate(_env())


def test_versao_maior_recusada_unsupported_version():
    with pytest.raises(ProtocolError) as e:
        validate(_env(v=max(SUPPORTED_VERSIONS) + 1))
    assert e.value.code == "unsupported_version"


def test_campo_desconhecido_ignorado():
    msg = _env()
    msg["novo_campo"] = 1
    msg["payload"]["extra"] = True
    validate(msg)


def test_campo_obrigatorio_ausente_falha():
    msg = _env()
    del msg["installation_id"]
    with pytest.raises(ProtocolError) as e:
        validate(msg)
    assert e.value.code == "invalid"


def test_payload_invalido_para_o_tipo_falha():
    with pytest.raises(ProtocolError):
        validate(_env(type="decision-response", payload={"confirmation_id": "c"}))


def test_tipo_desconhecido_falha():
    with pytest.raises(ProtocolError):
        validate(_env(type="inventado"))


def test_id_que_nao_e_uuidv7_falha():
    with pytest.raises(ProtocolError):
        validate(_env(id="not-a-uuid"))


def test_campo_novo_opcional_na_vizinha_nao_quebra_v1():
    base = _env(
        type="decision-request",
        payload={"confirmation_id": "c", "operation": "bash", "destination": "proj", "summary": "ls"},
    )
    novo = copy.deepcopy(base)
    novo["payload"]["campo_futuro_opcional"] = "x"
    validate(base)
    validate(novo)


def test_todos_os_tipos_tem_esquema_e_exemplo_valido():
    exemplos = {
        "status": {"state": "done"},
        "decision-request": {"confirmation_id": "c", "operation": "o", "destination": "d", "summary": "s"},
        "decision-response": {"confirmation_id": "c", "approved": True},
        "instruction": {"text": "faca", "destination": "d"},
        "run-result": {"run_id": "1", "state": "done", "summary": "ok"},
        "pair-request": {"code": "ABCD2345", "public_key": "k"},
        "pair-confirm": {"pending_id": "p", "side": "machine"},
        "error": {"code": "x"},
    }
    for tipo, payload in exemplos.items():
        validate(_env(type=tipo, payload=payload))
