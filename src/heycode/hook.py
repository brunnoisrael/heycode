"""Hook dos agentes. `heycode hook` envia evento; `heycode hook approve` pede aprovacao por voz.

So biblioteca padrao e falha aberta: a ponte nunca pode quebrar nem atrasar o agente.
"""

import json
import os
import sys
import urllib.request


def post(url, secret, path, body, timeout):
    req = urllib.request.Request(
        url + path, json.dumps(body).encode(), {"Content-Type": "application/json", "x-secret": secret}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def project_of(cwd):
    return os.path.basename(str(cwd or "").rstrip("/\\")) or None


def agent_of(argv):
    if "--agent" in argv:
        i = argv.index("--agent")
        if i + 1 < len(argv):
            return argv[i + 1]
    return "claude"


def run(argv, stdin=None):
    """Executa o hook. Retorna sempre 0: qualquer erro deixa o agente seguir normalmente."""
    url = os.environ.get("BRIDGE_URL", "http://127.0.0.1:8765")
    secret = os.environ.get("BRIDGE_SECRET", "")
    try:
        agent = agent_of(argv)
        raw = (stdin or sys.stdin.buffer).read()
        data = json.loads(raw.decode("utf-8", errors="replace"))
        data["agent"] = agent
        if "approve" in argv:
            res = post(url, secret, "/approval", data, 55).get("decision")
            if res in ("allow", "deny"):
                decision = {"behavior": res}
                if res == "deny":
                    decision["message"] = "Negado por voz via Alexa."
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}))
            # qualquer outra coisa: sem saida => o agente mostra o prompt normal
        else:
            post(url, secret, "/event", data, 3)
            if data.get("hook_event_name") == "Stop":
                body = {"agent": agent}
                project = project_of(data.get("cwd"))
                if project:
                    body["project"] = project
                text = post(url, secret, "/instruction/next", body, 3).get("instruction")
                if text:
                    reason = "Instrução do dono, ditada pela Alexa e confirmada por voz: " + text
                    print(json.dumps({"decision": "block", "reason": reason}, separators=(",", ":")))
    except Exception:
        pass  # a ponte nunca pode quebrar o agente
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
