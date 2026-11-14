from pathlib import Path

from heycode.templates import template_root


def test_template_root_tem_gates_e_hooks():
    root = Path(template_root())
    assert (root / "scripts" / "gates" / "commit_msg.py").is_file()
    assert (root / ".githooks" / "commit-msg").is_file()


def test_template_root_prefere_o_diretorio_do_pacote(tmp_path, monkeypatch):
    pkg = tmp_path / "heycode"
    (pkg / "_template" / "scripts" / "gates").mkdir(parents=True)
    (pkg / "_template" / ".githooks").mkdir()
    import heycode.templates as t

    monkeypatch.setattr(t, "__file__", str(pkg / "templates.py"))
    assert Path(t.template_root()) == (pkg / "_template").resolve()
