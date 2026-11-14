"""Site publico em navegador de verdade (ADR 0059): sem erro, sem violacao de CSP e sem transbordar."""

import re
import socket
import threading
import time

import httpx
import pytest
import uvicorn

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect

from heycode.relay.app import create_app  # noqa: E402
from heycode.relay.repo import SqliteRepository  # noqa: E402

FIRST = "Alexa, pergunte ao HeyCode o status"


@pytest.fixture(scope="module")
def base():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = create_app(SqliteRepository(":memory:"), time.time)
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(url + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield url
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


def open_page(browser, width=1280, **context):
    ctx = browser.new_context(viewport={"width": width, "height": 800}, locale="pt-BR", **context)
    page = ctx.new_page()
    page.problems = []
    page.on("console", lambda m: page.problems.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: page.problems.append(str(e)))
    return page


def test_inicio_carrega_limpo_e_a_demonstracao_troca_de_cena(browser, base):
    page = open_page(browser)
    page.goto(base + "/")
    expect(page.locator("h1")).to_contain_text("Seus agentes fazem.")
    expect(page.locator("#demo-said")).to_have_text(FIRST)
    expect(page.locator("#demo-said")).not_to_have_text(FIRST, timeout=9000)  # a segunda cena comecou a ser digitada
    assert page.locator(".stage").get_attribute("aria-hidden") == "true" and page.locator("p.sr").count() == 1
    assert page.problems == []
    page.context.close()


def test_sem_movimento_a_primeira_cena_fica_parada(browser, base):
    page = open_page(browser, reduced_motion="reduce")
    page.goto(base + "/")
    page.wait_for_timeout(5200)
    expect(page.locator("#demo-said")).to_have_text(FIRST)
    assert page.problems == []
    page.context.close()


def test_caminhos_levam_ao_painel_e_a_pagina_de_apoio(browser, base):
    page = open_page(browser)
    page.goto(base + "/")
    page.get_by_role("link", name="Ver como apoiar").click()
    expect(page).to_have_url(base + "/apoie")
    expect(page.locator("h1")).to_contain_text("não assinatura")
    assert page.locator(".tier").count() == 3 and page.locator("details").count() == 5
    page.get_by_role("link", name="Abrir Plano e apoio").click()
    expect(page).to_have_url(re.compile(r"/app#/plano$"))
    page.wait_for_selector(".auth")  # sem sessao, o painel pede o login
    assert not [m for m in page.problems if "401" not in m], page.problems
    page.context.close()


@pytest.mark.parametrize("path", ["/", "/apoie"])
def test_layout_estreito_nao_transborda(browser, base, path):
    page = open_page(browser, width=360)
    page.goto(base + path)
    page.wait_for_selector("footer")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert page.problems == []
    page.context.close()
