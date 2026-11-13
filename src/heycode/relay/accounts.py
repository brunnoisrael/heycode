"""Contas e sessoes do relay (ADR 0036): Argon2id, token opaco guardado so como hash, sem enumeracao."""

import hashlib
import re
import secrets
from collections.abc import Callable

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

SESSION_TTL = 12 * 3600.0
MIN_PASSWORD = 10
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Accounts:
    def __init__(self, repo, clock: Callable[[], float]) -> None:
        self._repo = repo
        self._clock = clock
        self._hasher = PasswordHasher()  # argon2id por padrao
        self._dummy = self._hasher.hash("senha-ficticia-para-tempo-constante")

    def register(self, email: str, password: str) -> str:
        email = email.strip().lower()
        if not _EMAIL.match(email):
            raise AccountError("invalid_email", "e-mail invalido")
        if len(password) < MIN_PASSWORD:
            raise AccountError("weak_password", f"senha com ao menos {MIN_PASSWORD} caracteres")
        aid = self._repo.create_account(email, self._hasher.hash(password), self._clock())
        if aid is None:
            raise AccountError("email_taken", "e-mail ja cadastrado")
        return aid

    def login(self, email: str, password: str) -> str:
        account = self._repo.get_account_by_email(email.strip().lower())
        stored = account["password_hash"] if account else self._dummy  # tempo parecido nos dois casos
        try:
            self._hasher.verify(stored, password)
            ok = account is not None
        except VerificationError:
            ok = False
        if not ok:
            raise AccountError("bad_credentials", "credenciais invalidas")
        token = secrets.token_urlsafe(32)
        self._repo.create_session(_hash_token(token), account["id"], self._clock() + SESSION_TTL)
        return token

    def authenticate(self, token: str | None) -> str | None:
        if not token:
            return None
        th = _hash_token(token)
        session = self._repo.get_session(th)
        if session is None:
            return None
        if session["expires"] < self._clock():
            self._repo.delete_session(th)
            return None
        return session["account_id"]

    def logout(self, token: str) -> None:
        self._repo.delete_session(_hash_token(token))
