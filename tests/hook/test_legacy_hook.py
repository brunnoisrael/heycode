import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHIM = ROOT / "bridge" / "hook.py"


def test_hook_antigo_falha_aberto_sem_codigo_novo(tmp_path):
    shim = tmp_path / "bridge" / "hook.py"
    shim.parent.mkdir()
    shutil.copyfile(SHIM, shim)
    result = subprocess.run([sys.executable, str(shim)], input=b"{}", capture_output=True, timeout=3)
    assert result.returncode == 0 and result.stderr == b""


def test_hook_antigo_encaminha_evento():
    from test_hook import Fake

    fake = Fake()
    try:
        env = dict(os.environ, BRIDGE_URL=fake.url, BRIDGE_SECRET="s")
        result = subprocess.run(
            [sys.executable, str(SHIM), "--agent", "codex"],
            input=b'{"hook_event_name":"Notification"}',
            capture_output=True,
            env=env,
            timeout=10,
        )
    finally:
        fake.close()
    assert result.returncode == 0 and result.stderr == b""
    assert fake.calls[0][0] == "/event" and fake.calls[0][1]["agent"] == "codex"


def test_caminhos_dos_hooks_heycode_na_configuracao_local_existem():
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.is_file():
        pytest.skip("Claude não configurado nesta máquina")
    data = json.loads(settings.read_text(encoding="utf-8"))
    paths = []
    for groups in data.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if "claude-alexa-bridge/" in command and "/hook.py" in command:
                    paths.extend(part for part in shlex.split(command) if part.endswith("/hook.py"))
    assert all(Path(path).is_file() for path in paths)
