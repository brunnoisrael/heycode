# Plano: respostas livres por voz

Spec: `docs/superpowers/specs/2026-11-12-respostas-livres-por-voz.md`.

1. Registrar a decisão de arquitetura e o contrato de expiração e confirmação.
2. Implementar fila de perguntas, resposta atômica e ferramenta MCP, com testes de concorrência, prazo e reinício.
3. Implementar preparação e confirmação da resposta pela ponte, sem interferir nas aprovações ou em outras confirmações.
4. Acrescentar diálogo da Alexa, modelo de interação e testes dos turnos e casos de erro.
5. Executar as suítes Python e Lambda; registrar os limites de verificação no console Alexa. Criar commit local com trailer da spec.
