#!/usr/bin/env python3
"""Hook do Claude Code. `hook.py` = envia evento; `hook.py approve` = pede aprovação por voz."""
import json, os, sys, urllib.request

URL = os.environ.get("BRIDGE_URL", "http://127.0.0.1:8765")
SECRET = os.environ.get("BRIDGE_SECRET", "")


def post(path, body, timeout):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "x-secret": SECRET})
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


try:
    argv = sys.argv[1:]
    agent = agent_of(argv)
    data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    data["agent"] = agent
    if "approve" in argv:
        res = post("/approval", data, 55).get("decision")
        if res in ("allow", "deny"):
            decision = {"behavior": res}
            if res == "deny":
                decision["message"] = "Negado por voz via Alexa."
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}))
        # qualquer outra coisa: sem saída => Claude Code mostra o prompt normal
    else:
        post("/event", data, 3)
        if data.get("hook_event_name") == "Stop":
            body = {"agent": agent}
            project = project_of(data.get("cwd"))
            if project:
                body["project"] = project
            text = post("/instruction/next", body, 3).get("instruction")
            if text:
                print(json.dumps({"decision": "block", "reason": text}, separators=(",", ":")))
except Exception:
    pass  # a ponte nunca pode quebrar o Claude Code
sys.exit(0)
