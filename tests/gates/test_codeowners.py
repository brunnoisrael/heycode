from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"


def _parse():
    rules = {}
    for raw in CODEOWNERS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pattern, *owners = line.split()
        glob = pattern.lstrip("/")
        if glob.endswith("/"):
            glob += "**"
        rules[glob] = set(owners)
    return rules


def test_codeowners_espelha_gates_json(config):
    expected = set(config["protected_paths"]) | set(config["human_review_paths"])
    assert set(_parse()) == expected


def test_donos_do_codeowners_sao_os_donos_humanos(config):
    owners = {"@" + o for o in config["human_owners"]}
    for glob, who in _parse().items():
        assert who == owners, glob
