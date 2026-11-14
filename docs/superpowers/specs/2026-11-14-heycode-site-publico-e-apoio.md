# HeyCode: site público, identidade e planos de apoio

Data: 2026-11-14. Status: Aprovada pelo dono em 2026-11-14 ("manda bala no A [...] vamos colocar planos mas dizer que é meio que contribuição", depois de o agente apresentar as quatro frentes, a ordem e a opção A: planos e limites funcionando, sem cobrança, com lista de interesse; registrado pelo agente, que tomou as decisões de desenho abaixo por delegação).

Base: spec do painel web (2026-11-13), spec de rotas, borda e painel (2026-11-14), `docs/ROADMAP-HEYCODE.md` (M4), `docs/REVISAO-ADVERSARIAL-2026-11-13.md`. ADR: 0059.

## 1. Intenção e porquê

O dono quer que o HeyCode deixe de ser só um painel e vire **um site com identidade forte**, com uma **tela de planos** que dê mais para quem ajuda o projeto. O dono não pode ter empresa, então os planos são apresentados como **contribuição voluntária**: ninguém compra uma assinatura; quem apoia ganha, como agradecimento, limites maiores. A comunidade de pacotes e a carga automática ficam para specs próprias; aqui entram só como prévia na página inicial.

## 2. Objetivos, não objetivos e antiobjetivos

Objetivos:

- Uma página inicial pública que explique em segundos o que o HeyCode faz, com marca própria e uma demonstração animada da conversa por voz.
- Uma página "Apoie" com três níveis e o que cada um recebe.
- Limites por nível valendo de verdade no relay (computadores, atalhos, pedidos por dia).
- O usuário logado vê seu nível, o uso de cada limite e pode dizer "quero apoiar"; o dono consegue medir esse interesse e conceder um nível manualmente.

Não objetivos: cobrança, checkout, provedor de pagamento, nota fiscal; catálogo da comunidade; recursos novos da Alexa (avisos proativos, resumo matinal), que aparecem só como "em construção".

Antiobjetivos:

- Parecer loja ou empresa: nada de "comprar" ou "assinar", e nenhuma quantia sem a palavra "sugerida".
- Prometer o que não existe: recurso não construído é marcado como "em construção"; a prévia da comunidade é marcada como ilustrativa.
- Coletar e-mail de visitante anônimo (vetor de spam e obrigação de LGPD): o interesse só é registrado por quem tem conta.
- Sugerir vínculo com a Amazon: o rodapé diz que o projeto é independente.

## 3. Abordagens

Site:

- **A. Páginas estáticas servidas pelo relay, sem build (escolhida).** Mesma CSP rígida do painel, lista fechada de arquivos, nada de terceiros. A Cloudflare na frente (ADR 0058) faz cache do que é público.
- B. Site separado em hospedagem estática. Mais uma peça para publicar e manter, e a conta continuaria no relay. Fica como evolução se o tráfego pedir.
- C. Framework com build. Peso de cadeia de suprimentos e de CI para duas páginas. Rejeitada.

Níveis:

- **A. Limites por nível no relay, nível concedido à mão pelo dono (escolhida).** Funciona hoje, sem provedor de pagamento, e mede interesse antes de qualquer cobrança (a revisão adversarial apontou demanda não validada).
- B. Cobrança integrada. Exige conta em provedor e situação fiscal que o dono não tem agora. Fora.

## 4. Identidade

- **Ideia central:** o anel que escuta e o prompt que executa. A marca é um anel (referência ao anel de luz dos aparelhos de voz) com um sinal de prompt dentro.
- **Paleta:** fundo quase preto azulado; verde-água do painel como cor principal; violeta como segunda luz; âmbar só para destaque pontual. O site é sempre escuro (palco); o painel continua com tema claro, escuro ou automático.
- **Tipografia:** pilha do sistema, títulos pesados e apertados; mono para tudo que é fala ou comando.
- **Textura e movimento:** aurora em gradiente, grão sutil, malha fina; anel que pulsa, fala que é "digitada" e terminal que responde. Tudo respeita `prefers-reduced-motion`.
- **Voz do texto:** direta, em português, sem jargão de marketing.

## 5. Páginas

Servidas pelo relay, com a CSP do painel:

- `/` (início): navegação; chamada principal com a demonstração (anel, fala e terminal em ciclo); faixa "funciona com"; como funciona em três passos; grade de recursos reais; segurança; prévia da comunidade (ilustrativa); níveis de apoio; rodapé com aviso de independência.
- `/apoie`: por que apoiar, os três níveis lado a lado, perguntas frequentes (inclui "isso é uma assinatura?": não).
- Arquivos novos em `src/heycode/relay/site/`; `site.css` e `site.js` entram na mesma lista fechada de estáticos.
- O painel ganha a tela **Plano e apoio** (`#/plano`) e a marca nova.

## 6. Níveis e limites

| Nível | Contribuição sugerida | Computadores | Atalhos | Pedidos por dia |
|---|---|---|---|---|
| Livre | R$ 0 | 2 | 30 | 200 (ou o configurado no relay) |
| Apoiador | R$ 15 por mês | 4 | 100 | 1000 |
| Patrono | R$ 45 por mês | 8 | 300 | 3000 |

- Os valores são sugestões exibidas com a palavra "sugerida"; o relay não cobra nem registra pagamento.
- `GET /v1/plan`: nível, interesse registrado, limites, uso atual e a lista de níveis.
- `PUT /v1/plan/interest`: registra ou retira o interesse em um nível (só conta logada; entra no rastro).
- Concessão: `python -m heycode.relay.grant set EMAIL NIVEL` no servidor; `python -m heycode.relay.grant interest` lista quem pediu. Não existe rota HTTP que mude o nível.
- Reduzir o nível não apaga nada: quem está acima do limite só não consegue criar mais.
- Excluir a conta apaga nível e interesse.

## 7. Critérios de aceite

1. `/` e `/apoie` respondem 200 com a CSP rígida, sem script ou estilo inline e sem recurso externo; a lista de estáticos continua fechada.
2. Em navegador de verdade: a página inicial não gera erro de console nem violação de CSP, não transborda em 360 px e os botões levam ao painel e à página de apoio.
3. Limites: conta Livre barra no 3º computador e no 31º atalho; conta Apoiador não; a cota diária segue o nível.
4. Interesse: registrar, trocar e retirar; aparece no rastro; a conta B não vê o da conta A; some ao excluir a conta.
5. `grant`: concede, recusa nível ou e-mail desconhecido, lista interessados.
6. Nenhum texto do site diz "comprar" ou "assinar"; toda quantia vem com "sugerida".

## 8. Restrições

- PRs de até 400 linhas (G12), empilhados sobre `painel-borda/5-telas`.
- VM fraca: páginas estáticas, sem imagem pesada (só SVG inline e CSS).
- Sem dependência nova.

## 9. Deixado para quem implementa

Textos finais, formas dos ícones, tempos de animação e divisão dos commits.
