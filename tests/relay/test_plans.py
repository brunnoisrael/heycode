"""Niveis de apoio (ADR 0059): limites por nivel, interesse registrado pela conta e concessao pelo dono."""

from conftest import signup

from heycode.relay import grant
from heycode.relay.plans import PLANS, limits_for, tiers
from heycode.relay.repo import SqliteRepository


def account_id(client, email):
    return client.app.state.repo.get_account_by_email(email)["id"]


def pair(client, auth, key):
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    pid = client.post("/v1/pair/redeem", json={"code": code, "public_key": key}).json()["pending_id"]
    client.post("/v1/pair/machine-confirm", json={"pending_id": pid})
    return client.post("/v1/pair/confirm", json={"pending_id": pid}, headers=auth)


def shortcut(client, auth, n):
    body = {"name": f"comando numero {n}", "agent": "claude", "instruction": "rode os testes"}
    return client.post("/v1/commands", json=body, headers=auth)


def test_niveis_crescem_e_o_livre_usa_a_cota_configurada():
    assert limits_for("livre", 50) == {"installations": 2, "shortcuts": 30, "daily_quota": 50}
    assert limits_for("apoiador", 50)["daily_quota"] == 1000 and limits_for("apoiador", 5000)["daily_quota"] == 5000
    assert limits_for("nao-existe", 200) == limits_for("livre", 200)
    listed = tiers(200)
    assert [t["key"] for t in listed] == ["livre", "apoiador", "patrono"] and listed[0]["suggested"] == 0
    for a, b in zip(listed, listed[1:], strict=False):
        assert all(a[k] < b[k] for k in ("suggested", "installations", "shortcuts", "daily_quota"))


def test_conta_nova_e_livre_e_ve_limites_uso_e_niveis(client):
    auth = signup(client, "ana@exemplo.com")
    assert pair(client, auth, "chave-1").json()["state"] == "done"
    shortcut(client, auth, 1)
    plan = client.get("/v1/plan", headers=auth).json()
    assert plan["plan"] == "livre" and plan["interest"] is None
    assert plan["limits"] == {"installations": 2, "shortcuts": 30, "daily_quota": 200}
    assert plan["usage"] == {"installations": 1, "shortcuts": 1, "daily_quota": 0}
    assert [t["name"] for t in plan["tiers"]] == ["Livre", "Apoiador", "Patrono"]
    assert client.get("/v1/plan").status_code == 401


def test_livre_barra_no_terceiro_computador_e_apoiador_nao(client, clock):
    auth = signup(client, "ana@exemplo.com")
    assert pair(client, auth, "chave-1").json()["state"] == "done"
    assert pair(client, auth, "chave-2").json()["state"] == "done"
    assert pair(client, auth, "chave-3").json() == {"detail": "quota_installations"}
    client.app.state.repo.set_plan(account_id(client, "ana@exemplo.com"), "apoiador", clock())
    assert pair(client, auth, "chave-4").json()["state"] == "done"
    assert client.get("/v1/plan", headers=auth).json()["limits"]["installations"] == 4


def test_limite_de_atalhos_segue_o_nivel(client, clock):
    auth = signup(client, "ana@exemplo.com")
    for n in range(30):
        assert shortcut(client, auth, n).status_code == 201
    assert shortcut(client, auth, 30).json() == {"detail": "quota_commands"}
    client.app.state.repo.set_plan(account_id(client, "ana@exemplo.com"), "apoiador", clock())
    assert shortcut(client, auth, 30).status_code == 201


def test_cota_diaria_segue_o_nivel(make_client, clock):
    client = make_client(daily_quota=1)
    auth = signup(client, "ana@exemplo.com")
    pair(client, auth, "chave-1")
    body = {"text": "oi", "destination": "aberto"}
    assert client.post("/v1/skill/request", json=body, headers=auth).status_code == 200
    assert client.post("/v1/skill/request", json=body, headers=auth).json() == {"detail": "quota_requests"}
    client.app.state.repo.set_plan(account_id(client, "ana@exemplo.com"), "patrono", clock())
    assert client.post("/v1/skill/request", json=body, headers=auth).status_code == 200
    assert client.get("/v1/plan", headers=auth).json()["usage"]["daily_quota"] == 3


