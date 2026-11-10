"""Rotas HTTP do supervisor (ADR 0007)."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


class RunIn(BaseModel):
    agent: str
    prompt: str = Field(min_length=1)
    cwd: Optional[str] = None
    project: Optional[str] = None


def resolve_under_root(root: str, path: str):
    """realpath + commonpath: devolve o caminho real se for um diretorio dentro de `root`, senao None."""
    try:
        real, base = os.path.realpath(path), os.path.realpath(root)
        if os.path.commonpath([base, real]) != base or not os.path.isdir(real):
            return None
    except ValueError:  # discos diferentes no Windows
        return None
    return real


def make_router(supervisor, store, auth, projects_root=None) -> APIRouter:
    router = APIRouter(dependencies=[Depends(auth)])

    @router.post("/runs")
    def post_run(body: RunIn):
        if not body.cwd:
            raise HTTPException(400, "cwd obrigatorio")
        if projects_root is None:
            cwd = os.path.realpath(body.cwd)
        else:
            cwd = resolve_under_root(projects_root, body.cwd)
            if cwd is None:
                raise HTTPException(400, "cwd fora de PROJECTS_ROOT")
        project = os.path.basename(cwd) or None  # politica sempre do cwd final; body.project e ignorado
        mode = store.get_policy(body.agent, project)["mode"]
        try:
            run_id = supervisor.start(body.agent, body.prompt, cwd, mode)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"run_id": run_id}

    # `latest` antes de `{run_id}` para nao ser capturado como id
    @router.get("/runs/latest")
    def latest(agent: Optional[str] = None):
        return store.latest_run(agent)

    @router.get("/runs/{run_id}")
    def get_run(run_id: int):
        run = supervisor.status(run_id)
        if run is None:
            raise HTTPException(404, "run nao encontrada")
        return run

    @router.post("/runs/{run_id}/cancel")
    def cancel(run_id: int):
        if supervisor.status(run_id) is None:
            raise HTTPException(404, "run nao encontrada")
        return {"cancelled": supervisor.cancel(run_id)}

    return router
