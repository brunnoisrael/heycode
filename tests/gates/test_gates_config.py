def test_versao_2(config):
    assert config["version"] == 2


def test_gates_ativos_e_desligados(config):
    enabled = set(config["enabled_gates"])
    assert {"G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G13", "G14", "G16"} <= enabled
    assert "G12" not in enabled
    assert "G9" not in enabled and "G10" not in enabled  # ligam na trilha P2


def test_pisos_numericos(config):
    assert "max_added_lines" not in config
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


def test_revisoes_de_pr_nao_sao_gates(config):
    assert not {"G11", "G15"} & set(config["enabled_gates"])


def test_ci_nao_exige_revisao_de_pr():
    from pathlib import Path

    workflows = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    assert not (workflows / "agent-review.yml").exists()
    assert "human-approval:" not in (workflows / "ci.yml").read_text(encoding="utf-8")
