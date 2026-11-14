"""Guarda global das rotas: taxa por IP, banimento, tamanho do corpo e cabecalhos (spec de 2026-11-14, fase A)."""

from heycode.relay.app import MAX_BODY, SECURITY_HEADERS


def test_ip_acima_da_taxa_recebe_429_com_retry_after_e_volta_depois(make_client, clock):
    client = make_client(ip_limit=5)
    for _ in range(5):
        assert client.get("/v1/installations").status_code == 401
    r = client.get("/v1/installations")
    assert r.status_code == 429 and r.json() == {"detail": "muitas tentativas"}
    assert r.headers["retry-after"] == "60"
    clock.t += 61
    assert client.get("/v1/installations").status_code == 401


def test_health_nao_conta_para_a_taxa(make_client):
    client = make_client(ip_limit=2)
    for _ in range(10):
        assert client.get("/health").status_code == 200
    assert client.get("/v1/installations").status_code == 401


def test_insistir_alem_da_taxa_bane_o_ip_por_15_minutos(make_client, clock):
    client = make_client(ip_limit=1)
    client.get("/v1/installations")
    for _ in range(21):  # 20 faltas cabem; a 21a bane
        assert client.get("/v1/installations").status_code == 429
    clock.t += 61  # a janela da taxa passou, mas o banimento nao
    r = client.get("/v1/installations")
    assert r.status_code == 429 and r.headers["retry-after"] == "839"
    assert client.get("/health").status_code == 200
    clock.t += 840
    assert client.get("/v1/installations").status_code == 401


def test_corpo_declarado_acima_do_teto_recebe_413_sem_ser_lido(client):
    big = "a" * (MAX_BODY + 1)
    r = client.post("/v1/login", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    r = client.post("/v1/login", content=b"{}", headers={"Content-Type": "application/json", "Content-Length": "x"})
    assert r.status_code == 413


def test_campos_tem_teto_de_tamanho(client):
    r = client.post("/v1/login", json={"email": "a@b.co", "password": "s" * 257})
    assert r.status_code == 422
    r = client.post("/v1/register", json={"email": "a" * 250 + "@b.co", "password": "senha-bem-longa"})
    assert r.status_code == 422
    r = client.post("/v1/pair/redeem", json={"code": "A" * 65, "public_key": "k"})
    assert r.status_code == 422


def test_toda_resposta_leva_os_cabecalhos_de_seguranca(client):
    for path in ("/health", "/v1/installations", "/nao-existe"):
        r = client.get(path)
        for name, value in SECURITY_HEADERS.items():
            assert r.headers[name] == value, (path, name)
    refused = client.post("/v1/login", content="a" * (MAX_BODY + 1))
    assert refused.headers["x-frame-options"] == "DENY"


def test_painel_mantem_a_propria_csp(client):
    csp = client.get("/app").headers["content-security-policy"]
    assert "script-src 'self'" in csp and "style-src 'self'" in csp


def test_documentacao_automatica_fica_desligada(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
