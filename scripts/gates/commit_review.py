"""Valida parecer independente emitido como status do commit no GitHub."""

import json
import os
import subprocess
import sys

CONTEXT = "heycode-review"


def check_review(statuses: list[dict], reviewer: str, author: str) -> list[str]:
    if not reviewer or not author:
        return ["Revisao: revisor ou autor GitHub ausente; falha fechada."]
    if reviewer.casefold() == author.casefold():
        return ["Revisao: o revisor deve ter identidade distinta do autor."]
    for item in statuses:  # a API retorna os status mais recentes primeiro
        creator = item.get("creator") or {}
        if item.get("context") == CONTEXT and creator.get("login", "").casefold() == reviewer.casefold():
            if item.get("state") == "success":
                return []
            return ["Revisao: o parecer mais recente do revisor nao aprovou o commit."]
    return ["Revisao: nenhum parecer do revisor configurado neste commit."]


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["HEAD_SHA"]
    reviewer = os.environ.get("INDEPENDENT_REVIEWER", "")
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("SHA invalido")
    commit = json.loads(subprocess.check_output(["gh", "api", f"repos/{repo}/commits/{sha}"], text=True))
    pages = json.loads(
        subprocess.check_output(
            ["gh", "api", "--paginate", "--slurp", f"repos/{repo}/commits/{sha}/statuses?per_page=100"],
            text=True,
        )
    )
    statuses = [item for page in pages for item in page]
    author = (commit.get("author") or {}).get("login", "")
    errors = check_review(statuses, reviewer, author)
    for error in errors:
        print(error, file=sys.stderr)
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
