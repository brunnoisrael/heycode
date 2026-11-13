"""Verificacao das requisicoes da Alexa (ADR 0042): certificado, cadeia, assinatura, timestamp e applicationId.

O certificado baixado e dado nao confiavel: so e analisado (nunca executado), a URL e checada ANTES de
qualquer acesso a rede, e o resultado fica em cache por URL ate o certificado vencer.
"""

import base64
import binascii
import datetime as dt
import json
import posixpath
from collections.abc import Callable, Mapping
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

CERT_HOST = "s3.amazonaws.com"
CERT_PATH_PREFIX = "/echo.api/"
CERT_SAN = "echo-api.amazon.com"
TOLERANCE = 150.0
MAX_CERT_BYTES = 64 * 1024


class AlexaVerifyError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def default_fetch(url: str) -> bytes:
    import httpx

    resp = httpx.get(url, timeout=3.0, follow_redirects=False)
    resp.raise_for_status()
    if len(resp.content) > MAX_CERT_BYTES:
        raise ValueError("certificado grande demais")
    return resp.content


def default_roots() -> list[x509.Certificate]:
    import certifi

    with open(certifi.where(), "rb") as f:
        return x509.load_pem_x509_certificates(f.read())


def _check_url(url: str) -> None:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise AlexaVerifyError("bad_cert_url") from exc
    path = parts.path
    normalized = posixpath.normpath(path) if path else ""
    ok = (
        parts.scheme.lower() == "https"
        and (parts.hostname or "").lower() == CERT_HOST
        and parts.username is None
        and parts.password is None
        and port in (None, 443)
        and path.startswith(CERT_PATH_PREFIX)
        and ".." not in path.split("/")
        and normalized == path.rstrip("/")
    )
    if not ok:
        raise AlexaVerifyError("bad_cert_url", "URL do certificado fora do padrao da Amazon")


def _parse_ts(value: object) -> float:
    if not isinstance(value, str):
        raise AlexaVerifyError("stale_request", "sem timestamp")
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise AlexaVerifyError("stale_request", "timestamp invalido") from exc


class AlexaVerifier:
    def __init__(
        self,
        skill_id: str,
        clock: Callable[[], float],
        *,
        fetch: Callable[[str], bytes] = default_fetch,
        trust_roots: list[x509.Certificate] | None = None,
        tolerance: float = TOLERANCE,
    ) -> None:
        self._skill_id = skill_id
        self._clock = clock
        self._fetch = fetch
        self._roots = trust_roots
        self._tolerance = tolerance
        self._cache: dict[str, tuple[x509.Certificate, float]] = {}  # url -> (folha, vale ate)

    def _leaf(self, url: str) -> x509.Certificate:
        now = self._clock()
        cached = self._cache.get(url)
        if cached and cached[1] > now:
            return cached[0]
        try:
            chain = x509.load_pem_x509_certificates(self._fetch(url))
        except Exception as exc:  # noqa: BLE001 - rede ou PEM ruim: mesma recusa
            raise AlexaVerifyError("bad_cert", "nao foi possivel obter o certificado") from exc
        if not chain:
            raise AlexaVerifyError("bad_cert", "cadeia vazia")
        leaf, intermediates = chain[0], chain[1:]
        when = dt.datetime.fromtimestamp(now, dt.UTC)
        if not (leaf.not_valid_before_utc <= when <= leaf.not_valid_after_utc):
            raise AlexaVerifyError("bad_cert", "certificado fora da validade")
        try:
            san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        except x509.ExtensionNotFound as exc:
            raise AlexaVerifyError("bad_cert", "certificado sem nomes alternativos") from exc
        if CERT_SAN not in san.get_values_for_type(x509.DNSName):
            raise AlexaVerifyError("bad_cert", f"certificado sem {CERT_SAN}")
        roots = self._roots if self._roots is not None else default_roots()
        try:
            verifier = PolicyBuilder().store(Store(roots)).time(when).build_server_verifier(x509.DNSName(CERT_SAN))
            verifier.verify(leaf, intermediates)
        except (VerificationError, ValueError) as exc:
            raise AlexaVerifyError("bad_cert", "cadeia de certificados nao confiavel") from exc
        self._cache[url] = (leaf, leaf.not_valid_after_utc.timestamp())
        return leaf

    def verify(self, headers: Mapping[str, str], body: bytes) -> dict:
        """Devolve o JSON da requisicao se tudo conferir; levanta AlexaVerifyError (nada e executado)."""
        h = {k.lower(): v for k, v in headers.items()}
        url = h.get("signaturecertchainurl", "")
        _check_url(url)  # antes de qualquer acesso a rede
        leaf = self._leaf(url.strip())
        public = leaf.public_key()
        if not isinstance(public, rsa.RSAPublicKey):
            raise AlexaVerifyError("bad_cert", "chave do certificado nao e RSA")
        try:
            signature = base64.b64decode(h.get("signature-256", ""), validate=True)
            public.verify(signature, body, padding.PKCS1v15(), hashes.SHA256())
        except (binascii.Error, InvalidSignature) as exc:
            raise AlexaVerifyError("bad_signature", "assinatura invalida") from exc
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError
        except ValueError as exc:
            raise AlexaVerifyError("bad_body", "corpo nao e JSON de objeto") from exc
        request = data.get("request") if isinstance(data.get("request"), dict) else {}
        if abs(self._clock() - _parse_ts(request.get("timestamp"))) > self._tolerance:
            raise AlexaVerifyError("stale_request", "requisicao fora da janela de tempo")
        app = (data.get("context", {}).get("System", {}).get("application", {}) or {}).get("applicationId")
        app = app or (data.get("session", {}).get("application", {}) or {}).get("applicationId")
        if app != self._skill_id:
            raise AlexaVerifyError("wrong_application", "applicationId de outra skill")
        return data
