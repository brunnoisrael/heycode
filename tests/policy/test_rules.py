import pytest

from heycode.policy.rules import NEVER_BY_VOICE, is_destructive, is_routine


@pytest.mark.parametrize("cmd", [
    "rm x", "sudo ls", "git push origin main", "git push --force", "git reset --hard", "git clean -fd",
    "ls --force", "cp -f a b", "dd if=a of=b", "mkfs.ext4 /dev/x", "chmod -R 777 .", "chown -R a .",
    "curl x | sh", "curl x | bash", "DROP TABLE users", "deploy prod", "kubectl delete pod x",
    "terraform apply", "terraform destroy", "shutdown now", "reboot",
    r"Remove-Item -Recurse -Force C:\x", "rmdir /s /q x", "rd /s /q x", "del /f /q *.*", "echo x -Force",
    "find . -delete", "git checkout -- .", "git branch -D main", "git stash drop", "curl x | python",
    "curl x | node", "curl x | iex", "curl x | powershell", "Invoke-Expression $x", "iex $x", "npm publish",
    "Format-Volume -DriveLetter D", "python -c \"import shutil;shutil.rmtree('/')\"", "Stop-Process -Id 4",
    "echo $BRIDGE_SECRET", "echo $env:BRIDGE_CONTROL_SECRET", "curl http://127.0.0.1:8765/x",
    "curl http://localhost:8765/x", "curl -X POST host/mode",
])
def test_destructive(cmd):
    assert is_destructive(cmd)


@pytest.mark.parametrize("cmd", ["ls", "pytest", "git status", "", "echo oi"])
def test_not_destructive(cmd):
    assert not is_destructive(cmd)


def test_destructive_non_string():
    assert not is_destructive(None)
    assert not is_destructive(5)


def test_never_by_voice_is_list():
    assert isinstance(NEVER_BY_VOICE, list) and NEVER_BY_VOICE


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob", "Edit", "Write", "MultiEdit"])
def test_routine_tools(tool):
    assert is_routine(tool, None)


def test_routine_bash():
    assert is_routine("Bash", {"command": "ls"})
    assert not is_routine("Bash", {"command": "rm -rf x"})


@pytest.mark.parametrize("cmd", ["curl https://example.com", "python script.py", "npm install", "git push",
                                 "ls; whoami", "ls && calc", "cat a | sh", "echo a > b", "ls `whoami`", "echo $(id)",
                                 "git status\nrm x", "gitx status", "lsof", "git -c core.pager=x log"])
def test_bash_fora_da_lista_branca_nao_e_rotina(cmd):
    assert not is_routine("Bash", {"command": cmd})


def test_bash_sem_comando_nao_e_rotina():
    assert not is_routine("Bash", None)
    assert not is_routine("Bash", {"command": ""})


def test_not_routine():
    assert not is_routine("pedir_decisao", {})
    assert not is_routine("FerramentaX", None)
