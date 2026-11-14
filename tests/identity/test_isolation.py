import pytest

from heycode.identity import IdentityError
from heycode.identity.auto_mode import AutoMode
from heycode.identity.confirmation import ConfirmationStore
from heycode.identity.keys import generate_keypair, load_private_key
from heycode.identity.routing import Installation, Router
from heycode.protocol import validate
from heycode.protocol.outbound import build_envelope, send_fail_open


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def router():
    r = Router()
    r.register(Installation("inst-a", "conta-a", "pub-a"))
    r.register(Installation("inst-b", "conta-b", "pub-b"))
    return r


def _env(inst, payload=None):
    return {"installation_id": inst, "type": "instruction", "payload": payload or {}}


def test_conta_a_nao_aciona_instalacao_de_b(router):
    with pytest.raises(IdentityError) as e:
        router.route("conta-a", "inst-b", _env("inst-b"))
    assert e.value.code == "not_owner"


def test_instalacao_inexistente_recusada(router):
    with pytest.raises(IdentityError):
        router.route("conta-a", "inst-x", _env("inst-x"))


def test_installation_id_forjado_no_payload_ignorado(router):
    inst = router.route("conta-a", "inst-a", _env("inst-a", {"installation_id": "inst-b"}))
    assert inst.id == "inst-a"


def test_envelope_com_installation_id_diferente_do_autenticado_recusado(router):
    with pytest.raises(IdentityError) as e:
        router.route("conta-a", "inst-a", _env("inst-b"))
    assert e.value.code == "mismatch"


def test_instalacao_nao_pode_ser_registrada_por_duas_contas(router):
    with pytest.raises(IdentityError):
        router.register(Installation("inst-a", "conta-b", "pub-x"))


def test_confirmacao_vale_para_o_destino_apresentado():
    store = ConfirmationStore(Clock())
    cid = store.bind("bash", "projeto-x", "inst-a")
    store.consume(cid, "bash", "projeto-x", "inst-a")


def test_confirmacao_nao_vale_para_outro_destino():
    store = ConfirmationStore(Clock())
    cid = store.bind("bash", "projeto-x", "inst-a")
    for args in (("bash", "projeto-y", "inst-a"), ("rm", "projeto-x", "inst-a"), ("bash", "projeto-x", "inst-b")):
        with pytest.raises(IdentityError) as e:
            store.consume(cid, *args)
        assert e.value.code == "mismatch"
    store.consume(cid, "bash", "projeto-x", "inst-a")  # tentativa errada nao a gasta


def test_confirmacao_nao_reutilizavel():
    store = ConfirmationStore(Clock())
    cid = store.bind("bash", "p", "inst-a")
    store.consume(cid, "bash", "p", "inst-a")
    with pytest.raises(IdentityError) as e:
        store.consume(cid, "bash", "p", "inst-a")
    assert e.value.code == "unknown_confirmation"


def test_confirmacao_expira_e_nao_fica_pendente_para_sempre():
    clock = Clock()
    store = ConfirmationStore(clock, ttl=300)
    cid = store.bind("bash", "p", "inst-a")
    clock.t += 301
    with pytest.raises(IdentityError) as e:
        store.consume(cid, "bash", "p", "inst-a")
    assert e.value.code == "expired"
    assert store.pending_count() == 0


def test_auto_so_liga_com_confirmacao_no_computador(router):
    auto = AutoMode(router)
    auto.associate_device("conta-a", "inst-a", "echo-1")
    with pytest.raises(IdentityError) as e:
        auto.enable("inst-a", by_account="conta-a", via="voice", device_id="echo-1")
    assert e.value.code == "needs_machine_confirmation"
    assert not auto.is_enabled("inst-a")
    auto.enable("inst-a", by_account="conta-a", via="machine")
    assert auto.is_enabled("inst-a")


def test_depois_da_primeira_confirmacao_auto_liga_por_voz(router):
    auto = AutoMode(router)
    auto.associate_device("conta-a", "inst-a", "echo-1")
    auto.enable("inst-a", by_account="conta-a", via="machine")
    auto.disable("inst-a", by_account="conta-a")
    assert not auto.is_enabled("inst-a")
    auto.enable("inst-a", by_account="conta-a", via="voice", device_id="echo-1")
    assert auto.is_enabled("inst-a")


def test_auto_nao_liga_por_outra_conta(router):
    auto = AutoMode(router)
    with pytest.raises(IdentityError) as e:
        auto.enable("inst-a", by_account="conta-b", via="machine")
    assert e.value.code == "not_owner"
    assert not auto.is_enabled("inst-a")


def test_auto_nao_liga_por_dispositivo_nao_associado(router):
    auto = AutoMode(router)
    auto.associate_device("conta-a", "inst-a", "echo-1")
    auto.enable("inst-a", by_account="conta-a", via="machine")
    auto.disable("inst-a", by_account="conta-a")
    with pytest.raises(IdentityError) as e:
        auto.enable("inst-a", by_account="conta-a", via="voice", device_id="echo-intruso")
    assert e.value.code == "device_not_associated"
    with pytest.raises(IdentityError):
        auto.enable("inst-a", by_account="conta-a", via="voice")  # sem dispositivo


def test_dispositivo_de_outra_conta_nao_pode_ser_associado(router):
    auto = AutoMode(router)
    with pytest.raises(IdentityError):
        auto.associate_device("conta-a", "inst-b", "echo-1")


def test_dispositivo_revogado_nao_liga_auto(router):
    auto = AutoMode(router)
    auto.associate_device("conta-a", "inst-a", "echo-1")
    auto.enable("inst-a", by_account="conta-a", via="machine")
    auto.disable("inst-a", by_account="conta-a")
    auto.revoke_device("conta-a", "inst-a", "echo-1")
    with pytest.raises(IdentityError):
        auto.enable("inst-a", by_account="conta-a", via="voice", device_id="echo-1")


def test_segredo_mascarado_antes_de_sair(tmp_path):
    generate_keypair(tmp_path)
    priv = load_private_key(tmp_path)
    segredo = "ghp_" + "a" * 36
    env = build_envelope(
        "run-result",
        {
            "run_id": "1",
            "state": "done",
            "summary": f"usei o token {segredo} e Bearer abc.def.ghi",
            "n": [f"password={'x' * 9}"],
        },
        installation_id="inst-a",
        private_key=priv,
        now=1000.0,
    )
    texto = repr(env)
    assert segredo not in texto and "abc.def.ghi" not in texto and "xxxxxxxxx" not in texto
    validate(env)  # continua um envelope valido


def test_assinatura_cobre_o_payload_ja_mascarado(tmp_path):
    from heycode.identity.signing import verify

    pub = generate_keypair(tmp_path)
    env = build_envelope(
        "status", {"state": "running"}, installation_id="inst-a", private_key=load_private_key(tmp_path), now=1000.0
    )
    verify(env, pub, 1000.0)


def test_relay_fora_nao_trava_agente():
    def envia(_):
        raise ConnectionError("relay fora do ar")

    assert send_fail_open(envia, {"x": 1}) is False


def test_envio_bem_sucedido_devolve_true():
    assert send_fail_open(lambda _: None, {"x": 1}) is True
