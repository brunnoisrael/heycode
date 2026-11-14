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
| Redirecionamento aberto ou código OAuth reaproveitado | `redirect_uri` de lista exata, código de uso único atado a cliente e redirect | `test_redirect_uri_fora_da_lista_nao_redireciona`, `test_codigo_de_uso_unico`, `test_codigo_nao_vale_com_outro_redirect_uri` |
| Refresh token roubado e reusado | rotação; reuso revoga a família | `test_reuso_de_refresh_revoga_a_familia_inteira` |
| Requisição forjada fingindo ser a Alexa | URL, certificado, cadeia, assinatura, janela de 150 s e applicationId | `test_assinatura_sobre_outro_corpo_recusada`, `test_cadeia_nao_confiavel_recusada`, `test_application_id_de_outra_skill_recusado` |
| SSRF pelo cabeçalho do certificado | URL validada antes de qualquer rede | `test_url_do_certificado_invalida_recusada_sem_buscar_nada` |
| Dispositivo novo aciona a máquina | nada executa até a conta dona aprovar; pendentes com limite | `test_dispositivo_novo_nao_executa_e_vira_solicitacao_pendente`, `test_solicitacoes_pendentes_tem_limite` |
| Conta B aprova ou usa dispositivo de A | tudo filtrado por conta | `test_so_a_conta_dona_aprova_o_dispositivo`, `test_dispositivo_aprovado_para_a_nao_vale_para_b` |
| Roteamento ambíguo entre máquinas | nunca adivinha: pede escolha; padrão só da própria conta | `test_varias_instalacoes_sem_padrao_pedem_escolha_e_com_padrao_roteiam`, `test_instalacao_padrao_de_outra_conta_recusada` |
| Dados que sobram depois da exclusão (LGPD) | exclusão apaga tudo e derruba conexões e tokens | `test_apagar_conta_remove_tudo_e_invalida_tokens`, `test_apagar_conta_derruba_a_conexao_ativa` |
| Relay (ou bug) pede à máquina uma rota que a voz nunca usou | executor local com lista fechada de (método, caminho) e consulta restrita; nada fora dela toca a ponte | `test_qualquer_rota_fora_da_lista_e_recusada_sem_tocar_a_ponte`, `test_consulta_com_chave_nao_permitida_recusada`, `test_lista_permitida_e_exatamente_a_do_lambda` |
| Modo `auto` ligado só por voz no modo compartilhado | `mode: auto` só passa com `auto_allowed` ligado no computador (`heycode relay-auto on`) | `test_auto_so_passa_se_ligado_no_computador`, `test_auto_com_variacao_de_escrita_tambem_e_barrado`, `test_auto_por_voz_e_barrado_ate_o_dono_liberar_no_computador` |
| Segredo de controle da ponte vaza para o relay | o segredo só é lido no computador; o relay envia método e caminho lógicos | `test_segredo_nunca_aparece_no_resultado`, `test_status_vai_da_alexa_ate_a_ponte_e_volta_com_a_fala` |
| Confirmação antiga vale para outro destino depois de trocar de projeto | atributos de sessão `block_prior_confirmation` e `free_answer` herdados do Lambda | `test_confirmacao_antiga_e_rejeitada_depois_de_trocar_de_projeto`, `test_selecionar_projeto_guarda_na_sessao_e_bloqueia_confirmacao_antiga` |
| Aprovação sem ler o pedido | decisão atada ao `approval_id` lido em voz alta na mesma sessão | `test_aprovar_sem_pendencia_lida_nao_chama_o_computador`, `test_fluxo_de_aprovacao_usa_a_sessao_da_alexa_e_o_pedido_lido_em_voz_alta` |
| Cota estourada por intents que chamam a máquina | cada chamada à ponte conta na cota diária | `test_cota_diaria_conta_pedidos_e_zera_no_dia_seguinte` |
| XSS no painel rouba a sessão | cookie `HttpOnly` (JS não lê), CSP `default-src 'none'` sem inline nem eval, dados só por `textContent`, nada de token no `localStorage` | `test_cookie_e_httponly_samesite_e_invisivel_ao_javascript`, `test_html_nao_tem_script_inline_estilo_inline_nem_recurso_externo`, `test_js_nunca_monta_html_com_dados_nem_avalia_texto`, `test_comando_novo_e_html_malicioso_aparece_como_texto` |
| CSRF contra o painel | `SameSite=Strict` + token ligado à sessão no cabeçalho em toda escrita por cookie | `test_escrita_com_cookie_sem_csrf_ou_com_csrf_errado_e_recusada`, `test_csrf_de_outra_sessao_nao_vale`, `test_escrita_sem_csrf_e_recusada_pelo_servidor` |
| Clickjacking do painel | `frame-ancestors 'none'` e `X-Frame-Options: DENY` | `test_pagina_do_painel_e_servida_com_csp_rigida` |
| Rastro vaza conteúdo, PIN ou dado de outra conta | linhas só com metadados, filtradas por conta; detalhe vem do computador, mascarado | `test_nenhum_conteudo_vai_para_o_rastro`, `test_conta_b_nunca_ve_o_rastro_da_conta_a`, `test_devolve_aprovacoes_e_execucoes_recentes_com_segredos_mascarados`, `test_nao_vaza_a_resposta_livre_nem_o_texto_da_pergunta` |
| Atalho executa sem confirmação ou dispara o comando errado | atalho só monta o ditado, que exige "Confirma?"; empate e baixa semelhança são recusados | `test_atalho_vira_ditado_com_confirmacao_e_nao_executa_sozinho`, `test_empate_e_recusado`, `test_atalho_cadastrado_no_painel_vira_ditado_com_confirmacao_na_ponte` |
| Conta B usa ou apaga o atalho de A | tudo filtrado por conta | `test_conta_b_nao_ve_edita_nem_apaga_o_atalho_de_a`, `test_conta_b_nao_renomeia_computador_de_outra_conta` |
| Relay, painel ou Alexa criam ou editam um script/webhook | definições só em `commands.json`, escrito pelo CLI local; o executor não tem rota para criar, editar, ligar ou remover; remoto só desliga | `test_o_executor_nao_alcanca_rotas_de_escrita_do_registro`, `test_nao_existe_rota_para_ligar_nem_editar`, `test_qualquer_rota_fora_da_lista_e_recusada_sem_tocar_a_ponte` |
| Fala vira argumento, URL ou corpo (injeção) | a fala só escolhe o comando; argv, URL e corpo são exatamente os cadastrados; sem shell | `test_a_fala_nunca_chega_ao_comando`, `test_sem_shell_o_argumento_e_literal`, `test_pergunta_com_texto_malicioso_nao_vira_argumento` |
| Comando perigoso roda sem aval | níveis `confirmar` e `pin`; pendência única de 120 s atada ao hash da definição; PIN verificado na ponte com bloqueio por tentativas | `test_confirmar_pergunta_antes_e_so_roda_depois`, `test_pin_exige_o_pin_verificado_pela_ponte`, `test_pin_exige_o_pin_da_ponte_com_bloqueio_por_tentativas`, `test_definicao_alterada_entre_pedir_e_confirmar_invalida`, `test_pendencia_expira_em_120s` |
| Webhook que muda estado marcado como leitura, ou que desvia o destino | POST nunca é `leitura`; só `https` (ou localhost); sem seguir redirecionamento | `test_webhook_invalido_e_recusado`, `test_webhook_nao_segue_redirecionamento` |
| Token de webhook ou segredo no relay, no rastro ou na fala | cabeçalho por referência `env:`, valor lido só no computador; resumo sem argv/URL/cabeçalhos; saída mascarada e fora do histórico | `test_webhook_confirmar_envia_corpo_fixo_e_cabecalho_resolvido`, `test_resumo_nunca_traz_argv_url_cabecalho_ou_corpo`, `test_webhook_usa_segredo_do_config_env_local_e_nunca_o_devolve`, `test_saida_com_segredo_sai_mascarada_e_limitada` |
| Script travado, em laço ou várias execuções em paralelo | timeout que mata a árvore, uma execução por vez, intervalo de 3 s por comando | `test_timeout_mata_o_processo_e_avisa`, `test_um_comando_por_vez_e_intervalo_minimo_de_3s` |
| Registro corrompido ou adulterado vira execução | validação estrita (campos desconhecidos recusados); CLI nunca sobrescreve registro corrompido | `test_versao_e_campos_desconhecidos_sao_recusados`, `test_registro_corrompido_nao_e_sobrescrito`, `test_registro_invalido_vira_fala_clara_sem_executar` |
| Relay comprometido forja pedidos à máquina | **risco aceito no MVP** (quadros do relay sem assinatura, ADR 0038); mitigação na P6 | n/a |

## Riscos aceitos e lacunas

- Relay comprometido vê metadados (quem, quando, qual projeto) e texto já mascarado; não vê a chave privada nem consegue assinar por uma instalação.
- Mascaramento por padrões não pega todo segredo (heurístico); permanece a regra de nunca ler saída em voz sem resumo.
- Perda da chave privada exige novo pareamento.
- A persistência de contas, vínculos e revogações no relay (Postgres, retenção, exclusão LGPD) e o endpoint HTTPS da skill pertencem à P3 e à P4; este documento será estendido por esses ADRs (G10).
- **PIN em trânsito (modo compartilhado):** o PIN falado passa pelo relay até a máquina, onde a ponte o verifica; o relay não o registra nem guarda (a resposta é entregue e esquecida), mas um relay comprometido poderia vê-lo. Risco aceito e documentado; mitigação futura: PIN com desafio.
- **Risco aceito dos comandos locais:** quem escolhe `risco leitura` aceita que o comando rode assim que a Alexa reconhecer o nome (o CLI avisa); o reconhecimento de fala pode errar, e só a recusa de empate e a semelhança mínima protegem esse nível. Script mal escrito é responsabilidade de quem o cadastra.
