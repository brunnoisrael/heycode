"""Aplicacao HTTP do relay (spec P3). A autoridade de conta vem do token de sessao, nunca do corpo."""

import base64
import binascii
import html
from collections.abc import Callable
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from heycode.identity import IdentityError
from heycode.identity.pairing import PairingService
from heycode.identity.replay import ReplayWindow
from heycode.identity.signing import verify
from heycode.protocol import ProtocolError, validate
from heycode.protocol.outbound import uuid7
from heycode.relay.accounts import AccountError, Accounts
from heycode.relay.hub import Hub
from heycode.relay.limits import RateLimiter, day_key
from heycode.relay.oauth import OAuthConfig, OAuthError, OAuthServer

__all__ = ["OAuthConfig", "create_app"]

MAX_INSTALLATIONS = 2
DAILY_QUOTA = 200
SYNC_TIMEOUT = 4.0
CLOSE_UNAUTHORIZED = 4401


class Credentials(BaseModel):
    email: str
    password: str


class RedeemBody(BaseModel):
    code: str
    public_key: str
    name: str = "computador"


class PendingBody(BaseModel):
    pending_id: str


class SkillRequest(BaseModel):
    installation_id: str | None = None
    text: str
    destination: str
    agent: str | None = None


def create_app(
    repo,
    clock: Callable[[], float],
    *,
    sync_timeout: float = SYNC_TIMEOUT,
    daily_quota: int = DAILY_QUOTA,
    oauth: OAuthConfig | None = None,
) -> FastAPI:
    app = FastAPI(title="HeyCode relay")
    accounts = Accounts(repo, clock)
    pairing = PairingService(clock)
    hub = Hub()
    oauth_server = OAuthServer(repo, accounts, clock, oauth) if oauth else None
    replay = ReplayWindow()
    login_limiter = RateLimiter(clock, limit=10, window=60.0)
    names: dict[str, str] = {}
    done: dict[str, str] = {}
    app.state.repo, app.state.clock, app.state.accounts, app.state.pairing = repo, clock, accounts, pairing
    app.state.hub = hub

    def current_account(authorization: str | None = Header(default=None)) -> str:
        token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None
        account_id = accounts.authenticate(token)
        if account_id is None and oauth_server is not None:
            account_id = oauth_server.authenticate_access(token)  # token do account linking da Alexa
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
    def login(body: Credentials, request: Request) -> dict:
        source = request.client.host if request.client else "desconhecida"
        if not login_limiter.allow(source):
            raise HTTPException(429, "muitas tentativas")
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

    @app.get("/v1/pair/pending")
    def pending_pairings(account_id: str = Depends(current_account)) -> list[dict]:
        return [
            {"pending_id": p.id, "verification": p.verification, "name": names.get(p.id, "computador")}
            for p in pairing.pending_for(account_id)
        ]

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
    async def revoke(installation_id: str, account_id: str = Depends(current_account)) -> Response:
        if not repo.revoke_installation(account_id, installation_id):
            raise HTTPException(404, "nao encontrado")
        await hub.disconnect(installation_id)
        return Response(status_code=204)

    # --- account linking (ADR 0041) ---

    def _form_html(params: dict, error: str = "") -> str:
        hidden = "".join(
            f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v, quote=True)}">'
            for k, v in params.items()
        )
        msg = f"<p>{html.escape(error)}</p>" if error else ""
        return (
            "<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Vincular HeyCode</title>"
            "<h1>Vincular a Alexa ao HeyCode</h1>" + msg + "<form method='post' action='/oauth/authorize'>"
            "<label>E-mail <input type='email' name='email' required></label>"
            "<label>Senha <input type='password' name='password' required></label>"
            + hidden
            + "<button type='submit'>Vincular</button></form></html>"
        )

    _OAUTH_PARAMS = ("client_id", "redirect_uri", "state", "response_type", "code_challenge", "code_challenge_method")

    def _need_oauth() -> OAuthServer:
        if oauth_server is None:
            raise HTTPException(404, "oauth nao configurado")
        return oauth_server

    @app.get("/oauth/authorize")
    def oauth_authorize_form(request: Request) -> Response:
        server = _need_oauth()
        params = {k: request.query_params.get(k, "") for k in _OAUTH_PARAMS if request.query_params.get(k)}
        if not server.valid_client_redirect(params.get("client_id", ""), params.get("redirect_uri", "")):
            return HTMLResponse("Pedido de vinculacao invalido.", status_code=400)
        return HTMLResponse(_form_html(params))

    @app.post("/oauth/authorize")
    async def oauth_authorize(request: Request) -> Response:
        server = _need_oauth()
        source = request.client.host if request.client else "desconhecida"
        if not login_limiter.allow(source):
            return HTMLResponse("Muitas tentativas. Tente de novo em instantes.", status_code=429)
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode("utf-8", "replace")).items()}
        params = {k: form[k] for k in _OAUTH_PARAMS if form.get(k)}
        try:
            location = server.authorize(form.get("email", ""), form.get("password", ""), params)
        except OAuthError:
            return HTMLResponse("Pedido de vinculacao invalido.", status_code=400)  # nunca redireciona
        except AccountError:
            return HTMLResponse(_form_html(params, "E-mail ou senha incorretos."), status_code=401)
        return Response(status_code=302, headers={"Location": location})

    @app.post("/oauth/token")
    async def oauth_token(request: Request) -> Response:
        server = _need_oauth()
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode("utf-8", "replace")).items()}
        basic = None
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("basic "):
            try:
                cid, _, secret = base64.b64decode(auth[6:]).decode().partition(":")
                basic = (cid, secret)
            except (binascii.Error, UnicodeDecodeError):
                basic = ("", "")
        try:
            return JSONResponse(server.token(form, basic), headers={"Cache-Control": "no-store"})
        except OAuthError as exc:
            return JSONResponse({"error": exc.code}, status_code=exc.status)

    # --- conexao da maquina e endpoint da skill ---

    def authenticate_envelope(msg: object, expected: str | None = None) -> dict | None:
        """Instalacao dona do envelope se estiver valido e assinado; None em qualquer duvida (falha fechada)."""
        if not isinstance(msg, dict):
            return None
        try:
            validate(msg)
        except ProtocolError:
            return None
        iid = msg["installation_id"]
        if expected is not None and iid != expected:
            return None
        inst = repo.get_installation(iid)
        if inst is None or inst["revoked"]:
            return None
        try:
            verify(msg, inst["public_key"], clock(), replay=replay)
        except IdentityError:
            return None
        return inst

    def frame(type_: str, installation_id: str, payload: dict, msg_id: str | None = None) -> dict:
        # relay -> maquina: autenticado pelo TLS da conexao (ver threat-model), sem assinatura no MVP
        return {
            "v": 1,
            "id": msg_id or uuid7(clock()),
            "ts": clock(),
            "installation_id": installation_id,
            "type": type_,
            "payload": payload,
            "sig": "",
        }

    @app.websocket("/v1/connect")
    async def connect(ws: WebSocket) -> None:
        await ws.accept()
        try:
            inst = authenticate_envelope(await ws.receive_json())
        except (WebSocketDisconnect, ValueError):
            return
        if inst is None:
            await ws.close(code=CLOSE_UNAUTHORIZED)
            return
        iid = inst["id"]
        repo.touch_installation(iid, clock())
        await hub.attach(iid, ws)
        try:
            await ws.send_json(frame("status", iid, {"state": "idle"}))
            while True:
                msg = await ws.receive_json()
                if authenticate_envelope(msg, expected=iid) is None:
                    await ws.close(code=CLOSE_UNAUTHORIZED)
                    return
                repo.touch_installation(iid, clock())
                reply_to = msg["payload"].get("in_reply_to")
                if isinstance(reply_to, str):
                    hub.resolve(iid, reply_to, msg["payload"])
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            hub.detach(iid, ws)

    @app.post("/v1/skill/request")
    async def skill_request(body: SkillRequest, account_id: str = Depends(current_account)) -> dict:
        if body.installation_id is not None:
            inst = repo.get_owned_installation(account_id, body.installation_id)
            if inst is None:  # mesma resposta para inexistente e de outra conta
                raise HTTPException(404, "not_found")
        else:
            owned = repo.list_installations(account_id)
            if not owned:
                raise HTTPException(404, "no_installation")
            if len(owned) > 1:
                raise HTTPException(409, "choose_installation")
            inst = owned[0]
        if repo.bump_usage(account_id, day_key(clock())) > daily_quota:
            raise HTTPException(429, "quota_requests")
        payload = {"text": body.text, "destination": body.destination}
        if body.agent:
            payload["agent"] = body.agent
        envelope = frame("instruction", inst["id"], payload)
        state, result = await hub.request(inst["id"], account_id, envelope, sync_timeout)
        if state == "offline":
            return {"state": "offline"}
        if state == "pending":
            return {"state": "pending", "request_id": envelope["id"]}
        return {"state": "done", "request_id": envelope["id"], "result": result}

    @app.get("/v1/skill/result/{request_id}")
    def skill_result(request_id: str, account_id: str = Depends(current_account)) -> dict:
        found = hub.result_for(account_id, request_id)
        if found is None:
            raise HTTPException(404, "not_found")
        return found

    return app
