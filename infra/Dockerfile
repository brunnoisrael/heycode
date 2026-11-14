# Relay HeyCode (ADR 0035). Instancia unica; o banco SQLite fica num volume persistente em /data.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml constraints.txt README.md ./
COPY src ./src
COPY protocol ./protocol
# o wheel embute estas pastas (force-include do pyproject, ADR 0025): sem elas o pip install falha
COPY scripts/gates ./scripts/gates
COPY .githooks ./.githooks
RUN pip install --no-cache-dir -c constraints.txt .

ENV RELAY_DB=/data/relay.db
# a pasta precisa ser do usuario que roda o relay ANTES do VOLUME: o volume novo herda esse dono
RUN mkdir -p /data && chown nobody /data
VOLUME ["/data"]
EXPOSE 8080
USER nobody
# O relay limita taxa e pareamento por IP de origem. Atras do proxy da plataforma o IP real vem em
# X-Forwarded-For; `--forwarded-allow-ips "*"` so e seguro porque a porta 8080 NAO e exposta direto
# (so o proxy chega nela). Se expor a porta, troque "*" pelo IP do proxy: senao a origem pode ser forjada.
# Tetos do servidor (ADR 0058): conexoes simultaneas (HTTP + WebSocket das maquinas), keep-alive curto e
# mensagem de WebSocket de no maximo 1 MiB. Acima do teto de conexoes o uvicorn responde 503 sem gastar memoria.
CMD ["uvicorn", "heycode.relay.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*",      "--limit-concurrency", "400", "--timeout-keep-alive", "10", "--ws-max-size", "1048576", "--no-server-header"]
