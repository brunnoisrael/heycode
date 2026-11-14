from evidence import check_evidence

FENCE = chr(96) * 3


def body(evidence, tail="\n## Checklist\n- [ ] x\n"):
    return "## O que muda\n\nx\n\n## Evidência\n\n" + evidence + tail


def block(text):
    return FENCE + "\n" + text + "\n" + FENCE + "\n"


def test_evidencia_com_comando_e_saida_passa():
    assert check_evidence(body(block("$ python -m pytest -q\n638 passed in 71s"))) == []


def test_secao_ausente_falha():
    assert check_evidence("texto qualquer")


def test_secao_sem_bloco_de_codigo_falha():
    assert check_evidence(body("rodei os testes e passaram todos, confia\n"))


def test_bloco_so_com_o_comando_do_modelo_falha():
    assert check_evidence(body(block("$ python -m pytest -q")))


def test_secao_vazia_falha():
    assert check_evidence(body(""))


def test_aceita_heading_sem_acento():
    text = "## Evidencia\n\n" + block("$ x\nok ok ok ok ok ok")
    assert check_evidence(text) == []


def test_corpo_vazio_falha():
    assert check_evidence("")
