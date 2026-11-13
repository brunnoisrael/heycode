from diff_coverage import check_coverage, parse_added_lines


def cov(files):
    return {"files": files}


def entry(executed, missing, missing_branches=()):
    return {
        "executed_lines": sorted(executed),
        "missing_lines": sorted(missing),
        "missing_branches": [list(b) for b in missing_branches],
    }


def test_parse_added_lines_le_intervalos_do_diff():
    diff = (
        "diff --git a/bridge/a.py b/bridge/a.py\n"
        "+++ b/bridge/a.py\n"
        "@@ -1,0 +2,3 @@\n"
        "+a\n+b\n+c\n"
        "@@ -10 +20 @@\n"
        "+d\n"
        "diff --git a/README.md b/README.md\n"
        "+++ b/README.md\n"
        "@@ -0,0 +1 @@\n"
        "+x\n"
    )
    assert parse_added_lines(diff)["bridge/a.py"] == {2, 3, 4, 20}


def test_tudo_coberto_passa(config):
    added = {"bridge/a.py": {1, 2, 3}}
    assert check_coverage(added, cov({"bridge/a.py": entry({1, 2, 3}, set())}), config) == []


def test_cobertura_abaixo_do_piso_falha(config):
    added = {"bridge/a.py": set(range(1, 11))}
    c = cov({"bridge/a.py": entry(set(range(1, 9)), {9, 10})})  # 80%
    errs = check_coverage(added, c, config)
    assert errs and errs[0].startswith("G7")


def test_exatamente_no_piso_passa(config):
    added = {"bridge/a.py": set(range(1, 11))}
    c = cov({"bridge/a.py": entry(set(range(1, 10)), {10})})  # 90%
    assert check_coverage(added, c, config) == []


def test_linhas_nao_executaveis_sao_ignoradas(config):
    added = {"bridge/a.py": {1, 2, 3}}  # 2 e 3 sao comentario/branco: fora do relatorio
    assert check_coverage(added, cov({"bridge/a.py": entry({1}, set())}), config) == []


def test_sem_linha_executavel_nova_passa(config):
    assert check_coverage({"docs/x.md": {1, 2}}, cov({}), config) == []


def test_arquivo_de_codigo_ausente_do_relatorio_falha(config):
    errs = check_coverage({"bridge/novo.py": {1, 2}}, cov({}), config)
    assert errs and "bridge/novo.py" in errs[0]


def test_ramo_nao_coberto_na_politica_falha(config):
    added = {"bridge/policy/engine.py": {5, 6}}
    c = cov({"bridge/policy/engine.py": entry({5, 6}, set(), missing_branches=[(6, 9)])})
    errs = check_coverage(added, c, config)
    assert any("ramo" in e for e in errs)


def test_ramo_nao_coberto_fora_das_linhas_tocadas_passa(config):
    added = {"bridge/policy/engine.py": {5}}
    c = cov({"bridge/policy/engine.py": entry({5, 40}, set(), missing_branches=[(40, 41)])})
    assert check_coverage(added, c, config) == []


def test_ramo_nao_coberto_fora_da_politica_passa(config):
    added = {"bridge/a.py": {6}}
    c = cov({"bridge/a.py": entry({6}, set(), missing_branches=[(6, 9)])})
    assert check_coverage(added, c, config) == []


def test_relatorio_do_windows_com_barra_invertida(config):
    added = {"bridge/policy/engine.py": {5, 6}}
    c = cov({"bridge" + chr(92) + "policy" + chr(92) + "engine.py": entry({5, 6}, set())})
    assert check_coverage(added, c, config) == []
