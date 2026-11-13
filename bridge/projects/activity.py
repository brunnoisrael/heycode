"""Visibilidade por voz de projetos e execuções sem expor prompts ou caminhos."""
import os
import time
import unicodedata
from html import escape

from fastapi import APIRouter, Depends, Query

try:
    from policy.redact import mask_secrets
except ImportError:  # uso pelo pacote bridge nos testes
    from bridge.policy.redact import mask_secrets

PAGE_SIZE = 3
SESSION_WINDOW = 1800


def _key(value):
    if '/' in str(value) or '\\' in str(value):
        return ''
    text = unicodedata.normalize('NFKD', str(value).casefold())
    return ''.join(c for c in text if c.isalnum())


def _agent(value):
    name = str(value or '').casefold()
    return name if name in ('claude', 'codex', 'aider') else 'agente'


def _directories(root):
    """Apenas diretórios imediatos com destino real dentro da raiz."""
    root = os.path.realpath(root)
    try:
        with os.scandir(root) as entries:
            result = []
            for e in entries:
                name = e.name
                if not name or mask_secrets(name) != name or not _key(name):
                    continue
                real = os.path.realpath(e.path)
                try:
                    inside = os.path.commonpath([root, real]) == root and real != root
                    if inside and e.is_dir():
                        result.append(name)
                except (ValueError, OSError):
                    continue
            return sorted(result, key=lambda x: (x.casefold(), x))
    except OSError:
        return None


def _resolve(names, name):
    key = _key(name)
    matches = [n for n in names if _key(n) == key] if key else []
    return matches[0] if len(matches) == 1 else None


def _gather(store, names, now):
    runs, sessions = store.activity_snapshot(now - SESSION_WINDOW)
    groups = {}
    for row in runs:
        project = _resolve(names, row['project'] or '')
        if not project:
            continue
        group = groups.setdefault(project, {'project': project, 'running': [], 'recent_sessions': [], '_time': 0})
        group['running'].append({'id': row['id'], 'agent': _agent(row['agent']), 'status': 'rodando'})
        group['_time'] = max(group['_time'], row['t_start'] or 0)
    for row in sessions:
        project = _resolve(names, row['project'] or '')
        if not project or row['updated'] > now + 60:
            continue
        group = groups.setdefault(project, {'project': project, 'running': [], 'recent_sessions': [], '_time': 0})
        status = row['status'] if row['status'] in ('trabalhando', 'aguardando', 'concluido', 'parado') else 'registrado'
        group['recent_sessions'].append({'agent': _agent(row['agent']), 'status': status, 'updated': row['updated']})
        group['_time'] = max(group['_time'], row['updated'])
    return sorted(groups.values(), key=lambda g: (-g['_time'], g['project'].casefold(), g['project']))


def _describe(group, now):
    running, sessions = group['running'], group['recent_sessions']
    parts = []
    if running:
        names = ', '.join(f"{r['agent']} número {r['id']}" for r in running[:3])
        extra = f" e mais {len(running) - 3}" if len(running) > 3 else ''
        unit = 'execução' if len(running) == 1 else 'execuções'
        parts.append(f"{len(running)} {unit} em andamento: {names}{extra}")
    if sessions:
        age = max(0, int((now - sessions[0]['updated']) // 60))
        when = 'há menos de um minuto' if age == 0 else f'há {age} minutos'
        parts.append(f"atividade recente de {sessions[0]['agent']} {when}")
    return f"{escape(mask_secrets(group['project']))}: " + '; '.join(parts) + '.'


def make_router(store, auth, projects_root, clock=time.time):
    router = APIRouter(dependencies=[Depends(auth)], prefix='/voice/projects')

    @router.get('')
    def list_projects(offset: int = Query(default=0, ge=0, le=100000)):
        names = _directories(projects_root)
        if names is None:
            return {'ok': False, 'speech': 'Não consegui acessar a pasta de projetos.', 'projects': [], 'next_offset': None}
        now = clock()
        groups = _gather(store, names, now)
        page = groups[offset:offset + PAGE_SIZE]
        more = offset + len(page) if offset + len(page) < len(groups) else None
        for item in page:
            item.pop('_time')
        if not page:
            speech = 'Não há mais projetos com atividade recente.' if offset else 'Não há projetos com atividade recente.'
        else:
            speech = ' '.join(_describe(item, now) for item in page)
            if more is not None:
                speech += ' Diga mais para ouvir os próximos.'
        return {'ok': True, 'speech': mask_secrets(speech), 'projects': page, 'next_offset': more}

    @router.get('/resolve')
    def resolve_project(name: str = Query(min_length=1, max_length=120)):
        names = _directories(projects_root)
        if names is None:
            return {'ok': False, 'project': None, 'speech': 'Não consegui acessar a pasta de projetos.'}
        matches = [n for n in names if _key(n) == _key(name) and _key(name)]
        if len(matches) > 1:
            return {'ok': False, 'project': None, 'speech': 'Encontrei projetos com nomes parecidos. Escolha outro nome.'}
        if not matches:
            return {'ok': False, 'project': None, 'speech': 'Não encontrei esse projeto.'}
        return {'ok': True, 'project': matches[0], 'speech': f'Projeto {escape(mask_secrets(matches[0]))} selecionado.'}

    @router.get('/status')
    def project_status(project: str = Query(min_length=1, max_length=120)):
        result = resolve_project(project)
        if not result['ok']:
            return result
        now = clock()
        groups = _gather(store, _directories(projects_root) or [], now)
        group = next((x for x in groups if x['project'] == result['project']), None)
        speech = _describe(group, now) if group else f"{escape(result['project'])}: nenhuma atividade recente registrada."
        return {'ok': True, 'project': result['project'], 'speech': mask_secrets(speech)}

    return router
