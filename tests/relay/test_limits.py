from conftest import Clock

from heycode.relay.limits import BanList, RateLimiter


def test_chave_vazia_some_e_a_memoria_nao_cresce_com_origens_antigas():
    clock = Clock()
    limiter = RateLimiter(clock, limit=2, window=60)
    for i in range(50):
        assert limiter.allow(f"ip-{i}")
    assert len(limiter) == 50
    clock.t += 61
    assert limiter.allow("ip-0")
    assert limiter.retry_after("ip-1") == 0  # consultar tambem limpa a chave vencida
    assert len(limiter) == 49


def test_teto_de_chaves_expulsa_as_usadas_ha_mais_tempo():
    clock = Clock()
    limiter = RateLimiter(clock, limit=1, window=60, max_keys=3)
    for key in ("a", "b", "c"):
        assert limiter.allow(key)
    assert not limiter.allow("a")  # ainda lembrada
    assert limiter.allow("d")  # estoura o teto: "a" e a mais antiga e sai
    assert len(limiter) == 3
    assert limiter.allow("a")


def test_retry_after_diz_quanto_falta_para_a_proxima_vaga():
    clock = Clock()
    limiter = RateLimiter(clock, limit=2, window=60)
    assert limiter.retry_after("ip") == 0
    limiter.allow("ip")
    clock.t += 20
    limiter.allow("ip")
    assert not limiter.allow("ip")
    assert limiter.retry_after("ip") == 40
    clock.t += 40.5
    assert limiter.retry_after("ip") == 0 and limiter.allow("ip")


def test_banimento_comeca_depois_das_faltas_e_expira_sozinho():
    clock = Clock()
    bans = BanList(clock, points=3, window=300, duration=900)
    for _ in range(3):
        bans.strike("ip")
    assert bans.remaining("ip") == 0  # tres faltas ainda cabem
    bans.strike("ip")
    assert bans.remaining("ip") == 900
    assert bans.remaining("outro") == 0
    clock.t += 899
    assert bans.remaining("ip") == 1
    clock.t += 2
    assert bans.remaining("ip") == 0


def test_faltas_antigas_nao_contam_para_o_banimento():
    clock = Clock()
    bans = BanList(clock, points=2, window=300, duration=900)
    bans.strike("ip")
    bans.strike("ip")
    clock.t += 301
    bans.strike("ip")
    assert bans.remaining("ip") == 0


def test_lista_de_banidos_tem_teto():
    clock = Clock()
    bans = BanList(clock, points=1, window=300, duration=900, max_keys=2)
    for key in ("a", "b", "c"):
        bans.strike(key)
        bans.strike(key)
    assert bans.remaining("a") == 0 and bans.remaining("b") == 900 and bans.remaining("c") == 900
