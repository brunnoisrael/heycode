"""Aplicacao HTTP do relay (spec P3). A autoridade de conta vem do token de sessao, nunca do corpo."""

import asyncio
import base64
import binascii
import hashlib
import hmac
import html
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.websockets import WebSocketDisconnect

from heycode.identity import IdentityError
from heycode.identity.pairing import PairingService
from heycode.identity.replay import ReplayWindow
from heycode.identity.signing import verify
from heycode.protocol import ProtocolError, validate
from heycode.protocol.outbound import uuid7
from heycode.relay.accounts import SESSION_TTL, AccountError, Accounts
from heycode.relay.alexa_verify import AlexaVerifier, AlexaVerifyError
from heycode.relay.hub import Hub
from heycode.relay.limits import RateLimiter, day_key
from heycode.relay.oauth import OAuthConfig, OAuthError, OAuthServer
from heycode.relay.shortcuts import normalize
from heycode.relay.voice import BridgeUnavailable
from heycode.relay.voice import handle as handle_voice

__all__ = ["OAuthConfig", "create_app"]

MAX_INSTALLATIONS = 2
DAILY_QUOTA = 200
SESSION_COOKIE = "hc_session"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
MAX_PENDING_DEVICES = 10
MAX_SHORTCUTS = 30
PANEL_DIR = Path(__file__).parent / "panel"
PANEL_FILES = {"panel.js": "text/javascript; charset=utf-8", "panel.css": "text/css; charset=utf-8"}  # lista fechada
PANEL_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "font-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
SHORTCUT_AGENTS = ("claude", "codex", "aider")
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


class DeviceBody(BaseModel):
    installation_id: str
    device_id: str


class RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome vazio")
        return v


class DefaultInstallationBody(BaseModel):
    installation_id: str


class DeleteAccountBody(BaseModel):
    password: str


