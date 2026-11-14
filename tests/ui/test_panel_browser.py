"""Painel em navegador de verdade (Playwright + Chromium) contra um relay real. Pula se o Playwright faltar."""

import asyncio
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect

from heycode.identity.keys import generate_keypair, load_private_key  # noqa: E402
from heycode.relay.app import create_app  # noqa: E402
from heycode.relay.repo import SqliteRepository  # noqa: E402
from heycode.relay_client import RelayClient, ws_url  # noqa: E402
from heycode.relay_executor import BridgeExecutor  # noqa: E402

EMAIL, PASSWORD = "ana@exemplo.com", "senha-bem-longa"
XSS = "<img src=x onerror=window.__pwned=1> teste"


@pytest.fixture(scope="module")
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    repo = SqliteRepository(":memory:")
    srv = uvicorn.Server(uvicorn.Config(create_app(repo, time.time), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield base, repo
    srv.should_exit = True
    thread.join(5)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - sem Chromium instalado: pula
            pytest.skip(f"Chromium indisponivel: {exc}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser, server):
    base, _ = server
    ctx = browser.new_context(viewport={"width": 1100, "height": 800}, locale="pt-BR")
    pg = ctx.new_page()
    pg.problems, pg.js_errors = [], []
    pg.on("console", lambda m: pg.problems.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.js_errors.append(str(e)))
    pg.base = base
    yield pg
    ctx.close()


def nav(page, label, title=None):
    """Navega pelo menu e espera o titulo da tela. Sem wait_for_function: a CSP do painel proibe eval, de proposito."""
    page.get_by_role("link", name=label, exact=True).click()
    expect(page.locator("main h1")).to_have_text(title or label)


def test_01_cria_a_conta_e_cai_na_visao_geral_vazia(page, server):
    page.goto(page.base + "/app")
    page.get_by_role("button", name="Criar conta").first.click()
    page.fill("#email", EMAIL)
    page.fill("#pass", PASSWORD)
    page.locator("form button[type=submit]").click()
    page.wait_for_selector("main h1")
    assert page.inner_text("main h1") == "Visão geral"
    assert page.get_attribute("nav a[aria-current=page]", "href") == "#/inicio"
    assert [t.strip().split()[0] for t in page.locator(".stat-value").all_inner_texts()] == ["0", "0", "0"]
    assert page.locator(".steps li.done").count() == 0 and "Nada registrado ainda" in page.inner_text("main")
    assert page.locator("nav svg.icon").count() == 7 and EMAIL in page.inner_text(".who")
    nav(page, "Computadores")
    assert "Nenhum computador pareado" in page.inner_text("main")
    assert page.get_attribute("nav a[aria-current=page]", "href") == "#/computadores"


def test_02_cookie_e_httponly_samesite_e_invisivel_ao_javascript(page):
    cookie = next(c for c in page.context.cookies() if c["name"] == "hc_session")
    assert cookie["httpOnly"] is True and cookie["sameSite"] == "Strict"
    assert "hc_session" not in page.evaluate("document.cookie")
    assert page.evaluate("Object.keys(localStorage)") == []  # nenhum token guardado no navegador


def test_03_escrita_sem_csrf_e_recusada_pelo_servidor(page):
    status = page.evaluate("fetch('/v1/pair/codes', {method: 'POST', credentials: 'same-origin'}).then(r => r.status)")
    assert status == 403


def test_04_pareamento_ponta_a_ponta_com_codigo_de_verificacao(page, server):
    base, _ = server
    nav(page, "Parear", "Parear um computador")
    page.get_by_role("button", name="Gerar código de pareamento").click()
    page.wait_for_selector(".code")
    code = page.inner_text(".code")
    assert len(code) == 8 and code in page.inner_text("pre.cmd")
    machine = httpx.post(
        base + "/v1/pair/redeem", json={"code": code, "public_key": "chave-publica-de-teste", "name": "Notebook"}
    )
    assert machine.status_code == 200
    page.wait_for_selector(".verify", timeout=8000)
    assert page.inner_text(".verify") == machine.json()["verification"]  # o mesmo codigo dos dois lados
    page.get_by_role("button", name="O código confere: parear").click()
    expect(page.locator("#toast")).to_contain_text("Aguardando")  # so um lado confirmou ate aqui
    done = httpx.post(base + "/v1/pair/machine-confirm", json={"pending_id": machine.json()["pending_id"]})
    assert done.json()["state"] == "done"


def test_05_computador_aparece_offline_e_pode_ser_renomeado(page):
    nav(page, "Computadores")
    expect(page.locator(".card .name")).to_be_visible()
    assert "Notebook" in page.inner_text(".card .name") and "Offline" in page.inner_text(".card .meta")
    page.get_by_role("button", name="Renomear").click()
    modal = page.locator("dialog.modal[open]")
    expect(modal.locator("#ask-input")).to_have_value("Notebook")
    modal.get_by_role("button", name="Cancelar").click()  # cancelar nao muda nada
    expect(page.locator("dialog.modal")).to_have_count(0)
    assert "Notebook da sala" not in page.inner_text(".card .name")
    page.get_by_role("button", name="Renomear").click()
    page.fill("#ask-input", "Notebook da sala")
    page.get_by_role("button", name="Salvar nome").click()
    expect(page.locator(".card .name")).to_contain_text("Notebook da sala")
    expect(page.locator("dialog.modal")).to_have_count(0)


def test_05b_visao_geral_resume_computadores_passos_e_atividade(page):
    nav(page, "Visão geral")
    values = [t.strip().split()[0] for t in page.locator(".stat-value").all_inner_texts()]
    assert values == ["0", "0", "0"] and "de 1" in page.inner_text(".stats")  # um computador pareado, offline
    assert page.locator(".steps li.done").count() == 1
    expect(page.locator(".feed")).to_contain_text("Painel: renomeou um computador")
    page.get_by_role("button", name="Ver o rastro completo").click()
    expect(page.locator("main h1")).to_have_text("Rastro")


def test_06_dispositivo_novo_precisa_de_autorizacao_e_vira_rastro(page, server):
    base, repo = server
    inst = httpx.get(base + "/v1/installations", headers=_bearer(base)).json()[0]
    account_id = repo.get_installation(inst["id"])["account_id"]
    repo.add_pending_device(account_id, inst["id"], "amzn1.ask.device.TESTE1234", time.time(), 10)
    nav(page, "Dispositivos", "Dispositivos Alexa")
    expect(page.locator("main")).to_contain_text("Aguardando sua autorização")
    assert "1234" in page.inner_text("main")
    page.get_by_role("button", name="Autorizar").click()
    expect(page.locator("main")).to_contain_text("Nenhuma solicitação")
    assert page.get_by_role("button", name="Revogar").count() == 1
    nav(page, "Rastro")
    page.wait_for_selector("table tbody tr")
    assert "Painel: aprovou um dispositivo" in page.inner_text("main")


def test_07_rastro_detalhe_com_computador_offline_explica(page):
    page.get_by_role("button", name="Ver o que o computador registrou").click()
    expect(page.locator("main")).to_contain_text("offline")


def test_08_comando_novo_e_html_malicioso_aparece_como_texto(page):
    nav(page, "Comandos")
    page.fill("#c-name", XSS)
    page.fill("#c-instruction", "rode os testes e resuma as falhas")
    expect(page.locator(".field", has=page.locator("#c-instruction")).locator(".num")).to_have_text("33/500")
    assert page.locator("#c-enabled.switch").is_checked()
    page.get_by_role("button", name="Salvar").click()
    page.wait_for_selector(".card .name")
    assert "<img src=x" in page.inner_text(".card .name")  # visivel como texto, nao interpretado
    assert page.locator("main img").count() == 0
    assert page.evaluate("window.__pwned") is None
    page.get_by_role("button", name="Desligar").click()
    expect(page.locator(".badge").first).to_have_text("desligado")
    page.get_by_role("button", name="Apagar").click()
    page.get_by_role("button", name="Apagar comando").click()
    page.wait_for_selector("text=Nenhum comando ainda")


def test_08b_comandos_do_computador_aparecem_e_so_podem_ser_desligados(page, server, tmp_path_factory):
    base, _ = server
    auth = _bearer(base)
    keydir = tmp_path_factory.mktemp("servidor")
    pub = generate_keypair(keydir)
    code = httpx.post(base + "/v1/pair/codes", headers=auth).json()["code"]
    pid = httpx.post(
        base + "/v1/pair/redeem", json={"code": code, "public_key": pub, "name": "Servidor de testes"}
    ).json()["pending_id"]
    httpx.post(base + "/v1/pair/machine-confirm", json={"pending_id": pid})
    iid = httpx.post(base + "/v1/pair/confirm", headers=auth, json={"pending_id": pid}).json()["installation_id"]

    received = []

    def bridge(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        received.append((request.method, request.url.path, body))
        if request.url.path == "/voice/commands":
            return httpx.Response(
                200,
                json={
                    "commands": [
                        {
                            "name": "reiniciar app",
                            "aliases": [],
                            "type": "script",
                            "risk": "confirmar",
                            "enabled": True,
                            "description": "reinicia o servico",
                        },
                        {
                            "name": "ver disco",
                            "aliases": [],
                            "type": "script",
                            "risk": "leitura",
                            "enabled": True,
                            "description": "",
                        },
                    ]
                },
            )
        return httpx.Response(200, json={"ok": True, "speech": "desligado"})

    executor = BridgeExecutor(
        "http://127.0.0.1:8765", "segredo-local", auto_allowed=lambda: False, transport=httpx.MockTransport(bridge)
    )

    async def instruction(payload):
        return {"run_id": "1", "state": "done", "summary": "ok"}

    client = RelayClient(ws_url(base), iid, load_private_key(keydir), instruction, bridge=executor)
    loop = asyncio.new_event_loop()
    holder = {}

    def run():
        asyncio.set_event_loop(loop)
        holder["t"] = loop.create_task(client.run_forever())
        try:
            loop.run_until_complete(holder["t"])
        except asyncio.CancelledError:
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        for _ in range(100):  # espera o computador conectar
            online = [i for i in httpx.get(base + "/v1/installations", headers=auth).json() if i["id"] == iid]
            if online and online[0]["online"]:
                break
            time.sleep(0.05)
        nav(page, "Conta")  # sair da tela atual: clicar no mesmo link nao recarrega os dados
        nav(page, "Comandos")
        page.select_option("#pc-sel", label="Servidor de testes")
        card = page.locator(".card.row", has_text="reiniciar app")
        expect(card).to_contain_text("pede confirmação")
        expect(page.locator(".card.row", has_text="ver disco")).to_contain_text("roda direto")
        texto_do_cartao = card.inner_text()
        assert "http" not in texto_do_cartao and "argv" not in texto_do_cartao  # o computador so anuncia o resumo
        card.get_by_role("button", name="Desligar").click()
        expect(page.locator("#toast")).to_contain_text("desligado")
        assert ("POST", "/voice/commands/disable", {"name": "reiniciar app"}) in received
        nav(page, "Rastro")
        expect(page.locator("main")).to_contain_text("Painel: desligou um comando do computador")
    finally:
        loop.call_soon_threadsafe(holder["t"].cancel)
        thread.join(5)


def test_09_tema_e_cor_persistem_so_no_navegador(page):
    nav(page, "Conta")
    page.select_option("#theme", "dark")
    assert page.get_attribute("html", "data-theme") == "dark"
    page.get_by_label("Roxo").click()
    assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()") == "#7c3aed"
    page.reload()
    page.wait_for_selector("main h1")
    assert page.get_attribute("html", "data-theme") == "dark"
    assert sorted(page.evaluate("Object.keys(localStorage)")) == ["hc_accent", "hc_theme"]


def test_10_nenhuma_excecao_de_js_nem_violacao_de_csp_ate_aqui(page):
    assert page.js_errors == []
    assert not [m for m in page.problems if "Content Security Policy" in m or "Refused" in m]
    # o navegador registra como erro de console as respostas 4xx/5xx esperadas (sessao ainda nao aberta, CSRF
    # recusado de proposito, detalhe com o computador offline); qualquer outra coisa e problema
    esperados = ("status of 401", "status of 403", "status of 503")
    assert all("Failed to load resource" in m and any(e in m for e in esperados) for m in page.problems), page.problems


def test_11_sair_e_voltar_exige_login_e_excluir_conta_apaga_tudo(page, server):
    base, repo = server
    page.get_by_role("button", name="Sair").click()
    page.wait_for_selector("form #email")
    page.fill("#email", EMAIL)
    page.fill("#pass", PASSWORD)
    page.locator("form button[type=submit]").click()
    page.wait_for_selector("main h1")
    nav(page, "Conta")
    page.fill("#del-pw", "senha-errada-aqui")
    page.get_by_role("button", name="Excluir minha conta").click()
    page.get_by_role("button", name="Excluir definitivamente").click()
    expect(page.locator(".error")).to_contain_text("incorreta")
    page.fill("#del-pw", PASSWORD)
    page.get_by_role("button", name="Excluir minha conta").click()
    page.get_by_role("button", name="Excluir definitivamente").click()
    page.wait_for_selector("form #email")
    assert repo.count_audit() == 0 and repo.count_shortcuts() == 0
    assert httpx.post(base + "/v1/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401


def test_12_layout_estreito_nao_quebra(browser, server):
    base, _ = server
    ctx = browser.new_context(viewport={"width": 360, "height": 700})
    pg = ctx.new_page()
    pg.goto(base + "/app")
    pg.wait_for_selector(".auth")
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    pg.get_by_role("button", name="Criar conta").first.click()
    pg.fill("#email", "estreito@exemplo.com")
    pg.fill("#pass", PASSWORD)
    pg.locator("form button[type=submit]").click()
    for rota in ("inicio", "computadores", "rastro", "comandos", "parear", "conta"):
        pg.goto(base + "/app#/" + rota)
        pg.wait_for_selector("main h1")
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), rota
    assert pg.locator("nav a[aria-current=page]").bounding_box()["x"] >= 0  # o item atual do menu fica visivel
    ctx.close()


def _bearer(base):
    token = httpx.post(base + "/v1/login", json={"email": EMAIL, "password": PASSWORD}).json()["token"]
    return {"Authorization": "Bearer " + token}
