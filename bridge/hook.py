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


try:
    data = json.load(sys.stdin)
    if len(sys.argv) > 1 and sys.argv[1] == "approve":
        res = post("/approval", data, 55).get("decision")
        if res in ("allow", "deny"):
            decision = {"behavior": res}
            if res == "deny":
                decision["message"] = "Negado por voz via Alexa."
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}))
        # qualquer outra coisa: sem saída => Claude Code mostra o prompt normal
    else:
        post("/event", data, 3)
except Exception:
    pass  # a ponte nunca pode quebrar o Claude Code
sys.exit(0)
