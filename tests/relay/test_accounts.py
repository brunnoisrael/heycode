import hashlib

import pytest

from heycode.relay.accounts import SESSION_TTL, AccountError, Accounts
from heycode.relay.repo import SqliteRepository


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def repo():
    return SqliteRepository(":memory:")


@pytest.fixture
def acc(repo, clock):
    return Accounts(repo, clock)


def test_cadastro_e_login(acc):
    aid = acc.register("A@Exemplo.com", "senha-bem-longa")
    token = acc.login("a@exemplo.com", "senha-bem-longa")
    assert acc.authenticate(token) == aid


def test_email_duplicado_recusado_sem_diferenciar_caixa(acc):
    acc.register("a@exemplo.com", "senha-bem-longa")
    with pytest.raises(AccountError) as e:
        acc.register("A@EXEMPLO.COM", "outra-senha-longa")
    assert e.value.code == "email_taken"


def test_senha_curta_recusada(acc):
    with pytest.raises(AccountError) as e:
        acc.register("a@exemplo.com", "curta")
    assert e.value.code == "weak_password"


def test_email_invalido_recusado(acc):
    with pytest.raises(AccountError) as e:
        acc.register("sem-arroba", "senha-bem-longa")
    assert e.value.code == "invalid_email"


def test_senha_errada_e_email_inexistente_dao_o_mesmo_erro(acc):
    acc.register("a@exemplo.com", "senha-bem-longa")
    with pytest.raises(AccountError) as e1:
        acc.login("a@exemplo.com", "senha-errada-aqui")
    with pytest.raises(AccountError) as e2:
        acc.login("naoexiste@exemplo.com", "senha-errada-aqui")
    assert (
        (e1.value.code, str(e1.value)) == (e2.value.code, str(e2.value)) == ("bad_credentials", "credenciais invalidas")
    )


def test_senha_guardada_como_argon2id(acc, repo):
    acc.register("a@exemplo.com", "senha-bem-longa")
    stored = repo.get_account_by_email("a@exemplo.com")["password_hash"]
    assert stored.startswith("$argon2id$") and "senha-bem-longa" not in stored


def test_token_guardado_so_como_hash(acc, repo):
    acc.register("a@exemplo.com", "senha-bem-longa")
    token = acc.login("a@exemplo.com", "senha-bem-longa")
    assert repo.session_hashes() == [hashlib.sha256(token.encode()).hexdigest()]
    assert token not in repo.session_hashes()


def test_sessao_expira_em_12h(acc, clock):
    acc.register("a@exemplo.com", "senha-bem-longa")
    token = acc.login("a@exemplo.com", "senha-bem-longa")
    clock.t += SESSION_TTL - 1
    assert acc.authenticate(token) is not None
    clock.t += 2
    assert acc.authenticate(token) is None


def test_logout_revoga(acc):
    acc.register("a@exemplo.com", "senha-bem-longa")
    token = acc.login("a@exemplo.com", "senha-bem-longa")
    acc.logout(token)
    assert acc.authenticate(token) is None


def test_token_invalido_ou_vazio_nao_autentica(acc):
    assert acc.authenticate("") is None
    assert acc.authenticate("inventado") is None
    assert acc.authenticate(None) is None
