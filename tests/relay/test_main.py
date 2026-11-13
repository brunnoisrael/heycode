import pytest
from fastapi.testclient import TestClient

from heycode.relay.main import build_app


def test_app_sobe_com_banco_configurado_e_responde_health(tmp_path):
    app = build_app({"RELAY_DB": str(tmp_path / "relay.db")})
    assert TestClient(app).get("/health").json() == {"ok": True}
    assert (tmp_path / "relay.db").exists()


def test_sem_banco_configurado_recusa_subir_em_vez_de_perder_dados():
    with pytest.raises(RuntimeError) as e:
        build_app({})
    assert "RELAY_DB" in str(e.value)


def test_cotas_podem_ser_ajustadas_por_ambiente(tmp_path):
    app = build_app({"RELAY_DB": str(tmp_path / "r.db"), "RELAY_DAILY_QUOTA": "7", "RELAY_SYNC_TIMEOUT": "2.5"})
    assert TestClient(app).get("/health").status_code == 200
    with pytest.raises(ValueError):
        build_app({"RELAY_DB": str(tmp_path / "r2.db"), "RELAY_DAILY_QUOTA": "muitas"})


def test_oauth_so_liga_com_cliente_segredo_e_redirects(tmp_path):
    base = {"RELAY_DB": str(tmp_path / "r.db")}
    with pytest.raises(RuntimeError):
        build_app({**base, "OAUTH_CLIENT_ID": "x"})
    app = build_app(
        {
            **base,
            "OAUTH_CLIENT_ID": "x",
            "OAUTH_CLIENT_SECRET": "y",
            "OAUTH_REDIRECT_URIS": "https://a.example/cb, https://b.example/cb",
        }
    )
    r = TestClient(app).get("/oauth/authorize", params={"client_id": "x", "redirect_uri": "https://b.example/cb"})
    assert r.status_code == 200
