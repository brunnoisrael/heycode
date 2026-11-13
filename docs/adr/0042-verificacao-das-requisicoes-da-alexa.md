# 0042. Verificação das requisições da Alexa no relay

## Status

Aceito. Data: 2026-11-13.

## Contexto

No endpoint HTTPS próprio (ADR 0033) a Lambda deixa de validar as requisições; sem validação qualquer pessoa na internet poderia se passar pela Amazon. A certificação da skill também exige. Spec: `docs/superpowers/specs/2026-11-13-heycode-skill-compartilhada.md` §4.

## Decisão

O relay valida toda requisição em `POST /v1/alexa` antes de qualquer outra coisa: URL do certificado (`https`, `s3.amazonaws.com`, caminho `/echo.api/`, porta 443), certificado dentro da validade com `echo-api.amazon.com` nos nomes alternativos e cadeia validada contra raízes confiáveis, assinatura SHA-256/RSA sobre o corpo exato, `timestamp` a no máximo 150 s e `applicationId` igual a `ALEXA_SKILL_ID`. Falha é 400 e nada é executado. O certificado baixado é só analisado, nunca executado, e fica em cache por URL. Rejeitado: confiar no `applicationId` sozinho (forjável) e validar só em um proxy externo (mais uma peça sem ganho).

## Consequências

Só a Amazon fala com o endpoint. Custo: uma busca de rede ao primeiro uso de cada certificado e a necessidade de manter raízes confiáveis atualizadas.
