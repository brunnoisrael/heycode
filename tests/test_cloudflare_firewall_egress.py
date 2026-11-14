"""Cloudflare filtering must not block HTTPS initiated by Docker containers."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"), reason="requires bash")
def test_outbound_bridges_return_before_public_allowlist(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "rules"
    scripts = {
        "id": "#!/bin/sh\necho 0\n",
        "ufw": "#!/bin/sh\nexit 0\n",
        "iptables": '#!/bin/sh\necho "$(basename "$0") $*" >> "$RULE_LOG"\n[ "$1" != "-D" ]\n',
    }
    for name, content in scripts.items():
        path = tools / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
    (tools / "ip6tables").symlink_to(tools / "iptables")
    env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"], "RULE_LOG": str(log)}
    subprocess.run(["bash", str(ROOT / "infra/vps/cloudflare-firewall.sh"), "apply"], env=env, check=True)
    rules = log.read_text(encoding="utf-8").splitlines()
    for tool in ("iptables", "ip6tables"):
        chain = [line for line in rules if line.startswith(f"{tool} -A HEYCODE-WEB ")]
        assert chain[0].endswith("-i docker0 -j RETURN")
        assert chain[1].endswith("-i br+ -j RETURN")
        assert any(" -s " in line and line.endswith("-j RETURN") for line in chain)
        assert chain[-1].endswith("-j DROP")
