# scripts/ops

Ferramentas de operação usadas para montar o staging (Playwright sobre o navegador do dono). Nada aqui guarda segredo: perfil do navegador, chaves SSH e segredos OAuth ficam fora do repositório.

- `browser_host.py`: Chromium visível com perfil persistente e porta CDP só em 127.0.0.1; o dono faz o login.
- `oracle_retry_create.py`: repete "Criar" da VM Always Free até haver capacidade.
- `alexa_fill_account_linking.py`: preenche o account linking lendo o segredo do servidor sem imprimi-lo.

Procedimentos e armadilhas: `docs/runbooks/infra-staging-oracle.md` e `docs/runbooks/console-alexa-skill-compartilhada.md`.
Requer `pip install playwright` e `playwright install chromium`. Feche o navegador ao terminar.
