from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "DEPLOY-ALEXA.md",
    ROOT / "docs" / "QUICKSTART.md",
    ROOT / "docs" / "OPERATIONS.md",
]
REMOVIDOS = ("run-bridge.ps1", "install-service.ps1", "uninstall-service.ps1", "rotate-secret.ps1", "bridge/hook.py")
SUBCOMANDOS = ("init", "serve", "hook", "install-service", "uninstall-service", "rotate-secret", "doctor")


def test_docs_ativas_existem():
    for doc in ACTIVE:
        assert doc.is_file(), doc


def test_docs_nao_citam_caminhos_removidos():
    for doc in ACTIVE:
        text = doc.read_text(encoding="utf-8").replace(chr(92), "/")
        for removed in REMOVIDOS:
            assert removed not in text, f"{doc.name} cita {removed}"


def test_docs_nao_citam_o_requirements_nem_o_diretorio_bridge():
    for doc in ACTIVE:
        text = doc.read_text(encoding="utf-8").replace(chr(92), "/")
        assert "bridge/requirements.txt" not in text, doc.name
        assert "(`bridge/policy`)" not in text, doc.name


def test_quickstart_cita_todos_os_subcomandos():
    text = (ROOT / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")
    for sub in SUBCOMANDOS:
        assert f"heycode {sub}" in text, sub


def test_operations_cobre_reiniciar_rotacionar_e_recuperar():
    text = (ROOT / "docs" / "OPERATIONS.md").read_text(encoding="utf-8").lower()
    for topic in ("reiniciar", "rotacionar", "recuperar", "doctor"):
        assert topic in text, topic


def test_exemplo_de_hooks_usa_o_cli():
    text = (ROOT / "docs" / "claude-settings.example.json").read_text(encoding="utf-8")
    assert "heycode hook" in text and "bridge/hook.py" not in text


def test_readme_aponta_para_o_quickstart():
    assert "docs/QUICKSTART.md" in (ROOT / "README.md").read_text(encoding="utf-8")
