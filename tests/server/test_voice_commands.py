import json
import sys

import httpx
import pytest

PY = sys.executable


def script(code, name="rodar tarefa", risk="leitura", **over):
    d = {"name": name, "type": "script", "risk": risk, "argv": [PY, "-c", code]}
    d.update(over)
    return d


@pytest.fixture
def home_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def put(home_env):
    def write(*cmds):
        (home_env / "commands.json").write_text(json.dumps({"version": 1, "commands": list(cmds)}), encoding="utf-8")

    return write


def run(client, spoken):
    return client.post("/voice/commands/run", json={"spoken": spoken}).json()


def test_rotas_exigem_o_segredo_de_controle(home_env, client):
    for method, path in (
        ("GET", "/voice/commands"),
        ("POST", "/voice/commands/run"),
        ("POST", "/voice/commands/confirm"),
        ("POST", "/voice/commands/cancel"),
        ("POST", "/voice/commands/disable"),
    ):
        for headers in ({"x-secret": "errado"}, client.agent_h):  # segredo de agente tambem nao serve
            r = client.request(method, path, headers=headers, json={})
            assert r.status_code in (401, 403), (method, path)


def test_lista_so_o_resumo(home_env, client, put):
    put(script("print('segredo-no-argv')", description="d"))
    body = client.get("/voice/commands").json()
    assert body["commands"] == [
        {
            "name": "rodar tarefa",
            "aliases": [],
            "type": "script",
            "risk": "leitura",
            "enabled": True,
            "description": "d",
        }
    ]
    assert "segredo-no-argv" not in json.dumps(body) and PY not in json.dumps(body)


def test_lista_vazia_sem_arquivo_e_registro_invalido_nao_derruba(home_env, client, put):
    assert client.get("/voice/commands").json() == {"commands": []}
    put({"name": "x", "type": "script", "risk": "leitura", "argv": []})
    body = client.get("/voice/commands").json()
    assert body["commands"] == [] and body["error"] == "registro_invalido"


def test_leitura_roda_loga_no_historico_e_aparece_no_audit_sem_saida(home_env, client, put):
    put(script("print('ghp_' + 'a'*36); print('resultado-da-saida')"))
    r = run(client, "rodar tarefa")
    assert r["ok"] and r["label"] == "rodar tarefa" and "ghp_" not in r["speech"]
    audit = client.get("/voice/audit").json()
    (ev,) = audit["commands"]
    assert (ev["name"], ev["risk"], ev["type"], ev["outcome"], ev["exit_code"]) == (
        "rodar tarefa",
        "leitura",
        "script",
        "ok",
        0,
    )
    assert "resultado-da-saida" not in json.dumps(audit)


def test_confirmar_so_roda_depois_do_confirma(home_env, client, put, tmp_path):
    marker = tmp_path / "ok.txt"
    put(script(f"open({str(marker)!r}, 'w').write('x')", risk="confirmar"))
    r = run(client, "rodar tarefa")
    assert r["pending"] == {"risk": "confirmar"} and not marker.exists()
    done = client.post("/voice/commands/confirm", json={}).json()
    assert done["done"] is True and marker.exists()
    assert client.post("/voice/commands/confirm", json={}).json()["done"] is False


def test_pin_exige_o_pin_da_ponte_com_bloqueio_por_tentativas(home_env, client, put, tmp_path):
    marker = tmp_path / "pin.txt"
    put(script(f"open({str(marker)!r}, 'w').write('x')", risk="pin"))
    run(client, "rodar tarefa")
    assert "PIN" in client.post("/voice/commands/confirm", json={}).json()["speech"]  # sem PIN: pede
    wrong = client.post("/voice/commands/confirm", json={"pin": "0000"}).json()
    assert wrong["done"] is False and "PIN incorreto" in wrong["speech"] and not marker.exists()
    client.post("/voice/commands/confirm", json={"pin": "1111"})
    third = client.post("/voice/commands/confirm", json={"pin": "2222"}).json()
    assert "bloqueada" in third["speech"] and not marker.exists()
    locked = client.post("/voice/commands/confirm", json={"pin": "1234"}).json()  # nem o PIN certo passa travado
    assert locked["done"] is False and "bloqueada" in locked["speech"] and not marker.exists()


def test_pin_certo_executa(home_env, client, put, tmp_path):
    marker = tmp_path / "pin2.txt"
    put(script(f"open({str(marker)!r}, 'w').write('x')", risk="pin"))
    run(client, "rodar tarefa")
    done = client.post("/voice/commands/confirm", json={"pin": "1234"}).json()
    assert done["done"] is True and marker.exists()


def test_cancelar_limpa_a_pendencia(home_env, client, put):
    put(script("print(1)", risk="confirmar"))
    run(client, "rodar tarefa")
    assert client.post("/voice/commands/cancel").json()["ok"]
    assert client.post("/voice/commands/confirm", json={}).json()["done"] is False


def test_disable_so_desliga_e_persiste_no_arquivo(home_env, client, put):
    put(script("print(1)"))
    assert client.post("/voice/commands/disable", json={"name": "rodar tarefa"}).json()["ok"]
    saved = json.loads((home_env / "commands.json").read_text(encoding="utf-8"))
    assert saved["commands"][0]["enabled"] is False and saved["commands"][0]["argv"][0] == PY  # resto intacto
    assert "Não achei" in run(client, "rodar tarefa")["speech"]
    assert client.post("/voice/commands/disable", json={"name": "nada"}).json()["ok"] is False


def test_nao_existe_rota_para_ligar_nem_editar(home_env, client):
    for path in ("/voice/commands/enable", "/voice/commands/add", "/voice/commands/update", "/voice/commands/remove"):
        assert client.post(path, json={"name": "x"}).status_code in (404, 405)


def test_webhook_usa_segredo_do_config_env_local_e_nunca_o_devolve(home_env, client, put):
    (home_env / "config.env").write_text("HA_TOKEN=Bearer token-local-xyz\n", encoding="utf-8")
    put(
        {
            "name": "acender luz",
            "type": "webhook",
            "risk": "leitura",
            "method": "GET",
            "url": "https://casa.exemplo.com/luz",
            "headers": {"Authorization": "env:HA_TOKEN"},
        }
    )
    seen = []

    def handler(request):
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, text="aceso")

    client.server.command_runner._transport = httpx.MockTransport(handler)
    r = run(client, "acender luz")
    assert r["ok"] and seen == ["Bearer token-local-xyz"]
    assert "token-local-xyz" not in json.dumps(
        [r, client.get("/voice/audit").json(), client.get("/voice/commands").json()]
    )


def test_pergunta_com_texto_malicioso_nao_vira_argumento(home_env, client, put):
    put(script("import sys; print('argc', len(sys.argv))"))
    r = run(client, "rodar tarefa")
    assert "argc 1" in r["speech"]
    assert client.post("/voice/commands/run", json={"spoken": "x" * 500}).status_code == 422  # tamanho limitado
