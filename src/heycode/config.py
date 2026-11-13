"""Configuracao e segredos do usuario: leitura, criacao (`init`) e importacao do estado legado."""

import os
import secrets
import shutil
import sys
from collections.abc import MutableMapping
from pathlib import Path

REQUIRED_KEYS = ("BRIDGE_SECRET", "BRIDGE_CONTROL_SECRET", "BRIDGE_PIN")


def load_env_file(path: Path) -> dict[str, str]:
    """Le `CHAVE=valor` (ignora vazias, comentarios e linhas sem `=`; remove aspas simples ou duplas)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def apply_env(values: dict[str, str], environ: MutableMapping[str, str] = os.environ) -> None:
    """Define so o que ainda nao existe: a variavel de ambiente real prevalece sobre o arquivo."""
    for key, value in values.items():
        environ.setdefault(key, value)


def _write_private(path: Path, text: str) -> None:
    """Escrita atomica com permissao restrita (0600 onde o sistema suporta)."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if sys.platform != "win32":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _ensure_dir(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(home, 0o700)


def init_home(home: Path) -> dict[str, list[str]]:
    """Cria o diretorio e completa `config.env` com os segredos que faltam. Nunca sobrescreve nem devolve valores."""
    home = Path(home)
    _ensure_dir(home)
    path = home / "config.env"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    values = load_env_file(path)
    created: list[str] = []
    kept = [k for k in REQUIRED_KEYS if values.get(k)]
    generated: dict[str, str] = {}
    for key in REQUIRED_KEYS:
        if values.get(key):
            continue
        if key == "BRIDGE_PIN":
            generated[key] = f"{secrets.randbelow(10**6):06d}"
        else:
            while True:
                candidate = secrets.token_hex(32)
                if candidate not in {*values.values(), *generated.values()}:
                    break
            generated[key] = candidate
        created.append(key)
    if generated:
        body = existing if existing.endswith("\n") or not existing else existing + "\n"
        body += "".join(f"{k}={v}\n" for k, v in generated.items())
        _write_private(path, body)
    return {"created": created, "kept": kept}


def import_legacy(src: Path, home: Path) -> dict[str, list[str]]:
    """Copia `bridge.db` e `.env` de um clone antigo, sem apagar a origem e sem sobrescrever o destino."""
    src, home = Path(src), Path(home)
    _ensure_dir(home)
    plan = {
        "heycode.db": [src / "bridge" / "bridge.db", src / "bridge.db"],
        "config.env": [src / ".env"],
    }
    result: dict[str, list[str]] = {"copied": [], "skipped": [], "missing": []}
    for dest_name, candidates in plan.items():
        source = next((c for c in candidates if c.is_file()), None)
        dest = home / dest_name
        if source is None:
            result["missing"].append(dest_name)
        elif dest.exists():
            result["skipped"].append(dest_name)
        else:
            if dest_name == "config.env":
                _write_private(dest, source.read_text(encoding="utf-8"))
            else:
                shutil.copyfile(source, dest)
            result["copied"].append(dest_name)
    return result
