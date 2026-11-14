"""Abre um Chromium visivel com perfil persistente e porta de depuracao local, para o dono fazer login
(senha e 2FA so na janela dele) e o agente continuar a mesma sessao via CDP.

Uso: python scripts/ops/browser_host.py [URL]
Variaveis: HEYCODE_BROWSER_PROFILE (pasta do perfil, FORA de qualquer repositorio), HEYCODE_CDP_PORT (9222).
A porta escuta so em 127.0.0.1. Feche o navegador ao terminar: com a porta aberta, qualquer programa local
controla a sessao logada."""

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = os.environ.get("HEYCODE_BROWSER_PROFILE") or str(Path.home() / ".heycode-tools" / "chromium-profile")
PORT = int(os.environ.get("HEYCODE_CDP_PORT", "9222"))
URL = sys.argv[1] if len(sys.argv) > 1 else "about:blank"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE,
        headless=False,
        viewport=None,
        args=[f"--remote-debugging-port={PORT}", "--remote-debugging-address=127.0.0.1", "--start-maximized"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL)
    print("pronto", flush=True)
    while True:
        time.sleep(3600)
