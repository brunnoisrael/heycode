import asyncio
import threading
import time


def test_answer_flow_and_separation(client):
    store = client.server.store
    result = {}
    worker = threading.Thread(target=lambda: result.update(asyncio.run(
        client.server._tools.pedir_resposta('Qual biblioteca?', 'codex', 'app'))))
    worker.start()
    for _ in range(100):
        if store.pending_approvals():
            break
        time.sleep(0.005)
    pending = client.get('/pending').json()
    aid = pending['approval_id']
    assert pending['kind'] == 'question'
    client.post('/decide', json={'approve': False, 'approval_id': aid})
    assert store.get_approval(aid)['decision'] is None
    body = {'approval_id': aid, 'text': 'Use SQLite'}
    preview = client.post('/answer/preview', json=body).json()
    assert preview['ok']
    confirmation = {'approval_id': aid, 'token': preview['token']}
    assert not client.post('/answer/confirm', json={'approval_id': aid, 'token': 'outro'}).json()['ok']
    assert client.post('/answer/confirm', json=confirmation).json()['ok']
    assert not client.post('/answer/confirm', json=confirmation).json()['ok']
    worker.join(3)
    assert result == {'answer': 'Use SQLite'}


def test_answer_rejects_expired_wrong_type_and_invalid_text(client):
    store = client.server.store
    aid = store.add_approval('a', 'p', 'Bash', 'ls', 's')
    assert not client.post('/answer/confirm', json={'approval_id': aid, 'token': 'invalid'}).json()['ok']
    store.resolve_approval(aid, 'expired')
    q = store.add_approval('a', 'p', 'pedir_resposta', 'qual?', 's')
    assert not client.post('/answer/preview', json={'approval_id': q, 'text': ' '}).json()['ok']
    assert not client.post('/answer/preview', json={'approval_id': q, 'text': 'a' * 301}).json()['ok']
    preview = client.post('/answer/preview', json={'approval_id': q, 'text': 'sim'}).json()
    time.sleep(1.05)
    assert not client.post('/answer/confirm', json={'approval_id': q, 'token': preview['token']}).json()['ok']


def test_answer_atomic_under_concurrency(client):
    store = client.server.store
    aid = store.add_approval('a', 'p', 'pedir_resposta', 'qual?', 's')
    results = []
    threads = [threading.Thread(target=lambda: results.append(store.answer_question(aid, 'x', 10))) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count(True) == 1


def test_restarting_expires_questions_and_preview_masks_secret(client):
    store = client.server.store
    aid = store.add_approval('a', 'p', 'pedir_resposta', 'qual?', 's')
    response = client.post('/answer/preview', json={'approval_id': aid, 'text': 'senha=hunter2'}).json()
    assert response['ok']
    assert 'hunter2' not in response['speech']
    store.expire_pending()
    assert not client.post('/answer/confirm', json={'approval_id': aid, 'token': response['token']}).json()['ok']
