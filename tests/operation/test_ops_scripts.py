"""Exercita ferramentas operacionais com browser e SSH simulados, sem ações externas."""

import runpy
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2] / "scripts" / "ops"


@pytest.fixture
def browser(monkeypatch):
    manager = MagicMock()
    api = types.ModuleType("playwright.sync_api")
    api.sync_playwright = lambda: manager
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)
    return manager.__enter__.return_value


def test_browser_host_usa_endereco_local(browser, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["browser_host.py"])
    monkeypatch.setattr("time.sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        runpy.run_path(str(ROOT / "browser_host.py"))
    args = browser.chromium.launch_persistent_context.call_args.kwargs["args"]
    assert "--remote-debugging-address=127.0.0.1" in args


@pytest.mark.parametrize(
    "text, url, sleeps",
    [
        ("Provisionando", "https://example.com", 0),
        ("capacidade insuficiente", "https://example.com", 1),
        ("erro inesperado", "https://example.com", 0),
        ("", "https://example.com/compute/instances/ocid1", 0),
    ],
)
def test_criacao_oracle_so_repete_se_faltar_capacidade(browser, monkeypatch, text, url, sleeps):
    page = browser.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    page.url = url
    page.frames = [MagicMock()]
    page.frames[0].locator.return_value.inner_text.return_value = text
    slept = []
    monkeypatch.setattr("time.sleep", slept.append)
    monkeypatch.setattr(sys, "argv", ["oracle_retry_create.py", "1", "1", "2", "3"])
    runpy.run_path(str(ROOT / "oracle_retry_create.py"))
    assert page.mouse.click.call_count == 1
    assert len(slept) == sleeps


def test_account_linking_preenche_sem_salvar(browser, monkeypatch, capsys):
    page = browser.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    page.locator.return_value.is_disabled.return_value = False
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: types.SimpleNamespace(stdout="x" * 64))
    monkeypatch.setattr(
        sys, "argv", ["alexa_fill_account_linking.py", "--host", "test", "--key", "key", "--api", "https://example.com"]
    )
    runpy.run_path(str(ROOT / "alexa_fill_account_linking.py"))
    assert page.locator.return_value.fill.call_count == 5
    assert "x" * 64 not in capsys.readouterr().out
