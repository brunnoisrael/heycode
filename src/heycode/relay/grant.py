"""Concede niveis de apoio e lista quem pediu (ADR 0059). Roda no servidor; nenhuma rota HTTP faz isto.

python -m heycode.relay.grant set EMAIL NIVEL    # livre | apoiador | patrono
python -m heycode.relay.grant interest           # quem marcou "quero apoiar" no painel
"""

import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence

from heycode.relay.plans import PLANS
from heycode.relay.repo import SqliteRepository

USAGE = "uso: python -m heycode.relay.grant set EMAIL NIVEL | interest"


def run(argv: Sequence[str], repo, out: Callable[[str], None] = print, clock: Callable[[], float] = time.time) -> int:
    if len(argv) == 3 and argv[0] == "set":
        email, plan = argv[1].strip().lower(), argv[2]
        if plan not in PLANS:
            out(f"nivel desconhecido: {plan} (use {', '.join(PLANS)})")
            return 2
        account = repo.get_account_by_email(email)
        if account is None:
            out(f"nenhuma conta com o e-mail {email}")
            return 1
        repo.set_plan(account["id"], plan, clock())
        repo.add_audit(account["id"], clock(), "dono:conceder_nivel", "ok", label=plan)
        out(f"{email} agora e {PLANS[plan].name}")
        return 0
    if len(argv) == 1 and argv[0] == "interest":
        rows = repo.list_plan_interest()
        for row in rows:
            out(f"{row['email']}\tquer {row['interest']}\t(hoje: {row['plan']})")
        out(f"{len(rows)} pedido(s) de apoio")
        return 0
    out(USAGE)
    return 2


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    db = (os.environ if env is None else env).get("RELAY_DB")
    if not db:
        print("defina RELAY_DB com o caminho do banco do relay")
        return 2
    return run(sys.argv[1:] if argv is None else argv, SqliteRepository(db))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
