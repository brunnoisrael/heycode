from fastapi import APIRouter, Depends
from pydantic import BaseModel


class ProjectBody(BaseModel):
    name: str
    agent: str
    description: str


def make_router(creator, dictation, auth) -> APIRouter:
    """/confirm e /cancel unificados: projeto pendente primeiro, depois ditado."""
    r = APIRouter(dependencies=[Depends(auth)])
    creator.link(dictation)  # pendencia global unica: propor um tipo cancela o outro

    @r.post("/projects")
    def propose(b: ProjectBody):
        return creator.propose(b.name, b.agent, b.description)

    @r.post("/confirm")
    def confirm():
        if creator.has_pending():
            return creator.confirm()
        return dictation.confirm()

    @r.post("/cancel")
    def cancel():
        project = creator.cancel()
        spoken = dictation.cancel()
        return project if "Não há" not in project["speech"] else spoken

    return r
