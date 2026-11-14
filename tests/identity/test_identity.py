import os
import stat
import sys

import pytest

from heycode.identity import IdentityError
from heycode.identity.keys import generate_keypair, load_private_key
from heycode.identity.registry import Registry
from heycode.identity.replay import ReplayWindow
from heycode.identity.signing import canonical, rotate, sign, verify, verify_rotation

NOW = 1_000_000.0


def _env(**over):
    msg = {
        "v": 1,
        "id": "018f0000-0000-7000-8000-000000000001",
        "ts": NOW,
        "installation_id": "inst-1",
        "type": "status",
        "payload": {"state": "running"},
    }
    msg.update(over)
    return msg


@pytest.fixture
def keys(tmp_path):
    pub = generate_keypair(tmp_path)
    return pub, load_private_key(tmp_path)


def _signed(priv, **over):
    msg = _env(**over)
    msg["sig"] = sign(msg, priv)
    return msg


def test_assinatura_valida_passa(keys):
    pub, priv = keys
    verify(_signed(priv), pub, NOW)


def test_payload_adulterado_recusado(keys):
    pub, priv = keys
    msg = _signed(priv)
    msg["payload"]["state"] = "done"
    with pytest.raises(IdentityError) as e:
        verify(msg, pub, NOW)
    assert e.value.code == "bad_signature"


def test_installation_id_adulterado_recusado(keys):
    pub, priv = keys
    msg = _signed(priv)
    msg["installation_id"] = "inst-2"
    with pytest.raises(IdentityError):
        verify(msg, pub, NOW)


def test_chave_de_outra_instalacao_recusada(keys, tmp_path_factory):
    _, priv = keys
    outra = generate_keypair(tmp_path_factory.mktemp("outra"))
    with pytest.raises(IdentityError):
        verify(_signed(priv), outra, NOW)


def test_assinatura_ausente_recusada(keys):
    pub, _ = keys
    with pytest.raises(IdentityError):
        verify(_env(), pub, NOW)


def test_canonico_independe_da_ordem_das_chaves():
    a = {"b": 1, "a": {"y": 1, "x": 2}}
    b = {"a": {"x": 2, "y": 1}, "b": 1}
    assert canonical(a) == canonical(b)


def test_replay_recusado(keys):
    pub, priv = keys
    replay = ReplayWindow()
    msg = _signed(priv)
    verify(msg, pub, NOW, replay=replay)
    with pytest.raises(IdentityError) as e:
        verify(msg, pub, NOW + 1, replay=replay)
    assert e.value.code == "replay"


def test_id_volta_a_valer_apos_a_janela_mas_ts_velho_e_recusado(keys):
    pub, priv = keys
    replay = ReplayWindow(ttl=600, skew=120)
    msg = _signed(priv)
    verify(msg, pub, NOW, replay=replay)
    with pytest.raises(IdentityError):
        verify(msg, pub, NOW + 700, replay=replay)  # ts fora do skew


def test_relogio_dentro_de_2min_aceito(keys):
    pub, priv = keys
    verify(_signed(priv, ts=NOW - 119), pub, NOW, replay=ReplayWindow())
    verify(_signed(priv, ts=NOW + 119, id="018f0000-0000-7000-8000-000000000002"), pub, NOW, replay=ReplayWindow())


def test_relogio_fora_de_2min_recusado(keys):
    pub, priv = keys
    with pytest.raises(IdentityError) as e:
        verify(_signed(priv, ts=NOW - 121), pub, NOW, replay=ReplayWindow())
    assert e.value.code == "clock_skew"
    with pytest.raises(IdentityError):
        verify(_signed(priv, ts=NOW + 121), pub, NOW, replay=ReplayWindow())


def test_replay_esquece_ids_apos_ttl():
    replay = ReplayWindow(ttl=600, skew=120)
    replay.check("a", NOW, NOW)
    replay.check("b", NOW + 700, NOW + 700)  # purga "a"
    assert "a" not in replay._seen


def test_chave_revogada_recusada(keys):
    pub, priv = keys
    reg = Registry()
    verify(_signed(priv), pub, NOW, registry=reg)
    reg.revoke("inst-1")
    with pytest.raises(IdentityError) as e:
        verify(_signed(priv, id="018f0000-0000-7000-8000-000000000003"), pub, NOW, registry=reg)
    assert e.value.code == "revoked"


def test_rotacao_assinada_pela_chave_antiga(keys, tmp_path_factory):
    old_pub, old_priv = keys
    new_dir = tmp_path_factory.mktemp("nova")
    new_pub = generate_keypair(new_dir)
    stmt = rotate(old_priv, "inst-1", new_pub, NOW)
    verify_rotation(stmt, old_pub)
    assert stmt["new_public_key"] == new_pub


def test_rotacao_assinada_por_chave_alheia_recusada(keys, tmp_path_factory):
    old_pub, _ = keys
    intruso = load_private_key(_dir_com_chave(tmp_path_factory))
    new_pub = generate_keypair(tmp_path_factory.mktemp("n2"))
    stmt = rotate(intruso, "inst-1", new_pub, NOW)
    with pytest.raises(IdentityError):
        verify_rotation(stmt, old_pub)


def _dir_com_chave(factory):
    d = factory.mktemp("intruso")
    generate_keypair(d)
    return d


@pytest.mark.skipif(sys.platform == "win32", reason="permissoes POSIX")
def test_chave_privada_com_permissao_restrita(tmp_path):
    generate_keypair(tmp_path)
    arq = next(p for p in tmp_path.rglob("*.key"))
    assert stat.S_IMODE(os.stat(arq).st_mode) == 0o600


def test_gerar_nao_sobrescreve_chave_existente(tmp_path):
    a = generate_keypair(tmp_path)
    with pytest.raises(FileExistsError):
        generate_keypair(tmp_path)
    assert generate_keypair(tmp_path, force=True) != a