class ShortcutBody(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    aliases: list[Annotated[str, Field(min_length=2, max_length=40)]] = Field(default_factory=list, max_length=5)
    agent: str
    project: str | None = Field(default=None, max_length=80)
    instruction: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=200)
    enabled: bool = True

    @field_validator("agent")
    @classmethod
    def _agent(cls, v: str) -> str:
        if v not in SHORTCUT_AGENTS:
            raise ValueError("agente desconhecido")
        return v

    @field_validator("name", "instruction")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _speakable(self):
        if len(normalize(self.name)) < 2 or any(len(normalize(a)) < 2 for a in self.aliases):
            raise ValueError("nome ou apelido sem letras suficientes")
        if not self.instruction:
            raise ValueError("instrucao vazia")
        return self


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
    alexa: AlexaVerifier | None = None,
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

    def audit(account_id: str, kind: str, result: str = "ok", **extra) -> None:
        repo.add_audit(account_id, clock(), kind, result, **extra)

    csrf_key = secrets.token_bytes(32)  # por processo: reiniciar o relay exige entrar de novo no painel

    def _csrf_for(session_token: str) -> str:
        return hmac.new(csrf_key, session_token.encode(), hashlib.sha256).hexdigest()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith(("/v1/panel", "/app")):
            response.headers["Cache-Control"] = "no-store"
        return response

    def current_account(request: Request, authorization: str | None = Header(default=None)) -> str:
        if authorization:  # API: heycode e Alexa, sem cookie e sem CSRF
            token = authorization[7:] if authorization.lower().startswith("bearer ") else None
            account_id = accounts.authenticate(token)
            if account_id is None and oauth_server is not None:
                account_id = oauth_server.authenticate_access(token)  # token do account linking da Alexa
            if account_id is None:
                raise HTTPException(401, "nao autenticado")
            return account_id
        cookie = request.cookies.get(SESSION_COOKIE)  # painel web (ADR 0046)
        account_id = accounts.authenticate(cookie)
        if account_id is None:
            raise HTTPException(401, "nao autenticado")
        if request.method not in SAFE_METHODS:
            sent = request.headers.get("x-csrf-token", "")
            if not hmac.compare_digest(sent.encode(), _csrf_for(cookie or "").encode()):
                raise HTTPException(403, "csrf")
        return account_id

    def _set_session_cookie(response: Response, token: str, request: Request) -> None:
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=int(SESSION_TTL),
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            path="/",
        )

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

    @app.post("/v1/panel/login")
    def panel_login(body: Credentials, request: Request, response: Response) -> dict:
        source = request.client.host if request.client else "desconhecida"
        if not login_limiter.allow(source):
            raise HTTPException(429, "muitas tentativas")
        try:
            token = accounts.login(body.email, body.password)
        except AccountError as exc:
            raise HTTPException(401, "credenciais invalidas") from exc
        _set_session_cookie(response, token, request)
        return {"ok": True}  # o token nunca vai no corpo: so no cookie HttpOnly

    @app.get("/v1/panel/session")
    def panel_session(request: Request, account_id: str = Depends(current_account)) -> dict:
        token = request.cookies.get(SESSION_COOKIE, "")
        return {"email": repo.get_account_email(account_id), "csrf": _csrf_for(token)}

    @app.post("/v1/panel/logout", status_code=204)
    def panel_logout(request: Request, _: str = Depends(current_account)) -> Response:
        accounts.logout(request.cookies.get(SESSION_COOKIE, ""))
        response = Response(status_code=204)
        response.delete_cookie(
            SESSION_COOKIE, path="/", secure=request.url.scheme == "https", httponly=True, samesite="strict"
        )
        return response

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
        default = repo.get_default_installation(account_id)
        return [
            {**i, "online": hub.is_online(i["id"]), "is_default": i["id"] == default}
            for i in repo.list_installations(account_id)
        ]

    @app.patch("/v1/installations/{installation_id}")
    def rename_installation(installation_id: str, body: RenameBody, account_id: str = Depends(current_account)) -> dict:
        item = repo.rename_installation(account_id, installation_id, body.name)
        if item is None:
            raise HTTPException(404, "nao encontrado")
        audit(account_id, "painel:renomear_computador", installation_id=installation_id, label=item["name"])
        return {"id": item["id"], "name": item["name"]}

    @app.delete("/v1/installations/{installation_id}", status_code=204)
    async def revoke(installation_id: str, account_id: str = Depends(current_account)) -> Response:
        if not repo.revoke_installation(account_id, installation_id):
            raise HTTPException(404, "nao encontrado")
        audit(account_id, "painel:revogar_computador", installation_id=installation_id)
        await hub.disconnect(installation_id)
        return Response(status_code=204)

    # --- painel web (ADR 0046): arquivos estaticos de lista fechada, com CSP rigida ---

    def _panel_headers() -> dict:
        return {"Content-Security-Policy": PANEL_CSP, "X-Frame-Options": "DENY"}

    @app.get("/app", include_in_schema=False)
    def panel_index() -> Response:
        html = (PANEL_DIR / "index.html").read_bytes()
        return Response(html, media_type="text/html; charset=utf-8", headers=_panel_headers())

    @app.get("/app/static/{name}", include_in_schema=False)
    def panel_static(name: str) -> Response:
        media = PANEL_FILES.get(name)
        if media is None:
            raise HTTPException(404, "nao encontrado")
        return Response((PANEL_DIR / name).read_bytes(), media_type=media, headers=_panel_headers())

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

    # --- dispositivos, instalacao padrao e exclusao da conta (ADR 0043, LGPD) ---

    @app.get("/v1/audit")
    def list_audit(
        limit: int = 50,
        before: int | None = None,
        installation_id: str | None = None,
        device_id: str | None = None,
        result: str | None = None,
        account_id: str = Depends(current_account),
    ) -> list[dict]:
        limit = max(1, min(limit, 100))
        return repo.list_audit(account_id, limit, before, installation_id, device_id, result)

    @app.get("/v1/audit/detail")
    async def audit_detail(installation_id: str, limit: int = 20, account_id: str = Depends(current_account)) -> dict:
        """Detalhe vindo do proprio computador, sob demanda: o relay repassa e esquece (ADR 0047)."""
        if repo.get_owned_installation(account_id, installation_id) is None:
            raise HTTPException(404, "nao encontrado")
        limit = max(1, min(limit, 50))
        envelope = frame("bridge-call", installation_id, {"method": "GET", "path": f"/voice/audit?limit={limit}"})
        state, result = await hub.request(installation_id, account_id, envelope, sync_timeout)
        if state == "offline":
            raise HTTPException(503, "offline")
        if state != "done" or not isinstance(result, dict) or result.get("status") != 200:
            raise HTTPException(502, "computador nao respondeu")
        return result["body"]

    # --- atalhos para agentes (ADR 0048, fase A) ---

    def _taken(account_id: str, body: ShortcutBody, ignore_id: str | None = None) -> bool:
        """Nome ou apelido ja usado por outro atalho da conta (comparando como a Alexa vai ouvir)."""
        mine = {normalize(body.name), *(normalize(a) for a in body.aliases)}
        for other in repo.list_shortcuts(account_id):
            if other["id"] == ignore_id:
                continue
            if mine & {normalize(other["name"]), *(normalize(a) for a in other["aliases"])}:
                return True
        return False

    @app.get("/v1/commands")
    def list_commands(account_id: str = Depends(current_account)) -> list[dict]:
        return repo.list_shortcuts(account_id)

    @app.post("/v1/commands", status_code=201)
    def create_command(body: ShortcutBody, account_id: str = Depends(current_account)) -> dict:
        if repo.count_shortcuts(account_id) >= MAX_SHORTCUTS:
            raise HTTPException(409, "quota_commands")
        if _taken(account_id, body):
            raise HTTPException(409, "name_taken")
        item = repo.create_shortcut(account_id, body.model_dump(), clock())
        audit(account_id, "painel:criar_atalho", label=item["name"])
        return item

    @app.put("/v1/commands/{shortcut_id}")
    def update_command(shortcut_id: str, body: ShortcutBody, account_id: str = Depends(current_account)) -> dict:
        if _taken(account_id, body, ignore_id=shortcut_id):
            raise HTTPException(409, "name_taken")
        item = repo.update_shortcut(account_id, shortcut_id, body.model_dump())
        if item is None:
            raise HTTPException(404, "nao encontrado")
        audit(account_id, "painel:editar_atalho", label=item["name"])
        return item

    @app.delete("/v1/commands/{shortcut_id}", status_code=204)
    def delete_command(shortcut_id: str, account_id: str = Depends(current_account)) -> Response:
        gone = repo.delete_shortcut(account_id, shortcut_id)
        if gone is None:
            raise HTTPException(404, "nao encontrado")
        audit(account_id, "painel:apagar_atalho", label=gone["name"])
        return Response(status_code=204)

    @app.get("/v1/devices")
    def list_devices(account_id: str = Depends(current_account)) -> list[dict]:
        return repo.list_devices(account_id)

    @app.post("/v1/devices/approve", status_code=204)
    def approve_device(body: DeviceBody, account_id: str = Depends(current_account)) -> Response:
        if not repo.approve_device(account_id, body.installation_id, body.device_id):
            raise HTTPException(404, "nao encontrado")
        audit(account_id, "painel:aprovar_dispositivo", installation_id=body.installation_id, device_id=body.device_id)
        return Response(status_code=204)

    @app.post("/v1/devices/deny", status_code=204)
    def deny_device(body: DeviceBody, account_id: str = Depends(current_account)) -> Response:
        if not repo.remove_device(account_id, body.installation_id, body.device_id, status="pending"):
            raise HTTPException(404, "nao encontrado")
        audit(account_id, "painel:negar_dispositivo", installation_id=body.installation_id, device_id=body.device_id)
        return Response(status_code=204)

    @app.delete("/v1/devices/{installation_id}/{device_id}", status_code=204)
    def revoke_device(installation_id: str, device_id: str, account_id: str = Depends(current_account)) -> Response:
        if not repo.remove_device(account_id, installation_id, device_id, status="approved"):
            raise HTTPException(404, "nao encontrado")
        audit(account_id, "painel:revogar_dispositivo", installation_id=installation_id, device_id=device_id)
        return Response(status_code=204)

    @app.put("/v1/default-installation", status_code=204)
    def set_default(body: DefaultInstallationBody, account_id: str = Depends(current_account)) -> Response:
        if repo.get_owned_installation(account_id, body.installation_id) is None:
            raise HTTPException(404, "nao encontrado")
        repo.set_default_installation(account_id, body.installation_id)
        audit(account_id, "painel:instalacao_padrao", installation_id=body.installation_id)
        return Response(status_code=204)

    @app.delete("/v1/account", status_code=204)
    async def delete_account(body: DeleteAccountBody, account_id: str = Depends(current_account)) -> Response:
        email = repo.get_account_email(account_id)
        try:
            accounts.check_credentials(email or "", body.password)
        except AccountError as exc:
            raise HTTPException(403, "senha incorreta") from exc
        for iid in repo.delete_account(account_id):
            await hub.disconnect(iid)
        return Response(status_code=204)

    # --- endpoint da skill compartilhada (ADR 0033, 0042) ---

    def _say(text: str, *, end: bool = True, card: str | None = None) -> dict:
        response: dict = {"outputSpeech": {"type": "PlainText", "text": text}, "shouldEndSession": end}
        if card:
            response["card"] = {"type": card}
        return {"version": "1.0", "response": response}

    def _pick_installation(account_id: str) -> tuple[dict | None, str | None]:
        """(instalacao, fala de erro). Nunca adivinha entre varias e nunca sai da conta."""
        owned = repo.list_installations(account_id)
        if not owned:
            return None, "Nenhum computador esta pareado a sua conta HeyCode. Pareie um pelo aplicativo."
        default = repo.get_default_installation(account_id)
        chosen = next((i for i in owned if i["id"] == default), None)
        if chosen is None and len(owned) == 1:
            chosen = owned[0]
        if chosen is None:
            return None, "Voce tem varios computadores. Escolha qual usar no aplicativo do HeyCode."
        return chosen, None

    @app.post("/v1/alexa")
    async def alexa_endpoint(request: Request) -> JSONResponse:
        if alexa is None:
            raise HTTPException(404, "skill nao configurada")
        body = await request.body()
        try:
            data = await asyncio.to_thread(alexa.verify, dict(request.headers), body)
        except AlexaVerifyError as exc:
            return JSONResponse({"error": exc.code}, status_code=400)  # nada e executado
        system = data.get("context", {}).get("System", {})
        req = data.get("request", {})
        if req.get("type") == "SessionEndedRequest":
            return JSONResponse({"version": "1.0", "response": {}})
        token = (system.get("user") or {}).get("accessToken")
        account_id = oauth_server.authenticate_access(token) if oauth_server else None
        if account_id is None:
            return JSONResponse(
                _say("Para usar o HeyCode, vincule sua conta no aplicativo da Alexa.", card="LinkAccount")
            )
        kind = (req.get("intent") or {}).get("name") or str(req.get("type") or "?")
        device_id = (system.get("device") or {}).get("deviceId")
        inst, problem = _pick_installation(account_id)
        if inst is None:
            audit(account_id, kind, "sem_computador", device_id=device_id)
            return JSONResponse(_say(problem or ""))
        if not device_id:
            audit(account_id, kind, "barrado", installation_id=inst["id"])
            return JSONResponse(_say("Nao consegui identificar este dispositivo."))
        status = repo.device_status(account_id, inst["id"], device_id)
        if status != "approved":
            if status is None:
                repo.add_pending_device(account_id, inst["id"], device_id, clock(), MAX_PENDING_DEVICES)
            audit(account_id, kind, "barrado", installation_id=inst["id"], device_id=device_id)
            return JSONResponse(
                _say("Este dispositivo ainda nao foi autorizado. Autorize-o no aplicativo do HeyCode e tente de novo.")
            )
        if req.get("type") == "LaunchRequest" and not hub.is_online(inst["id"]):
            audit(account_id, kind, "offline", installation_id=inst["id"], device_id=device_id)
            return JSONResponse(_say(f"O computador {inst['name']} esta offline."))
        outcome = {"called": False, "result": "ok"}  # resultado da interacao para o rastro (sem conteudo)

        async def call(method: str, path: str, body: dict | None = None) -> dict:
            """Chama a ponte do computador pelo canal assinado; falhas viram BridgeUnavailable."""
            outcome["called"] = True
            if repo.bump_usage(account_id, day_key(clock())) > daily_quota:
                outcome["result"] = "cota"
                raise BridgeUnavailable("cota", speech="Voce atingiu o limite diario de pedidos. Tente amanha.")
            payload: dict = {"method": method, "path": path}
            if body is not None:
                payload["body"] = body
            envelope = frame("bridge-call", inst["id"], payload)
            state, result = await hub.request(inst["id"], account_id, envelope, sync_timeout)
            if state == "offline":
                outcome["result"] = "offline"
                raise BridgeUnavailable("offline", speech=f"O computador {inst['name']} esta offline.")
            if state != "done" or not isinstance(result, dict) or not isinstance(result.get("body"), dict):
                outcome["result"] = "erro"
                raise BridgeUnavailable(state)
            status = result.get("status")
            if status == 403 and result["body"].get("speech"):  # recusa explicada pelo computador (auto, etc.)
                outcome["result"] = "barrado"
                return result["body"]
            if not isinstance(status, int) or status >= 400:
                outcome["result"] = "erro"
                raise BridgeUnavailable(f"ponte respondeu {status}")
            return result["body"]

        meta: dict = {}
        shortcuts = repo.list_shortcuts(account_id) if kind == "RunCommandIntent" else None
        answer = await handle_voice(data, call, shortcuts=shortcuts, meta=meta)
        audit(
            account_id,
            kind,
            outcome["result"] if outcome["called"] else "sem_acao",
            installation_id=inst["id"],
            device_id=device_id,
            label=meta.get("label"),
        )
        if req.get("type") == "LaunchRequest":
            spoken = answer["response"]["outputSpeech"]["text"]
            answer["response"]["outputSpeech"]["text"] = f"HeyCode conectado ao computador {inst['name']}. {spoken}"
        return JSONResponse(answer)

    # --- conexao da maquina e endpoint da skill (pedidos autenticados) ---

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
