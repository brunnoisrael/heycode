"""Localiza os modelos (scripts/gates e .githooks) copiados para projetos novos criados por voz."""

from pathlib import Path


def template_root() -> str:
    """Pasta com `scripts/gates` e `.githooks`: dentro do pacote instalado ou, no clone, a raiz do repositorio."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "_template", here.parents[1]):
        if (candidate / "scripts" / "gates").is_dir() and (candidate / ".githooks").is_dir():
            return str(candidate)
    raise FileNotFoundError("modelos de projeto (scripts/gates e .githooks) nao encontrados")
