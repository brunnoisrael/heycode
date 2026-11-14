def test_versao_2(config):
    assert config["version"] == 2


def test_gates_ativos_e_desligados(config):
    enabled = set(config["enabled_gates"])
    assert {"G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G13", "G14", "G15", "G16"} <= enabled
    assert "G9" not in enabled and "G10" not in enabled  # ligam na trilha P2
    assert "G12" not in enabled  # removido pelo ADR 0060
    assert "G11" not in enabled  # removido pelo ADR 0061


def test_sem_aprovacao_humana_por_caminho(config):
    for chave in ("protected_paths", "human_review_paths", "human_owners"):
        assert chave not in config


def test_pisos_numericos(config):
    assert "max_added_lines" not in config and "size_exclude_globs" not in config
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
