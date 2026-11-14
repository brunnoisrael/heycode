# 0062. Preservar a permissão de execução do backup no pacote

## Status

Aceito. Data: 2026-11-14.

## Contexto

O serviço systemd executa `infra/vps/backup.sh` diretamente. O arquivo estava versionado sem permissão de execução, causando falha 203/EXEC após a implantação. A spec `docs/superpowers/specs/2026-11-13-ajuste-integracao-inicial.md` exige backup antes do deploy.

## Decisão

Versionar o script com o modo executável e verificar esse modo no índice Git. Pacotes devem preservar o modo registrado no Git; o serviço continua executando o mesmo script.

## Consequências

Arquivos gerados por `git archive` conservam a permissão. Cópias feitas por ferramentas que descartem permissões precisam restaurá-la na implantação; o teste evita regressão no modo registrado.
