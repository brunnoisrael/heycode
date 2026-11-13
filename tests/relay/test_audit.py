import pytest
from conftest import Machine
from test_alexa_endpoint import alexa, link, world  # noqa: F401  (fixture reaproveitada)

DEV = "amzn1.ask.device.A"
FIELDS = {"id", "t", "kind", "installation_id", "device_id", "result", "label"}


def rows(c, auth=None, **params):
    r = c.get("/v1/audit", params=params, headers=auth or {})
    assert r.status_code == 200, r.text
    return r.json()


def approved(world):  # noqa: F811
    c, env, clock, tf = world
    auth, tok = link(c)
    m = Machine(c, auth, tf.mktemp("m"), clock, "notebook")
    alexa(c, env, clock, token=tok)
    c.post("/v1/devices/approve", headers=auth, json={"installation_id": m.id, "device_id": DEV})
    return c, env, clock, auth, tok, m


def test_exige_autenticacao(world):  # noqa: F811
    c, *_ = world
    assert c.get("/v1/audit").status_code == 401


def test_dispositivo_novo_gera_linha_barrado_sem_conteudo(world):  # noqa: F811
    c, env, clock, tf = world
    auth, tok = link(c)
    m = Machine(c, auth, tf.mktemp("m"), clock)
    alexa(c, env, clock, token=tok, intent="ApproveIntent")
    (row,) = rows(c, auth)
    assert set(row) == FIELDS
    assert row["kind"] == "ApproveIntent" and row["result"] == "barrado"
    assert row["device_id"] == DEV and row["installation_id"] == m.id and row["t"] == clock()


def test_aprovada_e_offline_registra_offline(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    alexa(c, env, clock, token=tok, intent="StatusIntent")
    assert rows(c, auth, result="offline")[0]["kind"] == "StatusIntent"


def test_intent_sem_chamar_o_computador_vira_sem_acao(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    alexa(c, env, clock, token=tok, intent="ApproveIntent")  # sem pendencia lida: nada foi aprovado
    alexa(c, env, clock, token=tok, intent="AMAZON.HelpIntent")
    assert {r["result"] for r in rows(c, auth, device_id=DEV)[:2]} == {"sem_acao"}


def test_nenhum_conteudo_vai_para_o_rastro(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    alexa(c, env, clock, token=tok, intent="SendInstructionIntent")
    alexa(c, env, clock, token=tok, intent="ApproveIntent")
    texto = str(rows(c, auth))
    assert "4321" not in texto and "instrucao" not in texto.lower().replace("sendinstructionintent", "")


def test_acoes_do_painel_entram_no_rastro(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    c.put("/v1/default-installation", headers=auth, json={"installation_id": m.id})
    c.delete(f"/v1/devices/{m.id}/{DEV}", headers=auth)
    kinds = [r["kind"] for r in rows(c, auth)]
    assert "painel:revogar_dispositivo" in kinds and "painel:instalacao_padrao" in kinds
    assert "painel:aprovar_dispositivo" in kinds


def test_negar_e_revogar_computador_tambem(world):  # noqa: F811
    c, env, clock, tf = world
    auth, tok = link(c)
    m = Machine(c, auth, tf.mktemp("m"), clock)
    alexa(c, env, clock, token=tok)
    c.post("/v1/devices/deny", headers=auth, json={"installation_id": m.id, "device_id": DEV})
    c.delete(f"/v1/installations/{m.id}", headers=auth)
    kinds = [r["kind"] for r in rows(c, auth)]
    assert "painel:negar_dispositivo" in kinds and "painel:revogar_computador" in kinds


def test_conta_b_nunca_ve_o_rastro_da_conta_a(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    b_auth, _ = link(c, "b@exemplo.com")
    assert rows(c, b_auth) == []
    assert len(rows(c, auth)) >= 2


def test_ordem_filtros_e_paginacao(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    for _ in range(7):
        clock.t += 1
        alexa(c, env, clock, token=tok, intent="StatusIntent")
    todas = rows(c, auth, limit=100)
    assert [r["id"] for r in todas] == sorted((r["id"] for r in todas), reverse=True)  # mais recente primeiro
    pagina = rows(c, auth, limit=3)
    assert len(pagina) == 3
    proxima = rows(c, auth, limit=3, before=pagina[-1]["id"])
    assert proxima[0]["id"] < pagina[-1]["id"]
    assert all(r["installation_id"] == m.id for r in rows(c, auth, installation_id=m.id))
    assert rows(c, auth, installation_id="outra") == []
    assert len(rows(c, auth, limit=0)) == 1 and len(rows(c, auth, limit=9999)) <= 100


def test_retencao_de_30_dias_apaga_o_antigo(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    assert len(rows(c, auth)) >= 2
    clock.t += 31 * 86400
    token = c.post("/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()["token"]
    novo = {"Authorization": "Bearer " + token}
    c.put("/v1/default-installation", headers=novo, json={"installation_id": m.id})  # grava e dispara a limpeza
    restante = rows(c, novo)
    assert len(restante) == 1 and restante[0]["kind"] == "painel:instalacao_padrao"


def test_excluir_a_conta_apaga_o_rastro(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    assert rows(c, auth)
    c.request("DELETE", "/v1/account", headers=auth, json={"password": "senha-bem-longa"})
    assert c.app.state.repo.count_audit() == 0


def test_detalhe_com_computador_offline_diz_503(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    r = c.get("/v1/audit/detail", params={"installation_id": m.id}, headers=auth)
    assert r.status_code == 503 and r.json()["detail"] == "offline"


def test_detalhe_de_computador_alheio_e_404(world):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    b_auth, _ = link(c, "b@exemplo.com")
    assert c.get("/v1/audit/detail", params={"installation_id": m.id}, headers=b_auth).status_code == 404
    assert c.get("/v1/audit/detail", params={"installation_id": "nao-existe"}, headers=auth).status_code == 404


@pytest.mark.parametrize("cmd", ["x"])
def test_cookie_do_painel_le_o_rastro(world, cmd):  # noqa: F811
    c, env, clock, auth, tok, m = approved(world)
    c.cookies.clear()
    c.post("/v1/panel/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"})
    assert c.get("/v1/audit").status_code == 200
