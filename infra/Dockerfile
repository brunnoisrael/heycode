# Relay HeyCode (ADR 0035). Instancia unica; o banco SQLite fica num volume persistente em /data.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml constraints.txt README.md ./
COPY src ./src
COPY protocol ./protocol
RUN pip install --no-cache-dir -c constraints.txt .

ENV RELAY_DB=/data/relay.db
VOLUME ["/data"]
EXPOSE 8080
USER nobody
CMD ["uvicorn", "heycode.relay.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
