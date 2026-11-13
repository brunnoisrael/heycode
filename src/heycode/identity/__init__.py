"""Identidade por instalacao (ADR 0030). Falha fechada: qualquer duvida e recusa."""


class IdentityError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
