import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from bridge.projects.activity import make_router
from bridge.store.db import Store


def auth(x_secret: str = Header(default='')):
    if x_secret != 'controle':
        raise HTTPException(401)


def make_client(tmp_path):
    store = Store()
    app = FastAPI()
    app.include_router(make_router(store, auth, str(tmp_path)))
    return TestClient(app, headers={'x-secret': 'controle'}), store


def test_listagem_e_status_preservam_sigilo_e_diferenciam_sessao(tmp_path):
    c, store = make_client(tmp_path)
    (tmp_path / 'painel').mkdir()
    run = store.create_run('codex', 'painel', 'senha=supersecreta', str(tmp_path / 'painel'))
    store.upsert_session('s1', 'claude', 'painel', 'trabalhando', 'token=segredo', None)
    body = c.get('/voice/projects').json()
    assert body['ok'] and body['next_offset'] is None
    assert body['projects'][0]['running'] == [{'id': run, 'agent': 'codex', 'status': 'rodando'}]
    assert 'atividade recente' in body['speech']
    assert 'senha' not in str(body) and 'segredo' not in str(body) and str(tmp_path) not in str(body)
    assert c.get('/voice/projects/status', params={'project': 'painel'}).json()['ok']
    assert TestClient(c.app).get('/voice/projects').status_code == 401


def test_paginacao_e_estado_antigo(tmp_path):
    c, store = make_client(tmp_path)
    for name in ('um', 'dois', 'tres', 'quatro'):
        (tmp_path / name).mkdir()
        store.create_run('codex', name, 'x', str(tmp_path / name))
    store.upsert_session('old', 'claude', 'um', 'trabalhando')
    with store._lock:
        store._db.execute('UPDATE sessions SET updated=? WHERE session_id=?', (time.time() - 4000, 'old'))
        store._db.commit()
    first = c.get('/voice/projects').json()
    second = c.get('/voice/projects', params={'offset': first['next_offset']}).json()
    assert len(first['projects']) == 3 and len(second['projects']) == 1
    assert second['next_offset'] is None
    assert all(not x['recent_sessions'] for x in first['projects'] + second['projects'])
    assert c.get('/voice/projects', params={'offset': -1}).status_code == 422


def test_resolucao_recusa_colisoes_e_caminhos(tmp_path):
    c, store = make_client(tmp_path)
    (tmp_path / 'meu-app').mkdir()
    assert c.get('/voice/projects/resolve', params={'name': 'meu app'}).json()['project'] == 'meu-app'
    assert not c.get('/voice/projects/resolve', params={'name': '../meu-app'}).json()['ok']
    (tmp_path / 'meu app').mkdir()
    assert not c.get('/voice/projects/resolve', params={'name': 'meu app'}).json()['ok']
    store.upsert_session('s', 'claude', 'meu-app', 'trabalhando')
    assert c.get('/voice/projects').json()['projects'] == []


def test_raiz_indisponivel_e_projecto_sem_atividade(tmp_path):
    c, _ = make_client(tmp_path)
    (tmp_path / 'novo').mkdir()
    assert 'nenhuma atividade' in c.get('/voice/projects/status', params={'project': 'novo'}).json()['speech']
    (tmp_path / 'novo').rmdir()
    assert not c.get('/voice/projects/resolve', params={'name': 'novo'}).json()['ok']
    tmp_path.rmdir()
    assert not c.get('/voice/projects').json()['ok']
