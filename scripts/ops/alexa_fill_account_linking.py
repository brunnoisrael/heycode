"""Preenche o account linking da skill no console da Alexa. O segredo OAuth e lido do servidor por SSH e
digitado direto no campo: nunca e impresso nem gravado em arquivo.

Pre-requisito: browser_host.py rodando na pagina Account Linking, dono logado e o interruptor "Do you allow
users to create an account or link..." JA LIGADO com clique de mouse (clique via DOM nao atualiza a tela).
Uso: python scripts/ops/alexa_fill_account_linking.py --host deploy@IP --key CHAVE_SSH --api https://staging-api.exemplo.com
Nao clica em Save: confira a tela e salve voce mesmo."""

import argparse
import os
import subprocess

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--host", required=True, help="usuario@ip do servidor")
ap.add_argument("--key", required=True, help="chave SSH privada")
ap.add_argument("--api", required=True, help="URL base do relay, sem barra final")
ap.add_argument("--client-id", default="heycode-alexa")
ap.add_argument("--env-file", default="/opt/heycode/infra/vps/relay.env")
a = ap.parse_args()

secret = subprocess.run(
    ["ssh", "-i", a.key, "-o", "BatchMode=yes", a.host, f"grep '^OAUTH_CLIENT_SECRET=' {a.env_file} | cut -d= -f2-"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
assert len(secret) == 64, "segredo inesperado no servidor"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{os.environ.get('HEYCODE_CDP_PORT', '9222')}")
    pg = b.contexts[0].pages[0]
    assert not pg.locator("input[name=authorizationUrl]").is_disabled(), "ligue o interruptor antes"
    pg.locator("input[name=authorizationUrl]").fill(f"{a.api}/oauth/authorize")
    pg.locator("input[name=accessTokenUrl]").fill(f"{a.api}/oauth/token")
    pg.locator("input[name=clientId]").fill(a.client_id)
    pg.locator("input[name=clientSecret]").fill(secret)
    pg.locator("input[name=defaultTokenExpirationInSeconds]").fill("3600")
    pg.wait_for_timeout(800)
    names = ("authorizationUrl", "accessTokenUrl", "clientId", "defaultTokenExpirationInSeconds")
    print({n: pg.locator(f"input[name={n}]").input_value() for n in names})
    print("segredo preenchido:", len(pg.locator("input[name=clientSecret]").input_value()) == 64)