def test_interesse_registra_troca_retira_e_fica_no_rastro(client):
    ana, bia = signup(client, "ana@exemplo.com"), signup(client, "bia@exemplo.com")
    assert client.put("/v1/plan/interest", json={"tier": "apoiador"}, headers=ana).status_code == 204
    assert client.put("/v1/plan/interest", json={"tier": "patrono"}, headers=ana).status_code == 204
    assert client.get("/v1/plan", headers=ana).json()["interest"] == "patrono"
    assert client.get("/v1/plan", headers=bia).json()["interest"] is None  # isolamento entre contas
    assert client.get("/v1/plan", headers=ana).json()["plan"] == "livre"  # pedir nao concede
    for bad in ("livre", "ouro", "x" * 30):
        assert client.put("/v1/plan/interest", json={"tier": bad}, headers=ana).status_code == 422
    assert client.put("/v1/plan/interest", json={"tier": None}, headers=ana).status_code == 204
    assert client.get("/v1/plan", headers=ana).json()["interest"] is None
    trail = [(r["kind"], r["label"]) for r in client.get("/v1/audit", headers=ana).json()]
    assert trail[:3] == [("painel:interesse_apoio", x) for x in ("retirado", "patrono", "apoiador")]
    assert client.put("/v1/plan/interest", json={"tier": "apoiador"}).status_code == 401


def test_excluir_a_conta_apaga_nivel_e_interesse(client, clock):
    auth = signup(client, "ana@exemplo.com")
    repo = client.app.state.repo
    repo.set_plan(account_id(client, "ana@exemplo.com"), "apoiador", clock())
    client.put("/v1/plan/interest", json={"tier": "patrono"}, headers=auth)
    assert len(repo.list_plan_interest()) == 1
    assert (
        client.request("DELETE", "/v1/account", json={"password": "senha-bem-longa"}, headers=auth).status_code == 204
    )
    assert repo.list_plan_interest() == []
    again = signup(client, "ana@exemplo.com")
    assert client.get("/v1/plan", headers=again).json()["plan"] == "livre"


def test_grant_concede_recusa_e_lista_interessados(client, tmp_path):
    auth = signup(client, "ana@exemplo.com")
    client.put("/v1/plan/interest", json={"tier": "apoiador"}, headers=auth)
    repo, said = client.app.state.repo, []
    assert grant.run(["interest"], repo, said.append) == 0
    assert said == ["ana@exemplo.com\tquer apoiador\t(hoje: livre)", "1 pedido(s) de apoio"]
    assert grant.run(["set", " Ana@Exemplo.com ", "apoiador"], repo, said.append, lambda: 5.0) == 0
    assert said[-1] == "ana@exemplo.com agora e Apoiador"
    assert client.get("/v1/plan", headers=auth).json()["plan"] == "apoiador"
    assert client.get("/v1/audit", headers=auth).json()[0]["kind"] == "dono:conceder_nivel"
    assert grant.run(["set", "ana@exemplo.com", "ouro"], repo, said.append) == 2 and "nivel desconhecido" in said[-1]
    assert grant.run(["set", "ninguem@exemplo.com", "patrono"], repo, said.append) == 1
    assert grant.run([], repo, said.append) == 2 and said[-1] == grant.USAGE
    assert set(PLANS) == {"livre", "apoiador", "patrono"}


def test_grant_main_exige_o_banco_e_usa_o_arquivo(tmp_path, capsys):
    assert grant.main(["interest"], {}) == 2
    db = str(tmp_path / "relay.db")
    SqliteRepository(db)
    assert grant.main(["interest"], {"RELAY_DB": db}) == 0
    assert "0 pedido(s) de apoio" in capsys.readouterr().out
