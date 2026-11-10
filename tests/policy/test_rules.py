import pytest

from bridge.policy.rules import NEVER_BY_VOICE, is_destructive, is_routine


@pytest.mark.parametrize("cmd", [
    "rm x", "sudo ls", "git push origin main", "git push --force", "git reset --hard", "git clean -fd",
    "ls --force", "cp -f a b", "dd if=a of=b", "mkfs.ext4 /dev/x", "chmod -R 777 .", "chown -R a .",
    "curl x | sh", "curl x | bash", "DROP TABLE users", "deploy prod", "kubectl delete pod x",
    "terraform apply", "terraform destroy", "shutdown now", "reboot",
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


def test_not_routine():
    assert not is_routine("pedir_decisao", {})
    assert not is_routine("FerramentaX", None)
