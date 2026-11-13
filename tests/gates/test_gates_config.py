def test_versao_2(config):
    assert config["version"] == 2


def test_gates_ativos_e_desligados(config):
    enabled = set(config["enabled_gates"])
    assert {"G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G11", "G12", "G13", "G14", "G15", "G16"} <= enabled
    assert "G9" not in enabled and "G10" not in enabled  # ligam na trilha P2


def test_caminhos_protegidos_cobrem_a_esteira(config):
    protected = set(config["protected_paths"])
    for p in ("scripts/gates/**", ".githooks/**", ".github/**", "AGENTS.md", "CLAUDE.md", ".claude/**", "docs/SDLC.md"):
        assert p in protected


def test_caminhos_de_revisao_humana_cobrem_o_nucleo_sensivel(config):
    human = set(config["human_review_paths"])
    for p in (
        "src/heycode/policy/**",
        "src/heycode/store/**",
        "src/heycode/mcp_server/**",
        "src/heycode/supervisor/**",
        "skill/lambda/**",
        "docs/superpowers/specs/**",
    ):
        assert p in human


def test_pisos_numericos(config):
    assert config["max_added_lines"] == 400
    assert config["diff_coverage_floor"] == 90
    assert config["policy_branch_coverage_floor"] == 100


def test_arquitetura_ampliada_e_mantem_a_anterior(config):
    arch = set(config["architecture_paths"])
    assert {
        "src/heycode/policy/*",
        "src/heycode/mcp_server/*",
        "src/heycode/supervisor/*",
        "src/heycode/store/*",
    } <= arch
    assert {"relay/*", "protocol/*", "infra/*"} <= arch


def test_regex_de_status_aprovado_compila(config):
    import re

    assert re.compile(config["approved_status_regex"], re.IGNORECASE).match("Status: aprovada pelo dono")


def test_donos_humanos_configurados(config):
    assert config["human_owners"] and all(isinstance(o, str) and o for o in config["human_owners"])
