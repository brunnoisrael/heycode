from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel


class ProposeBody(BaseModel):
    agent: str = ""  # obrigatorio so para target "run"
    text: str
    project: str | None = None
    target: Literal["run", "aberto"] = "run"  # "aberto": fila da sessao ja aberta (ADR 0018)


def make_router(dictation, auth) -> APIRouter:
    r = APIRouter(dependencies=[Depends(auth)])

    @r.post("/dictation")
    def propose(b: ProposeBody):
        return dictation.propose(b.agent, b.text, b.project, b.target)

    @r.post("/dictation/confirm")
    def confirm():
        return dictation.confirm()

    @r.post("/dictation/cancel")
    def cancel():
        return dictation.cancel()

    return r
