# 0021. Operação do túnel nomeado

## Status

Aceito. Data: 2026-11-12.

## Contexto

A spec `docs/superpowers/specs/2026-11-12-roomcode-operacao-e-conversa.md` pede endereço estável e recuperação após reinício. O túnel rápido atual tem endereço efêmero; o domínio `heycode.dev.br` foi solicitado, mas sua disponibilidade, delegação e configuração Cloudflare ainda precisam ser confirmadas.

## Decisão

Usar túnel nomeado com um hostname sob domínio do dono. O provisionamento de conta, DNS e credenciais Cloudflare é etapa separada; nenhum script presume que o domínio já está ativo ou altera uma configuração existente sem revisão. A ponte continua em loopback. Uma tarefa agendada dedicada inicia o `cloudflared` com um arquivo de configuração existente no logon, sem token na linha de comando; falhas podem reiniciar a tarefa. O instalador apresenta prévia por padrão e recusa substituir uma tarefa divergente.

O diagnóstico distingue ponte local, estado da tarefa e resposta HTTPS externa. A consulta autenticada é opcional, usa segredo de controle do ambiente e não mostra corpo nem credencial. Nenhuma dessas verificações comprova reconhecimento de voz ou funcionamento do Echo.

## Consequências

Um hostname estável evita mudar a Lambda a cada reconexão. A disponibilidade depende de logon, conectividade, domínio, DNS, Cloudflare, Alexa e PC; não há garantia de disponibilidade. Credenciais do conector ficam no arquivo configurado pelo dono e precisam de proteção e backup adequados. A transição e o retorno ao túnel anterior exigem verificar a Lambda e o DNS; o instalador não interrompe o túnel rápido existente.
