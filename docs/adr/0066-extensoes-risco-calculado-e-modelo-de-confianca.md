# 0066. Extensões, risco calculado e modelo de confiança da lojinha

## Status

Proposto. Data: 2026-11-14.

## Contexto

A comunidade vai criar e publicar extensões que rodam no PC de outras pessoas e são disparadas por voz. Hoje o risco de um comando local é declarado por quem o cadastra, e um agente com shell pode declará-lo menor. `pedir_decisao` responde "sim" sozinho quando a política permite. O nome do projeto e do dono não pode ficar associado a artefato adulterado ou não aprovado, mesmo que a VM, o túnel ou a conta do GitHub sejam comprometidos. Spec: `docs/superpowers/specs/2026-11-14-heycode-ecossistema-de-extensoes.md`.

## Decisão

- O risco efetivo é calculado pelas capacidades, com piso; o declarado só sobe. Extensão nova ou alterada nasce desligada e liga só com confirmação fora do agente, atada ao hash da definição. Instalar e ativar nunca aceitam resposta de tools de agente.
- Quatro papéis de chave: raiz offline 2 de 3; oficial em token de hardware do dono; verificado por Sigstore keyless amarrado ao workflow do catálogo; revogação separada, que só desliga.
- Catálogo referencia commit completo e sha256. O índice tem versão monotônica, validade curta e hash do anterior, com o hash publicado no Rekor.
- A ponte verifica tudo antes de instalar e falha fechada para instalação. Os hooks dos agentes continuam falhando abertos.
- A VM hospeda arquivos assinados e repassa revogações assinadas; nunca guarda chave de assinatura.
- O mentor é um MCP separado, que não instala, não ativa, não aprova e não publica.
- Rejeitado: confiar no local de hospedagem; uma chave única para tudo; esteira com `pull_request_target` sobre código de fork; OpenCode hospedado.

## Consequências

- Invasão da VM forja avaliações ou atrasa revogação, mas não publica nada. Invasão da conta do GitHub forja selos "verificado", mas não "oficial".
- O dono passa a guardar dois tokens de hardware e uma cópia da raiz; perder a raiz exige reemitir a ponte.
- Comandos existentes com risco abaixo do piso sobem de nível na atualização; a pessoa é avisada no `heycode doctor`.
