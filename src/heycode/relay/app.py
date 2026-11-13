"""Aplicacao HTTP do relay (spec P3). A autoridade de conta vem do token de sessao, nunca do corpo."""

from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel

from heycode.identity import IdentityError
from heycode.identity.pairing import PairingService
from heycode.relay.accounts import AccountError, Accounts

MAX_INSTALLATIONS = 2


class Credentials(BaseModel):
    email: str
    password: str


class RedeemBody(BaseModel):
    code: str
    public_key: str
    name: str = "computador"


class PendingBody(BaseModel):
    pending_id: str


def create_app(repo, clock: Callable[[], float]) -> FastAPI:
    app = FastAPI(title="HeyCode relay")
    accounts = Accounts(repo, clock)
    pairing = PairingService(clock)
    names: dict[str, str] = {}
    done: dict[str, str] = {}
    app.state.repo, app.state.clock, app.state.accounts, app.state.pairing = repo, clock, accounts, pairing

    def current_account(authorization: str | None = Header(default=None)) -> str:
        token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None
        account_id = accounts.authenticate(token)
        if account_id is None:
            raise HTTPException(401, "nao autenticado")
        return account_id

    def complete(pending_id: str, binding) -> dict:
        if repo.count_installations(binding.account_id) >= MAX_INSTALLATIONS:
            raise HTTPException(409, "quota_installations")
        iid = repo.create_installation(
            binding.account_id, binding.public_key, names.pop(pending_id, "computador"), clock()
        )
        done[pending_id] = iid
        return {"state": "done", "installation_id": iid}

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/v1/register", status_code=201)
    def register(body: Credentials) -> dict:
        try:
            return {"account_id": accounts.register(body.email, body.password)}
        except AccountError as exc:
            raise HTTPException(400, exc.code) from exc

    @app.post("/v1/login")
    def login(body: Credentials) -> dict:
        try:
            return {"token": accounts.login(body.email, body.password)}
        except AccountError as exc:
            raise HTTPException(401, "credenciais invalidas") from exc

    @app.post("/v1/logout", status_code=204)
    def logout(authorization: str | None = Header(default=None), _: str = Depends(current_account)) -> Response:
        accounts.logout(authorization[7:])  # type: ignore[index]  # current_account ja validou o formato
        return Response(status_code=204)

    @app.post("/v1/pair/codes")
    def issue_code(account_id: str = Depends(current_account)) -> dict:
        return {"code": pairing.issue(account_id)}

    @app.post("/v1/pair/redeem")
    def redeem(body: RedeemBody, request: Request) -> dict:
        source = request.client.host if request.client else "desconhecida"
        try:
            pending = pairing.redeem(body.code.strip().upper(), body.public_key, source)
        except IdentityError as exc:
            raise HTTPException(429 if exc.code == "locked" else 400, exc.code) from exc
        names[pending.id] = body.name[:64]
        return {"pending_id": pending.id, "verification": pending.verification}

    @app.get("/v1/pair/{pending_id}/verification")
    def verification(pending_id: str, account_id: str = Depends(current_account)) -> dict:
        pending = pairing.get_pending(pending_id)
        if pending is None or pending.account_id != account_id:
            raise HTTPException(404, "nao encontrado")
        return {"verification": pending.verification}

    @app.post("/v1/pair/machine-confirm")
    def machine_confirm(body: PendingBody) -> dict:
        try:
            binding = pairing.confirm(body.pending_id, "machine")
        except IdentityError as exc:
            raise HTTPException(400, exc.code) from exc
        return complete(body.pending_id, binding) if binding else {"state": "pending"}

    @app.post("/v1/pair/confirm")
    def account_confirm(body: PendingBody, response: Response, account_id: str = Depends(current_account)) -> dict:
        try:
            binding = pairing.confirm(body.pending_id, "account", account_id=account_id)
        except IdentityError as exc:
            raise HTTPException(403 if exc.code == "wrong_account" else 400, exc.code) from exc
        if binding is None:
            response.status_code = 202
            return {"state": "pending"}
        return complete(body.pending_id, binding)

    @app.get("/v1/pair/{pending_id}")
    def pair_status(pending_id: str) -> dict:
        if pending_id in done:
            return {"state": "done", "installation_id": done[pending_id]}
        if pairing.get_pending(pending_id) is not None:
            return {"state": "pending"}
        raise HTTPException(404, "nao encontrado")

    @app.get("/v1/installations")
    def list_installations(account_id: str = Depends(current_account)) -> list[dict]:
        return repo.list_installations(account_id)

    @app.delete("/v1/installations/{installation_id}", status_code=204)
    def revoke(installation_id: str, account_id: str = Depends(current_account)) -> Response:
        if not repo.revoke_installation(account_id, installation_id):
            raise HTTPException(404, "nao encontrado")
        return Response(status_code=204)

    return app
