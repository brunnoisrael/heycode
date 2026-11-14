"""Niveis de apoio e os limites de cada um (ADR 0059). O relay nao cobra: o nivel e concedido pelo dono."""

from dataclasses import dataclass

FREE = "livre"


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    tagline: str
    suggested: int  # contribuicao sugerida, em reais por mes; so para exibir
    installations: int
    shortcuts: int
    daily_quota: int


PLANS: dict[str, Plan] = {
    FREE: Plan(FREE, "Livre", "Tudo o que o HeyCode faz hoje, sem pagar nada.", 0, 2, 30, 200),
    "apoiador": Plan(
        "apoiador", "Apoiador", "Ajuda a manter o relay no ar e ganha folga nos limites.", 15, 4, 100, 1000
    ),
    "patrono": Plan("patrono", "Patrono", "Banca o projeto e usa sem pensar em limite.", 45, 8, 300, 3000),
}
PAID = tuple(key for key in PLANS if key != FREE)


def limits_for(plan: str, base_quota: int) -> dict:
    """Limites do nivel. No nivel livre a cota diaria e a configurada no relay (`RELAY_DAILY_QUOTA`)."""
    p = PLANS.get(plan, PLANS[FREE])
    quota = base_quota if p.key == FREE else max(p.daily_quota, base_quota)
    return {"installations": p.installations, "shortcuts": p.shortcuts, "daily_quota": quota}


def tiers(base_quota: int) -> list[dict]:
    """Lista para exibir, do mais simples ao mais generoso."""
    return [
        {"key": p.key, "name": p.name, "tagline": p.tagline, "suggested": p.suggested, **limits_for(p.key, base_quota)}
        for p in PLANS.values()
    ]
