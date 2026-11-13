"""Servidor OAuth2 do relay para o account linking da Alexa (ADR 0041).

Codigo de uso unico (10 min), access token de 1 h, refresh token rotativo de 30 dias; reuso de um refresh
ja usado revoga a familia inteira. Tudo guardado so como hash; segredo do cliente em tempo constante.
"""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

CODE_TTL = 600.0
ACCESS_TTL = 3600.0
REFRESH_TTL = 30 * 86400.0


class OAuthError(Exception):
    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    client_secret: str
    redirect_uris: tuple[str, ...]


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _pkce_ok(verifier: str | None, challenge: str) -> bool:
    if not verifier:
        return False
    digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return hmac.compare_digest(digest, challenge)


class OAuthServer:
    def __init__(self, repo, accounts, clock: Callable[[], float], config: OAuthConfig) -> None:
        self._repo = repo
        self._accounts = accounts
        self._clock = clock
        self._cfg = config

    def valid_client_redirect(self, client_id: str, redirect_uri: str) -> bool:
        return hmac.compare_digest(client_id.encode(), self._cfg.client_id.encode()) and (
            redirect_uri in self._cfg.redirect_uris
        )

    def authorize(self, email: str, password: str, params: dict) -> str:
        """Valida cliente e credenciais; devolve a URL de redirecionamento com o codigo."""
        redirect_uri = params.get("redirect_uri", "")
        if not self.valid_client_redirect(params.get("client_id", ""), redirect_uri):
            raise OAuthError("invalid_request")
        account_id = self._accounts.check_credentials(email, password)  # AccountError sobe para a rota
        challenge = params.get("code_challenge") if params.get("code_challenge_method") == "S256" else None
        code = secrets.token_urlsafe(32)
        self._repo.put_oauth_code(
            _h(code), account_id, self._cfg.client_id, redirect_uri, challenge, self._clock() + CODE_TTL
        )
        query = {"code": code}
        if params.get("state"):
            query["state"] = params["state"]
        sep = "&" if "?" in redirect_uri else "?"
        return redirect_uri + sep + urlencode(query)

    def _authenticate_client(self, client_id: str | None, secret: str | None) -> None:
        ok_id = hmac.compare_digest((client_id or "").encode(), self._cfg.client_id.encode())
        ok_secret = hmac.compare_digest((secret or "").encode(), self._cfg.client_secret.encode())
        if not (ok_id and ok_secret):
            raise OAuthError("invalid_client", 401)

    def _issue(self, account_id: str, family: str) -> dict:
        now = self._clock()
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        cid = self._cfg.client_id
        self._repo.put_oauth_token(_h(access), "access", account_id, cid, family, now + ACCESS_TTL)
        self._repo.put_oauth_token(_h(refresh), "refresh", account_id, cid, family, now + REFRESH_TTL)
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": int(ACCESS_TTL),
            "refresh_token": refresh,
        }

    def token(self, form: dict, basic: tuple[str, str] | None = None) -> dict:
        client_id, secret = basic if basic else (form.get("client_id"), form.get("client_secret"))
        self._authenticate_client(client_id, secret)
        grant = form.get("grant_type")
        if grant == "authorization_code":
            return self._from_code(form)
        if grant == "refresh_token":
            return self._from_refresh(form.get("refresh_token", ""))
        raise OAuthError("unsupported_grant_type")

    def _from_code(self, form: dict) -> dict:
        row = self._repo.pop_oauth_code(_h(form.get("code", "")))
        if row is None or row["expires"] < self._clock():
            raise OAuthError("invalid_grant")
        if row["redirect_uri"] != form.get("redirect_uri") or row["client_id"] != self._cfg.client_id:
            raise OAuthError("invalid_grant")
        if row["challenge"] and not _pkce_ok(form.get("code_verifier"), row["challenge"]):
            raise OAuthError("invalid_grant")
        return self._issue(row["account_id"], secrets.token_hex(8))

    def _from_refresh(self, refresh_token: str) -> dict:
        th = _h(refresh_token)
        row = self._repo.get_oauth_token(th)
        if row is None or row["kind"] != "refresh":
            raise OAuthError("invalid_grant")
        if row["used"] or not self._repo.mark_oauth_token_used(th):
            self._repo.revoke_oauth_family(row["family"])  # refresh reaproveitado: alguem o copiou
            raise OAuthError("invalid_grant")
        if row["expires"] < self._clock():
            raise OAuthError("invalid_grant")
        return self._issue(row["account_id"], row["family"])

    def authenticate_access(self, token: str | None) -> str | None:
        if not token:
            return None
        row = self._repo.get_oauth_token(_h(token))
        if row is None or row["kind"] != "access" or row["expires"] < self._clock():
            return None
        return row["account_id"]

    def revoke_account(self, account_id: str) -> None:
        self._repo.revoke_oauth_account(account_id)
