# Plano: integração inicial

Status: em execução; spec correspondente aprovada pelo dono nesta conversa.

1. Aprovar a spec `docs/superpowers/specs/2026-11-13-ajuste-integracao-inicial.md` e registrar ADR novo de governança.
2. Definir mecanismo que limite a exceção ao commit de integração indicado e escreva testes que comprovem a manutenção do teto nos commits posteriores.
3. Validar cobertura real das ferramentas operacionais sem acionar serviços externos; manter o piso e as varreduras de segurança.
4. Executar a matriz de testes, analisar todas as falhas e obter um commit com assinatura verificada para a integração.
5. Depois da integração na `main` remota, criar backup, publicar exatamente esse commit, registrar `VERSION` e testar saúde e acesso.
6. Remover o mecanismo temporário de integração, mantendo o G12 para o trabalho futuro.
