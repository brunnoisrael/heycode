# 0006. Servidor MCP central e fila de instruções

## Status

Aceito. Data: 2026-11-09.

## Contexto

A fase 3 da spec (`docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`, §8, §9 e §10) quer que qualquer
agente com cliente MCP (Claude Code, Codex) converse com a ponte e que o Claude já aberto receba a próxima instrução.
O spike (`docs/superpowers/specs/2026-11-09-spike-codex-aider.md`) mostrou que o Codex fala MCP e que o Aider não tem
MCP nem hook de aprovação.

## Decisão

- Um único servidor MCP, `roomcode` (SDK oficial, FastMCP, HTTP streamable), montado em `/mcp` na mesma app FastAPI.
  Usa o mesmo `Store` e o mesmo `decidir`, então modos, PIN e `/decide` valem igual para hooks e MCP.
- Ferramentas: `registrar_status`, `pedir_decisao`, `reportar_fim`, `buscar_instrucao`. `pedir_decisao` cria uma
  aprovação (`tool="pedir_decisao"`), responde `sim` com `auto` no modo auto e devolve `sem_resposta` após
  `APPROVAL_WAIT`, sem travar o agente.
- O store ganha a fila `instructions` (`add_instruction`/`pop_instruction`): FIFO, entrega única, escopo por agente e
  projeto (sem projeto vale para qualquer um do agente). A API expõe `POST /instruction` e `POST /instruction/next`.
- Autenticação do `/mcp` por middleware ASGI: `Authorization: Bearer` ou `x-secret`, comparação em tempo constante.
  Como há credencial, a proteção contra DNS rebinding do SDK fica desligada.
- O gerenciador de sessão do SDK roda no lifespan da app (o `Mount` não executa o lifespan do sub-app); o sub-app é
  recriado a cada subida, pois o gerenciador só roda uma vez por instância.
- Por `bridge/mcp` fazer sombra ao pacote `mcp` do SDK quando `bridge/` está no `sys.path`, `server.py` carrega o
  módulo por caminho de arquivo, depois de importar o SDK sem `bridge/` no caminho.
- Alternativas rejeitadas: um MCP por agente (duplica política, estado e autenticação) e só hooks (Codex e agentes
  sem hook ficam de fora, e o hook não oferece ferramentas para o agente chamar).
- O Aider fica fora do MCP: sem suporte a MCP (spike), só entra pelo supervisor (fase 4).

## Consequências

- Um ponto único de política e estado para todos os agentes; novo agente com MCP só precisa registrar o servidor.
- A instrução para agente aberto chega ao Claude pelo hook de Stop e, ao Codex, só quando ele chama `buscar_instrucao`.
- Dependência nova (`mcp`) e um truque de carga de módulo por causa do nome do pacote; mitigado por teste que sobe o
  app e usa o cliente MCP real.
- `/mcp` na mesma porta expõe mais superfície: a credencial é obrigatória e a ponte já deve ficar atrás de túnel
  autenticado.
