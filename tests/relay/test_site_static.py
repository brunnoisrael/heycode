"""Site publico (ADR 0059): paginas estaticas com a CSP rigida, lista fechada e textos sem promessa de venda."""

import re
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2] / "src" / "heycode" / "relay" / "site"
PAGES = [p for p in ("index.html", "apoie.html") if (SITE / p).is_file()]
ROUTES = {"index.html": "/", "apoie.html": "/apoie"}


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).lower()


@pytest.mark.parametrize("page", PAGES)
def test_pagina_publica_e_servida_com_csp_rigida_e_cache_curto(client, page):
    r = client.get(ROUTES[page])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    csp = r.headers["content-security-policy"]
    for directive in ("default-src 'none'", "script-src 'self'", "style-src 'self'", "frame-ancestors 'none'"):
        assert directive in csp
    assert "unsafe" not in csp and "*" not in csp
    assert r.headers["cache-control"] == "public, max-age=300" and r.headers["x-frame-options"] == "DENY"
    assert "set-cookie" not in r.headers


def test_estaticos_do_site_sao_lista_fechada(client):
    js = client.get("/site/site.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert "max-age" in js.headers["cache-control"]
    for path in ("/site/index.html", "/site/apoie.html", "/site/../app.py", "/site/%2e%2e/app.py", "/site/x.js"):
        assert client.get(path).status_code == 404
    assert client.get("/site/panel.js").status_code == 404  # o que e do painel fica em /app/static


def test_pagina_ausente_responde_404_em_vez_de_erro(client, monkeypatch, tmp_path):
    from heycode.relay import app as relay_app

    monkeypatch.setattr(relay_app, "SITE_DIR", tmp_path)
    assert client.get("/").status_code == 404 and client.get("/apoie").status_code == 404


@pytest.mark.parametrize("page", PAGES)
def test_html_sem_inline_sem_recurso_externo_e_acessivel(page):
    html = (SITE / page).read_text(encoding="utf-8")
    assert '<html lang="pt-BR"' in html and 'name="viewport"' in html and "<title>" in html
    assert re.findall(r"<script\b[^>]*>", html) == ['<script type="module" src="/site/site.js">']
    assert " style=" not in html and "<style" not in html and not re.search(r"\bon[a-z]+\s*=", html)
    assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", html)  # nenhum dominio externo
    assert html.count("<h1") == 1 and 'href="#conteudo"' in html and 'id="conteudo"' in html
    for href in re.findall(r'href="([^"#][^"]*)"', html):
        assert href.split("#")[0] in ("/", "/apoie", "/app", "/site/site.css"), href


@pytest.mark.parametrize("page", PAGES)
def test_textos_nao_vendem_e_toda_quantia_e_sugerida(page):
    html = (SITE / page).read_text(encoding="utf-8")
    words = text_of(html)
    for proibida in ("comprar", "compre", "assine", "assinar", "checkout", "garantia"):
        assert proibida not in words, proibida
    for price in re.findall(r'<p class="price">(.*?)</p>', html, re.S):
        assert "R$ 0" in price or "contribuição sugerida" in price, price
    assert "sem vínculo com a amazon" in words


def test_previa_da_comunidade_e_marcada_como_ilustrativa():
    words = text_of((SITE / "index.html").read_text(encoding="utf-8"))
    assert "em construção" in words and "exemplos ilustrativos" in words and "não existem" in words


def test_js_do_site_so_enfeita():
    js = (SITE / "site.js").read_text(encoding="utf-8")
    for proibido in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert proibido not in js, proibido
    for proibido in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "document.cookie"):
        assert proibido not in js, proibido


def test_niveis_do_site_batem_com_os_do_relay():
    from heycode.relay.plans import PLANS

    for page in PAGES:
        words = text_of((SITE / page).read_text(encoding="utf-8"))
        for plan in PLANS.values():
            assert f"{plan.installations} computadores" in words and f"{plan.shortcuts} comandos de voz" in words
            assert f"{plan.daily_quota} pedidos por dia" in words and f"r$ {plan.suggested}" in words
