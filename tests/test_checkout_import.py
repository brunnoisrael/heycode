"""A suíte deve testar o checkout atual, mesmo com outro no ambiente Python."""

import os
import subprocess
import sys
from pathlib import Path


def test_pytest_prioriza_codigo_do_checkout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    other = tmp_path / "outro"
    package = other / "heycode"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("raise RuntimeError('checkout antigo')\n", encoding="utf-8")
    probe = tmp_path / "test_origem.py"
    probe.write_text(
        "from pathlib import Path\n"
        "import heycode\n"
        f"def test_origem(): assert Path(heycode.__file__).resolve().is_relative_to(Path({str(root / 'src')!r}))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(other)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-c", str(root / "pyproject.toml"), str(probe)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
