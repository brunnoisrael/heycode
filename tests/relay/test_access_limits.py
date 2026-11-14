from concurrent.futures import ThreadPoolExecutor

from heycode.relay.limits import RateLimiter


def test_criacao_de_contas_tem_limite_por_origem(client, clock):
    for _ in range(10):
        assert client.post("/v1/register", json={"email": "invalido", "password": "senha-bem-longa"}).status_code == 400
    assert (
        client.post("/v1/register", json={"email": "outro@exemplo.com", "password": "senha-bem-longa"}).status_code
        == 429
    )
    clock.t += 61
    assert (
        client.post("/v1/register", json={"email": "outro@exemplo.com", "password": "senha-bem-longa"}).status_code
        == 201
    )


def test_limite_resiste_a_requisicoes_concorrentes():
    limiter = RateLimiter(lambda: 1000, limit=10, window=60)
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(limiter.allow, ["mesma-origem"] * 200))
    assert sum(results) == 10
