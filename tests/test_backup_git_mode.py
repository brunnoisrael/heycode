"""The systemd backup service executes its script directly."""

import subprocess
from pathlib import Path


def test_backup_script_is_executable_in_git():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", "infra/vps/backup.sh"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.startswith("100755 ")
