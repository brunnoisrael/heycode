"""Supervisor: roda agentes como processos filhos e guarda o resultado (ADR 0007)."""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading

from heycode.policy.redact import mask_secrets
from heycode.supervisor.failure import failure_reason
from heycode.supervisor.runner import build_command

SUMMARY_MAX = 400
TAIL_LINES = 5


def _tail_lines(text: str, n: int = TAIL_LINES) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def _claude_result(output: str) -> str | None:
    """`claude -p --output-format json` imprime um objeto com o campo `result`."""
    for chunk in (output.strip(), *reversed(output.strip().splitlines())):
        try:
            data = json.loads(chunk)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("result"), str):
            return data["result"]
    return None


class Supervisor:
    def __init__(self, store, commands: dict | None = None, on_finish=None) -> None:
        self._store = store
        self._commands = commands
        self._on_finish = on_finish
        self._lock = threading.Lock()
        self._procs: dict[int, subprocess.Popen] = {}
        self._cancelled: set[int] = set()

    # API publica
    def start(self, agent: str, prompt: str, cwd: str, mode: str) -> int:
        fd, out_file = tempfile.mkstemp(prefix="bridge-run-", suffix=".txt")
        os.close(fd)
        try:
            cmd = build_command(agent, prompt, cwd, mode, out_file, self._commands)
        except ValueError:
            os.unlink(out_file)
            raise
        project = os.path.basename(os.path.abspath(cwd)) or cwd
        run_id = self._store.create_run(agent, project, prompt, cwd)
        threading.Thread(target=self._run, args=(run_id, agent, cmd, cwd, out_file),
                         daemon=True).start()
        return run_id

    def cancel(self, run_id: int) -> bool:
        with self._lock:
            proc = self._procs.get(run_id)
            if proc is None or proc.poll() is not None:
                return False
            self._cancelled.add(run_id)
        self._kill_tree(proc)
        return True

    def status(self, run_id: int) -> dict | None:
        return self._store.get_run(run_id)

    # internos
    @staticmethod
    def _kill_tree(proc: subprocess.Popen) -> None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                               capture_output=True, timeout=15)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass

    def _run(self, run_id, agent, cmd, cwd, out_file) -> None:
        output, code, error = "", None, None
        try:
            exe = shutil.which(cmd[0])
            if exe:
                cmd = [exe] + cmd[1:]
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            proc = subprocess.Popen(
                cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                **kwargs)
            with self._lock:
                self._procs[run_id] = proc
            self._store.update_run(run_id, pid=proc.pid)
            output, _ = proc.communicate()
            code = proc.returncode
        except Exception as exc:  # executavel ausente, cwd invalido...
            error = f"{type(exc).__name__}: {exc}"
        try:
            self._finish(run_id, agent, output or "", code, error, out_file)
        except Exception:  # nunca derruba a ponte
            try:
                self._store.update_run(run_id, status="falhou", summary="erro interno do supervisor")
            except Exception:
                pass
        finally:
            with self._lock:
                self._procs.pop(run_id, None)
                self._cancelled.discard(run_id)
            try:
                os.unlink(out_file)
            except OSError:
                pass

    def _finish(self, run_id, agent, output, code, error, out_file) -> None:
        with self._lock:
            cancelled = run_id in self._cancelled
        head = False  # resumo cortado pelo comeco (mensagem) ou pelo fim (cauda da saida)
        if cancelled:
            status, summary = "cancelada", _tail_lines(output)
        elif error is not None:
            status, summary = "falhou", error
        elif code != 0:
            reason = failure_reason(agent, output)  # ADR 0017: a mensagem do agente, nao o rabo do JSON
            status, summary, head = "falhou", reason or _tail_lines(output), bool(reason)
        else:
            status, summary, head = "concluida", self._last_message(agent, output, out_file), True
        summary = mask_secrets(summary)
        if len(summary) > SUMMARY_MAX:
            summary = summary[:SUMMARY_MAX] if head else summary[-SUMMARY_MAX:]
        self._store.update_run(run_id, status=status, summary=summary, exit_code=code)
        if self._on_finish:
            try:
                self._on_finish(self._store.get_run(run_id))
            except Exception:
                pass

    @staticmethod
    def _last_message(agent: str, output: str, out_file: str) -> str:
        if agent == "codex":
            try:
                with open(out_file, encoding="utf-8", errors="replace") as fh:
                    text = fh.read().strip()
                if text:
                    return text
            except OSError:
                pass
        if agent == "claude":
            result = _claude_result(output)
            if result:
                return result.strip()
        return output.strip()[-SUMMARY_MAX:]
