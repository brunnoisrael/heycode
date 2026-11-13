# Plano de entrega: conexão estável e experiência de desenvolvimento

Spec aprovada: `docs/superpowers/specs/2026-11-12-roomcode-operacao-e-conversa.md`.

## 1. Inventário e conexão

- Identificar domínio, conta Cloudflare e configuração existente sem ler ou mostrar segredos; validar pré-requisitos e plano de rollback.
- Registrar ADR novo para endereço estável, execução e recuperação. Preparar instalação e diagnóstico idempotentes, com testes de falha, reconexão e reinício.
- Configurar túnel e DNS autorizados; atualizar Lambda uma vez; verificar acesso externo autenticado e Echo após reboot. Se não houver domínio ou acesso, documentar dependência e prosseguir com entregas locais independentes.

## 2. Projetos e execuções

- Registrar ADR para identidade e estados de projeto, execução e sessão. Implementar listagem paginada, frescor, seleção e contrato somente leitura.
- Adicionar testes de múltiplos agentes, nomes ambíguos, caminhos, paginação e estado antigo. Atualizar modelo e Lambda sem sobrescrever mudanças existentes no console.

## 3. Fluxo de trabalho por voz

- Especificar e implementar contexto de sessão e confirmação por operação/destino, com testes de corridas, expiração, repetição e reinício.
- Integrar criação de projeto, início de agente, instrução para sessão compatível e cancelamento direcionado; testar recusas e políticas existentes.
- Definir perfis de agentes somente após validar descoberta, persistência e limites dos adaptadores; não instalar ferramentas implicitamente.

## 4. Conversa e validação

- Ampliar frases, perguntas contextuais, paginação falada e respostas naturais; rever o prazo de perguntas abertas de maneira vinculada ao ID.
- Executar testes Python e Lambda e verificações no console Alexa. Ensaiar no Echo com o dono: iniciar projeto, listar, acompanhar, enviar contexto e cancelar; anotar comportamento e limites reais.
- Documentar suporte, instalação, operação e custos; registrar ADRs necessários e commits pequenos com trailer `Spec:`. Propor camada de linguagem opcional somente depois da fase determinística estar medida.
