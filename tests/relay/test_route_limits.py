"""Limites por rota: login por e-mail, rotas sem login, codigos por conta e memoria do pareamento (fase A)."""

from conftest import signup

from heycode.identity.pairing import PairingService
from heycode.relay import app as relay_app

GOOD = "senha-bem-longa"


def test_login_tem_limite_por_email_mesmo_vindo_de_varios_ips(client, clock):
    signup(client, "ana@exemplo.com")
    for i in range(19):  # o login do signup ja contou uma
        clock.t += 7  # espacado: o limite por IP (10/min) nao e o que barra aqui
        r = client.post("/v1/login", json={"email": " Ana@Exemplo.com ", "password": f"errada-{i:04d}"})
        assert r.status_code == 401
    clock.t += 7
    r = client.post("/v1/login", json={"email": "ana@exemplo.com", "password": GOOD})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert client.post("/v1/panel/login", json={"email": "ana@exemplo.com", "password": GOOD}).status_code == 429
    clock.t += 61  # zera o limite por IP; o do e-mail da Ana continua valendo
    other = client.post("/v1/login", json={"email": "bia@exemplo.com", "password": GOOD})
    assert other.status_code == 401  # outro e-mail nao e afetado
    assert client.post("/v1/login", json={"email": "ana@exemplo.com", "password": GOOD}).status_code == 429
    clock.t += 901
    assert client.post("/v1/login", json={"email": "ana@exemplo.com", "password": GOOD}).status_code == 200


def test_rotas_de_pareamento_sem_login_tem_limite_por_ip(client, clock):
    for _ in range(30):
        assert client.get("/v1/pair/nao-existe").status_code == 404
    r = client.get("/v1/pair/nao-existe")
    assert r.status_code == 429 and r.headers["retry-after"] == "60"
    assert client.post("/v1/pair/machine-confirm", json={"pending_id": "x"}).status_code == 429
    clock.t += 61
    assert client.post("/v1/pair/machine-confirm", json={"pending_id": "x"}).status_code == 400


def test_emissao_de_codigo_tem_limite_por_conta(client, clock):
    ana, bia = signup(client, "ana@exemplo.com"), signup(client, "bia@exemplo.com")
    for _ in range(10):
        assert client.post("/v1/pair/codes", headers=ana).status_code == 200
    assert client.post("/v1/pair/codes", headers=ana).status_code == 429
    assert client.post("/v1/pair/codes", headers=bia).status_code == 200
    clock.t += 61
    assert client.post("/v1/pair/codes", headers=ana).status_code == 200


def test_pareamentos_concluidos_lembrados_tem_teto(client, monkeypatch):
    monkeypatch.setattr(relay_app, "MAX_TRACKED_PAIRINGS", 1)
    auth = signup(client, "ana@exemplo.com")
    ids = []
    for key in ("chave-um", "chave-dois"):
        code = client.post("/v1/pair/codes", headers=auth).json()["code"]
        pid = client.post("/v1/pair/redeem", json={"code": code, "public_key": key}).json()["pending_id"]
        client.post("/v1/pair/machine-confirm", json={"pending_id": pid})
        assert client.post("/v1/pair/confirm", json={"pending_id": pid}, headers=auth).json()["state"] == "done"
        ids.append(pid)
    assert client.get(f"/v1/pair/{ids[0]}").status_code == 404  # o mais antigo saiu
    assert client.get(f"/v1/pair/{ids[1]}").json()["state"] == "done"


def test_pareamento_varre_codigos_pendencias_e_falhas_vencidos():
    now = [1000.0]
    service = PairingService(lambda: now[0])
    code = service.issue("conta")
    service.issue("conta")
    service.redeem(code, "chave", "ip-bom")
    for i in range(3):
        try:
            service.redeem("ERRADO", "chave", f"ip-{i}")
        except Exception:  # noqa: BLE001 - a falha e o que se quer registrar
            pass
    assert len(service._codes) == 1 and len(service._pending) == 1 and len(service._failures) == 3
    now[0] += 301
    service.issue("conta")
    assert len(service._codes) == 1 and not service._pending and not service._failures
