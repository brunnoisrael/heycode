"""Repete o clique em "Criar" do assistente de instancia da Oracle ate conseguir: em Sao Paulo as formas
Always Free devolvem "capacidade insuficiente" com frequencia. Para ao primeiro sucesso (nunca cria duas)
ou no limite de tentativas.

Pre-requisito: browser_host.py rodando, dono logado e o assistente de criacao preenchido e na ultima etapa.
Uso: python scripts/ops/oracle_retry_create.py [TENTATIVAS=20] [PAUSA_S=75] [X=1191] [Y=633]
(X e Y: posicao do botao Criar na sua janela; confira com uma captura de tela)."""

import os
import sys
import time

from playwright.sync_api import sync_playwright

MAX_ATTEMPTS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
PAUSE = int(sys.argv[2]) if len(sys.argv) > 2 else 75
X = int(sys.argv[3]) if len(sys.argv) > 3 else 1191
Y = int(sys.argv[4]) if len(sys.argv) > 4 else 633
CDP = f"http://127.0.0.1:{os.environ.get('HEYCODE_CDP_PORT', '9222')}"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    pg = b.contexts[0].pages[0]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        pg.mouse.click(X, Y)  # botao Criar
        pg.wait_for_timeout(18000)
        body = " ".join(fr.locator("body").inner_text() for fr in pg.frames)  # o assistente usa iframes
        if "/compute/instances/ocid1" in pg.url or "PROVISIONING" in body.upper() or "Provisionando" in body:
            print(f"SUCESSO na tentativa {attempt}: {pg.url}", flush=True)
            break
        low = body.lower()
        if "capacidade insuficiente" in low or "out of host capacity" in low:
            print(f"tentativa {attempt}: sem capacidade", flush=True)
        else:
            print(f"tentativa {attempt}: resposta inesperada: {body[:300]!r}", flush=True)
            break
        time.sleep(PAUSE)
    else:
        print("limite de tentativas atingido", flush=True)
