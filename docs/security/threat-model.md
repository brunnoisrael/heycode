# Modelo de ameaça do HeyCode multiusuário

Escopo: relay, instalações pareadas e modo `auto` multiusuário. O caminho do dono (Lambda com allowlist, segredo compartilhado, ADR 0002) fica fora e não muda. Spec: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md`. ADRs 0029 a 0034.

## Ativos

Código e arquivos do usuário; credenciais locais; capacidade de executar comandos na máquina; contas e chaves públicas no relay; histórico de execuções.

## Fronteiras de confiança

voz (Alexa) → skill → relay → componente local → agente. Cada salto autentica o seguinte; o relay **não é confiável para ver segredo** (mascaramento na máquina antes de sair) e **não é confiável para forjar identidade** (envelopes assinados pela instalação).

## Atores

Outra conta de usuário; operador ou invasor do relay; dispositivo de voz roubado ou de terceiro; agente enganado por conteúdo baixado; observador da rede.

## Ameaças, controles e testes

| Ameaça | Controle | Teste |
|---|---|---|
| Conta A aciona a máquina de B | roteamento por (conta, instalação) vindos da autenticação; payload ignorado | `test_conta_a_nao_aciona_instalacao_de_b`, `test_installation_id_forjado_no_payload_ignorado`, `test_envelope_com_installation_id_diferente_do_autenticado_recusado` |
| Instalação reivindicada por duas contas | registro recusa outro dono | `test_instalacao_nao_pode_ser_registrada_por_duas_contas` |
| ID de confirmação reaproveitado ou usado em outro destino | confirmação atada a (operação, destino, instalação), uso único, 5 min | `test_confirmacao_nao_vale_para_outro_destino`, `test_confirmacao_nao_reutilizavel`, `test_confirmacao_expira_e_nao_fica_pendente_para_sempre` |
| Replay de envelope | janela de `id` de 10 min e `ts` dentro de ±2 min | `test_replay_recusado`, `test_relogio_fora_de_2min_recusado`, `test_relogio_dentro_de_2min_aceito` |
| Envelope adulterado | assinatura Ed25519 sobre JSON canônico | `test_payload_adulterado_recusado`, `test_installation_id_adulterado_recusado` |
| Chave revogada ou substituída | registro de revogação; rotação assinada pela chave antiga | `test_chave_revogada_recusada`, `test_rotacao_assinada_pela_chave_antiga`, `test_rotacao_assinada_por_chave_alheia_recusada` |
| Código de pareamento reaproveitado, expirado ou adivinhado | uso único, 5 min, bloqueio após 5 falhas por origem | `test_codigo_uso_unico`, `test_codigo_expira_em_5min`, `test_limite_de_5_tentativas_bloqueia_codigo` |
| Pareamento confirmado em um lado só, ou por conta errada | vínculo exige conta e máquina | `test_confirmacao_so_de_um_lado_nao_vincula`, `test_codigo_de_outra_conta_nao_vincula` |
| `auto` ligado por outra conta, dispositivo alheio ou só por voz na primeira vez | dono, dispositivo associado e confirmação no computador | `test_auto_nao_liga_por_outra_conta`, `test_auto_nao_liga_por_dispositivo_nao_associado`, `test_auto_so_liga_com_confirmacao_no_computador`, `test_dispositivo_revogado_nao_liga_auto` |
| Segredo subindo ao relay | mascaramento antes de assinar | `test_segredo_mascarado_antes_de_sair` |
| Relay fora do ar trava o agente | envio falha aberto; confirmações expiram | `test_relay_fora_nao_trava_agente` |

## Ameaças do relay (P3)

| Ameaça | Controle | Teste |
|---|---|---|
| Conta A pede algo à instalação de B pela skill | instalação resolvida só entre as da conta; resposta idêntica para inexistente e alheia | `test_skill_de_a_nao_alcanca_instalacao_de_b` |
| Conta B lê o resultado de A | resultado só para a conta que fez o pedido | `test_resultado_de_a_nao_e_lido_por_b` |
| Máquina de B resolve pedido de A | só a instalação que recebeu o pedido o resolve | `test_maquina_nao_resolve_pedido_de_outra_conta` |
| Handshake forjado, repetido ou de instalação revogada | assinatura, anti-replay e revogação em todo envelope | `test_assinatura_invalida_recusada`, `test_replay_do_handshake_recusado`, `test_instalacao_revogada_nao_conecta` |
| Revogação não derruba quem já está conectado | `DELETE` fecha a conexão | `test_revogar_derruba_a_conexao_ativa` |
| Enumeração de contas e força bruta no login | resposta única e limite de 10 tentativas/min por origem | `test_senha_errada_e_email_inexistente_dao_o_mesmo_erro`, `test_login_tem_limite_de_taxa_por_origem` |
| Custo descontrolado | cota diária por conta | `test_cota_diaria_conta_pedidos_e_zera_no_dia_seguinte` |
| Segredo em log do relay | o relay não registra corpo de pedidos nem senhas | `test_logs_do_relay_nao_contem_segredo` |
| Relay comprometido forja pedidos à máquina | **risco aceito no MVP** (quadros do relay sem assinatura, ADR 0038); mitigação na P6 | n/a |

## Riscos aceitos e lacunas

- Relay comprometido vê metadados (quem, quando, qual projeto) e texto já mascarado; não vê a chave privada nem consegue assinar por uma instalação.
- Mascaramento por padrões não pega todo segredo (heurístico); permanece a regra de nunca ler saída em voz sem resumo.
- Perda da chave privada exige novo pareamento.
- A persistência de contas, vínculos e revogações no relay (Postgres, retenção, exclusão LGPD) e o endpoint HTTPS da skill pertencem à P3 e à P4; este documento será estendido por esses ADRs (G10).
