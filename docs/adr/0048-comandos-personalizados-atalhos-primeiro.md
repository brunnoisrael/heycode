# 0048. Comandos personalizados: atalhos primeiro, scripts locais depois

## Status

Aceito. Data: 2026-11-13.

## Contexto

A pessoa quer plugar comandos novos que a Alexa executa pelo middleware. Um comando que executa coisas no computador é o ponto mais perigoso do produto: um relay comprometido não pode criar execução. Spec: `docs/superpowers/specs/2026-11-13-heycode-painel-web-rastro-e-comandos.md` §5 e §6.

## Decisão

- **Fase A (esta entrega): atalhos para agentes.** O relay guarda nome, apelidos, agente, projeto e um texto fixo. A Alexa os alcança por uma intent genérica, `RunCommandIntent`, com slot livre `comando`; o relay normaliza e casa por nome/apelido, recusando empate e ausência, e monta o mesmo `POST /dictation` do pedido por voz. A execução só acontece após o "Confirma?" por voz. Como o relay já podia pedir ditados (sempre com confirmação), o atalho não amplia seu poder e dispensa ativação no computador.
- **Fase B (futura, só desenho): scripts locais.** A definição vive no computador (`commands.json`), nunca no relay; criar ou alterar exige comando local; níveis de risco `leitura`, `confirmar` e `pin`; execução sem shell, com argumentos fixos, diretório e tempo máximo.
- **Fase C (futura): webhooks** apenas para destinos cadastrados no computador.
- O modelo de interação ganha `RunCommandIntent` de forma aditiva.
- Rejeitado: o relay definir scripts que o computador executa (um relay comprometido ganharia execução) e variáveis livres nos atalhos nesta fase (injeção de texto no ditado).

## Consequências

Entrega útil e segura em pouco tempo. Custo: atalhos não executam scripts ainda; a intent genérica depende do reconhecimento de fala livre, mitigado pela confirmação.
