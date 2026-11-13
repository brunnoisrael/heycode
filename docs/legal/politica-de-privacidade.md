# Política de privacidade do HeyCode (RASCUNHO)

> **Rascunho técnico, sem validade jurídica.** Precisa de revisão do dono (e, de preferência, de um advogado) antes de publicar. Os e-mails citados só passam a existir quando o dono os ativar.

Atualizado em: 2026-11-13 (rascunho).

## Quem somos

O HeyCode é operado por **[NOME DO CONTROLADOR A DEFINIR PELO DONO]**. Contato do encarregado e das solicitações de titulares: `privacy@heycode.dev.br` (a ativar).

## Que dados tratamos e para quê

| Dado | Finalidade | Base legal (LGPD, a confirmar) |
|---|---|---|
| E-mail e hash da senha (Argon2id) | Criar e acessar sua conta | Execução de contrato |
| Chave pública, nome e último acesso de cada computador pareado | Encaminhar pedidos ao computador certo | Execução de contrato |
| Identificador do dispositivo Alexa e estado da autorização | Autorizar quais dispositivos podem acionar seu computador | Execução de contrato |
| Tokens de acesso e renovação (somente o hash) | Manter a conta vinculada à Alexa | Execução de contrato |
| Contagem diária de pedidos | Aplicar cotas e evitar abuso | Legítimo interesse |

## O que **não** guardamos

O relay **não** guarda o conteúdo dos seus pedidos nem as saídas dos agentes: eles passam pela memória do serviço para chegar ao seu computador e à resposta, e os resultados ficam transitoriamente em memória (até 1.000 pedidos recentes, perdidos ao reiniciar). Segredos conhecidos (chaves, tokens) são mascarados no seu computador antes de sair dele. Seu código-fonte e seus arquivos nunca são enviados.

## Compartilhamento

A Amazon (Alexa) processa sua voz conforme a política da própria Amazon; o HeyCode recebe só o texto da requisição. A plataforma de hospedagem **[A DEFINIR]** armazena o banco do relay. Não vendemos dados.

## Retenção

Conta e dados associados: enquanto a conta existir. Contagem diária de uso: 30 dias (a rotina de limpeza ainda será implementada antes do beta aberto). Tokens de acesso: 1 hora; de renovação: 30 dias, ou até a revogação. Ao excluir a conta, tudo acima é apagado imediatamente.

## Seus direitos

Acesso, correção, exclusão, portabilidade e revogação de consentimento. **Exclusão:** `DELETE /v1/account` (ou pelo aplicativo), com confirmação da senha. Demais pedidos: `privacy@heycode.dev.br`.

## Segurança

Senhas em Argon2id, tokens só como hash, tráfego por TLS, isolamento entre contas testado automaticamente. Incidentes serão comunicados conforme a LGPD.
