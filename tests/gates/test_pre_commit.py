from pre_commit import check_staged


def test_mudanca_de_arquitetura_sem_adr_falha(config):
    assert check_staged([("M", "src/heycode/policy/engine.py")], config)


def test_com_novo_adr_passa(config):
    staged = [("M", "src/heycode/policy/engine.py"), ("A", "docs/adr/0003-x.md")]
    assert check_staged(staged, config) == []


def test_adr_existente_modificado_nao_basta(config):
    staged = [("M", "src/heycode/policy/engine.py"), ("M", "docs/adr/0001-x.md")]
    assert check_staged(staged, config)


def test_template_nao_conta_como_adr(config):
    staged = [("M", "src/heycode/policy/engine.py"), ("A", "docs/adr/0000-template.md")]
    assert check_staged(staged, config)


def test_remocao_de_arquivo_de_arquitetura_exige_adr(config):
    assert check_staged([("D", "src/heycode/mcp_server/server.py")], config)


def test_renomeacao_exige_adr(config):
    staged = [("D", "src/heycode/store/a.py"), ("A", "src/heycode/store/b.py")]
    assert check_staged(staged, config)


def test_fora_da_lista_nao_exige(config):
    assert check_staged([("M", "README.md")], config) == []
