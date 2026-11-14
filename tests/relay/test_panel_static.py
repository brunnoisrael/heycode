import re
from pathlib import Path

import pytest
from conftest import Clock
from fastapi.testclient import TestClient

from heycode.relay.app import create_app
from heycode.relay.repo import SqliteRepository

PANEL = Path(__file__).resolve().parents[2] / "src" / "heycode" / "relay" / "panel"


@pytest.fixture
def client():
    with TestClient(create_app(SqliteRepository(":memory:"), Clock())) as c:
        yield c


def test_pagina_do_painel_e_servida_com_csp_rigida(client):
    r = client.get("/app")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    csp = r.headers["content-security-policy"]
    for directive in (
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ):
        assert directive in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp and "*" not in csp
    assert "no-store" in r.headers["cache-control"]
    assert r.headers["x-frame-options"] == "DENY"


def test_arquivos_estaticos_tem_tipo_certo_e_so_a_lista_fechada(client):
    js = client.get("/app/static/panel.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    css = client.get("/app/static/panel.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
    for path in (
        "/app/static/index.html",
        "/app/static/nao-existe.js",
        "/app/static/%2e%2e/app.py",
        "/app/static/..%2fapp.py",
        "/app/static/../app.py",
        "/app/static/panel.js/x",
    ):
        assert client.get(path).status_code == 404


def test_html_nao_tem_script_inline_estilo_inline_nem_recurso_externo():
    html = (PANEL / "index.html").read_text(encoding="utf-8")
    assert '<html lang="pt-BR"' in html and 'name="viewport"' in html
    scripts = re.findall(r"<script\b[^>]*>", html)
    assert scripts == ['<script type="module" src="/app/static/panel.js">']
    assert all(body.strip() == "" for body in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S))
    assert " style=" not in html and "<style" not in html
    assert not re.search(r"\bon[a-z]+\s*=", html)  # nenhum onclick= e parentes
    assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", html)  # nada de dominio externo


def test_js_nunca_monta_html_com_dados_nem_avalia_texto():
    js = (PANEL / "panel.js").read_text(encoding="utf-8")
    for proibido in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
        "srcdoc",
    ):
        assert proibido not in js, proibido
    assert "X-CSRF-Token" in js and "credentials" in js


def test_js_so_guarda_preferencias_visuais_no_navegador():
    js = (PANEL / "panel.js").read_text(encoding="utf-8")
    chaves = set(re.findall(r"localStorage\.(?:set|get|remove)Item\(\s*['\"]([^'\"]+)['\"]", js))
    assert chaves <= {"hc_theme", "hc_accent"}
    assert "sessionStorage" not in js and "document.cookie" not in js


def test_css_sem_import_nem_url_externa():
    css = (PANEL / "panel.css").read_text(encoding="utf-8")
    assert "@import" not in css and not re.search(r"url\(\s*['\"]?(https?:)?//", css)


def test_painel_cobre_as_telas_da_spec():
    js = (PANEL / "panel.js").read_text(encoding="utf-8")
    for rota in ("#/inicio", "#/computadores", "#/dispositivos", "#/rastro", "#/comandos", "#/parear", "#/conta"):
        assert rota in js, rota
