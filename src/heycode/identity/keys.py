"""Par Ed25519 da instalacao. A privada fica so no diretorio de dados do usuario, modo 0600."""

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEY_NAME = "installation.key"


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / "identity" / KEY_NAME


def public_b64(private: Ed25519PrivateKey) -> str:
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def generate_keypair(data_dir: Path, force: bool = False) -> str:
    """Gera e grava a chave privada; devolve a publica em base64. Nao sobrescreve sem `force`."""
    path = _path(data_dir)
    if path.exists() and not force:
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    os.replace(tmp, path)
    return public_b64(private)


def load_private_key(data_dir: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(_path(data_dir).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("chave de instalacao deve ser Ed25519")
    return key
