# Política de segurança

O HeyCode controla agentes de código com acesso a arquivos e comandos do computador de quem o usa. Falhas de segurança importam.

## Como reportar

**Não abra issue pública para vulnerabilidades.** Use o relato privado de vulnerabilidades do GitHub neste repositório (aba Security → Report a vulnerability). Inclua o que você viu, como reproduzir e o impacto, sem segredos reais.

Contato por e-mail (`security@heycode.dev.br`) só será anunciado aqui quando o endereço estiver ativo.

## O que esperar

Confirmamos o recebimento e damos retorno sobre a avaliação. O projeto ainda é jovem e mantido por poucas pessoas, então não há prazo contratual de correção.

## Escopo e limites conhecidos

- O modo `auto` aprova tudo, sem piso de segurança, sem PIN e sem expiração (ADR 0002). É comportamento documentado, não vulnerabilidade; para uso compartilhado ele será redefinido por ADR.
- A allowlist do dono e do dispositivo na Lambda é a mitigação atual do modo `auto`.
- Conteúdo baixado é dado não confiável: nunca execute scripts de dentro dele.
