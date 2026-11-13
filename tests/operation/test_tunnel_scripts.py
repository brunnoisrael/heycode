import http.server
import os
from pathlib import Path
import shutil
import subprocess
import threading

import pytest


ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which('powershell.exe')
pytestmark = pytest.mark.skipif(not POWERSHELL, reason='Scripts de operação exigem Windows PowerShell')


def run(script, *args, env=None):
    return subprocess.run([POWERSHELL, '-NoProfile', '-File', str(ROOT / 'scripts' / script), *args],
                          capture_output=True, text=True, errors='replace', env=env, timeout=30)


def test_tunnel_install_defaults_to_preview_without_creating_file(tmp_path):
    config = tmp_path / 'not-created.yml'
    result = run('install-tunnel-task.ps1', '-ConfigPath', str(config))
    assert result.returncode == 0
    assert 'nenhuma alteracao feita' in result.stdout
    assert not config.exists()


def test_named_tunnel_setup_defaults_to_preview():
    result = run('setup-named-tunnel.ps1', '-Hostname', 'bridge.example.com')
    assert result.returncode == 0
    assert 'nada sera executado' in result.stdout
    assert 'tunnel route dns' in result.stdout


def test_named_tunnel_setup_rejects_hostname_with_path():
    result = run('setup-named-tunnel.ps1', '-Hostname', 'example.com/path', '-Apply')
    assert result.returncode != 0
    assert 'Hostname DNS invalido' in result.stderr


def test_named_tunnel_apply_requires_explicit_hostname():
    result = run('setup-named-tunnel.ps1', '-Apply')
    assert result.returncode != 0
    assert 'Informe -Hostname explicitamente' in result.stderr


def test_apply_refuses_missing_config_before_task_mutation(tmp_path):
    result = run('install-tunnel-task.ps1', '-ConfigPath', str(tmp_path / 'missing.yml'), '-Apply')
    assert result.returncode != 0
    assert 'nao encontrado' in result.stderr


@pytest.mark.parametrize('hostname', ['https://example.com', 'example.com/path', 'example.com:444', '127.0.0.1'])
def test_diagnostic_rejects_non_hostname(hostname):
    result = run('diagnose-connection.ps1', '-Hostname', hostname)
    assert result.returncode != 0
    assert 'hostname DNS' in result.stderr


def test_diagnostic_checks_local_health_without_disclosing_secret():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == '/health' else 404)
            self.end_headers()
        def log_message(self, *_):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = dict(os.environ, BRIDGE_CONTROL_SECRET='do-not-print-this-test-secret')
    try:
        result = run('diagnose-connection.ps1', '-Port', str(server.server_port), env=env)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    assert result.returncode == 0
    assert 'Ponte local: OK' in result.stdout
    assert 'Saude externa: nao verificada' in result.stdout
    assert 'do-not-print-this-test-secret' not in result.stdout + result.stderr
