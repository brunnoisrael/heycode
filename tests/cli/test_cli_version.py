import tomllib
from pathlib import Path

from heycode import __version__
from heycode.cli import main

ROOT = Path(__file__).resolve().parents[2]


def test_version_imprime_a_versao(capsys):
    assert main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_versao_inicial():
    assert __version__ == "0.1.0"


def test_sem_argumentos_mostra_ajuda_e_retorna_2(capsys):
    assert main([]) == 2
    captured = capsys.readouterr()
    assert "usage" in (captured.out + captured.err).lower()


def test_pyproject_declara_faixa_de_python():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "heycode"
    assert data["project"]["requires-python"] == ">=3.11,<3.15"
    assert data["project"]["scripts"]["heycode"] == "heycode.cli:main"
