from secret_scan import scan_diff, scan_text

# Tokens falsos montados em tempo de execucao para o proprio repositorio nao disparar o gate.
AWS = "AKIA" + "IOSFODNN7EXAMPLE"
GH = "ghp_" + "a1B2c3D4" * 5
SLACK = "xoxb-" + "1234567890-" + "abcdefghijklmnop"
PRIV = "-----BEGIN " + "RSA PRIVATE KEY-----"
SECRET = "BRIDGE_SECRET=" + "k9Xv2LmQ8rTz4WnB7yHc1JdF5gSa3PeU"


def test_chave_aws_e_detectada():
    assert scan_text("a.py", f'key = "{AWS}"')


def test_token_github_e_detectado():
    assert scan_text("a.txt", f"token {GH}")


def test_token_slack_e_detectado():
    assert scan_text("a.txt", SLACK)


def test_chave_privada_e_detectada():
    assert scan_text("k.pem", PRIV)


def test_atribuicao_de_segredo_longo_e_detectada():
    assert scan_text(".env", SECRET)


def test_bearer_longo_e_detectado():
    assert scan_text("a.sh", "curl -H 'Authorization: Bearer " + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4" + "'")


def test_placeholder_nao_e_segredo():
    assert scan_text("a.md", "BRIDGE_SECRET=<seu-segredo-aqui>") == []
    assert scan_text("a.md", "BRIDGE_SECRET=changeme-changeme-changeme-changeme") == []
    assert scan_text("a.md", "BRIDGE_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") == []


def test_leitura_de_variavel_de_ambiente_nao_e_segredo():
    assert scan_text("index.js", "const SECRET = process.env.BRIDGE_CONTROL_SECRET || '';") == []
    assert scan_text("a.py", "SECRET = os.environ.get('BRIDGE_SECRET_VALUE_X')") == []


def test_nome_sem_valor_nao_e_segredo():
    assert scan_text("a.md", "BRIDGE_SECRET (minimo de 32 caracteres)") == []
    assert scan_text("a.py", 'os.environ["BRIDGE_SECRET"]') == []


def test_marcador_de_permissao_na_linha_libera():
    assert scan_text("a.txt", SECRET + "  # gate:allow-secret") == []


def test_mensagem_nao_vaza_o_valor():
    msgs = scan_text(".env", SECRET)
    assert msgs and all("k9Xv2LmQ8rTz4WnB7yHc1JdF5gSa3PeU" not in m for m in msgs)


def test_scan_diff_so_olha_linhas_adicionadas():
    diff = f"diff --git a/.env b/.env\n+++ b/.env\n@@ -1 +1,2 @@\n-{SECRET}\n+X=1\n+{SECRET}\n"
    found = scan_diff(diff)
    assert len(found) == 1 and ".env" in found[0]


def test_scan_diff_sem_segredo_passa():
    assert scan_diff("diff --git a/a b/a\n+++ b/a\n@@ -0,0 +1 @@\n+print('oi')\n") == []
