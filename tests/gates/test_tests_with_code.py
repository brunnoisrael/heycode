from pre_commit import check_tests_with_code, local_warnings


def test_aviso_local_traz_g4_e_nao_limita_tamanho(config):
    warns = local_warnings(["src/heycode/a.py"], config)
    assert any(w.startswith("G4") for w in warns) and not any(w.startswith("G12") for w in warns)


def test_aviso_local_vazio_quando_tudo_certo(config):
    files = ["src/heycode/a.py", "tests/test_a.py"]
    assert local_warnings(files, config) == []


def test_feat_com_codigo_sem_teste_falha(config):
    assert check_tests_with_code(["src/heycode/policy/engine.py"], "feat", config)


def test_fix_com_codigo_e_teste_passa(config):
    files = ["src/heycode/policy/engine.py", "tests/policy/test_engine.py"]
    assert check_tests_with_code(files, "fix", config) == []


def test_teste_da_lambda_conta_como_teste(config):
    files = ["skill/lambda/index.js", "skill/lambda/test/index.test.js"]
    assert check_tests_with_code(files, "feat", config) == []


def test_docs_e_chore_sao_isentos(config):
    assert check_tests_with_code(["src/heycode/policy/engine.py"], "docs", config) == []
    assert check_tests_with_code(["src/heycode/policy/engine.py"], "chore", config) == []


def test_apenas_teste_ou_doc_passa(config):
    assert check_tests_with_code(["tests/a/test_x.py", "docs/x.md"], "feat", config) == []


def test_node_modules_nao_conta_como_codigo(config):
    assert check_tests_with_code(["skill/lambda/node_modules/x/index.js"], "feat", config) == []


def test_refactor_e_test_nao_exigem_teste_novo(config):
    assert check_tests_with_code(["src/heycode/store/db.py"], "refactor", config) == []
    assert check_tests_with_code(["src/heycode/store/db.py"], "test", config) == []
