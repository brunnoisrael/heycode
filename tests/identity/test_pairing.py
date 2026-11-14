import pytest

from heycode.identity import IdentityError
from heycode.identity.pairing import ALPHABET, PairingService


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def svc(clock):
    return PairingService(clock)


def test_codigo_tem_8_caracteres_sem_ambiguos(svc):
    code = svc.issue("conta-a")
    assert len(code) == 8
    assert set(code) <= set(ALPHABET)
    assert not set("01OIL") & set(ALPHABET)


def test_vinculo_so_com_confirmacao_nos_dois_lados(svc):
    code = svc.issue("conta-a")
    pending = svc.redeem(code, "pub-1", source="m1")
    assert svc.confirm(pending.id, "machine") is None
    binding = svc.confirm(pending.id, "account", account_id="conta-a")
    assert binding is not None and binding.account_id == "conta-a" and binding.public_key == "pub-1"


def test_confirmacao_so_de_um_lado_nao_vincula(svc):
    pending = svc.redeem(svc.issue("conta-a"), "pub-1", source="m1")
    assert svc.confirm(pending.id, "account", account_id="conta-a") is None
    assert svc.confirm(pending.id, "account", account_id="conta-a") is None  # repetir o mesmo lado nao basta


def test_codigo_uso_unico(svc):
    code = svc.issue("conta-a")
    svc.redeem(code, "pub-1", source="m1")
    with pytest.raises(IdentityError) as e:
        svc.redeem(code, "pub-2", source="m2")
    assert e.value.code == "invalid_code"


def test_codigo_expira_em_5min(svc, clock):
    code = svc.issue("conta-a")
    clock.t += 301
    with pytest.raises(IdentityError) as e:
        svc.redeem(code, "pub-1", source="m1")
    assert e.value.code == "invalid_code"


def test_pendencia_expira_em_5min_apos_o_resgate(svc, clock):
    pending = svc.redeem(svc.issue("conta-a"), "pub-1", source="m1")
    svc.confirm(pending.id, "machine")
    clock.t += 301
    with pytest.raises(IdentityError):
        svc.confirm(pending.id, "account", account_id="conta-a")


def test_limite_de_5_tentativas_bloqueia_codigo(svc):
    code = svc.issue("conta-a")
    for _ in range(5):
        with pytest.raises(IdentityError) as e:
            svc.redeem("AAAAAAAA", "pub-x", source="atacante")
        assert e.value.code == "invalid_code"
    with pytest.raises(IdentityError) as e:
        svc.redeem(code, "pub-x", source="atacante")  # ate o codigo certo e recusado
    assert e.value.code == "locked"


def test_bloqueio_de_uma_origem_nao_afeta_outra(svc):
    code = svc.issue("conta-a")
    for _ in range(5):
        with pytest.raises(IdentityError):
            svc.redeem("AAAAAAAA", "pub-x", source="atacante")
    assert svc.redeem(code, "pub-1", source="legitima").id


def test_bloqueio_acaba_apos_a_janela(svc, clock):
    for _ in range(5):
        with pytest.raises(IdentityError):
            svc.redeem("AAAAAAAA", "pub-x", source="s")
    clock.t += 301
    with pytest.raises(IdentityError) as e:
        svc.redeem("AAAAAAAA", "pub-x", source="s")
    assert e.value.code == "invalid_code"


def test_codigo_de_outra_conta_nao_vincula(svc):
    pending = svc.redeem(svc.issue("conta-a"), "pub-1", source="m1")
    svc.confirm(pending.id, "machine")
    with pytest.raises(IdentityError) as e:
        svc.confirm(pending.id, "account", account_id="conta-b")
    assert e.value.code == "wrong_account"


def test_codigo_de_verificacao_e_derivado_e_igual_nos_dois_lados(svc):
    code = svc.issue("conta-a")
    p = svc.redeem(code, "pub-1", source="m1")
    assert len(p.verification) == 6 and p.verification.isdigit()
    other = PairingService(Clock())
    p2 = other.redeem(other.issue("conta-a"), "pub-1", source="m1")
    assert p2.verification != p.verification  # depende do codigo, nao so da chave


def test_pendencia_nao_vincula_duas_vezes(svc):
    pending = svc.redeem(svc.issue("conta-a"), "pub-1", source="m1")
    svc.confirm(pending.id, "machine")
    assert svc.confirm(pending.id, "account", account_id="conta-a")
    with pytest.raises(IdentityError):
        svc.confirm(pending.id, "machine")
