#!/usr/bin/env python3
# KaiAir demo dashboard, run LOCALLY, view in a browser, drives the bench over ssh + the
# codesign agent HTTP API (kaiair_agent.py) on gnb1.
#
#   python3 dashboard/kaiair_dash.py          # then open http://localhost:8080
#
# Requirements: `ssh gnb1` must work from this machine (the agent listens on gnb1:5000).
# Everything (telemetry polling AND control) goes through the agent API via ssh+curl, so no
# extra ports or tunnels are needed.
#
#   telemetry : GET  /metrics            (1 Hz poll -> rolling 10 min buffer)
#   state     : GET  /kaiair/state      (toggle states shown in the UI)
#   power     : POST /kaiair/power      {"enable": bool}     (instant, live overlay)
#   target    : POST /kaiair/params     {"sinr_target_db": x} (instant, live overlay)
#   LDP       : POST /kaiair/params {"ldp_deadline_ms": x} (live ctrl-file overlay; 0 = off), 
#               instant, no restarts.
import json
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GNB_HOST = "gnb1"    # ssh alias of the gNB host running the agent
POLL_S = 0.3
HISTORY = 600  # samples: sliding window of ~3 min at the ~3 Hz poll
PORT = 8080

history = deque(maxlen=HISTORY)
state = {"power": None, "gamma": None, "ldp_ms": None, "er_gate": None, "busy": "", "link": "down", "ue": False, "rf": "?"}
lock = threading.Lock()


def ssh(cmd, timeout=8):
    try:
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=4", GNB_HOST, cmd],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def agent_get(path):
    out = ssh(f"curl -s -m 2 localhost:5000{path}")
    try:
        return json.loads(out)
    except Exception:
        return {}


def agent_post(path, payload):
    body = json.dumps(payload).replace('"', '\\"')
    out = ssh(f'curl -s -m 3 -X POST localhost:5000{path} -d "{body}"')
    try:
        return json.loads(out)
    except Exception:
        return {}


def poller():
    while True:
        t0 = time.time()
        m = agent_get("/metrics")
        with lock:
            if m and m.get("ts"):
                age = time.time() - float(m["ts"])
                state["link"] = "up" if age < 5 else "down"
                # "UE connected" iff the gNB metrics carry an active C-RNTI (idle-attached still counts).
                state["ue"] = bool(m.get("rnti")) if age < 5 else False
                ni = m.get("ni_dbfs")
                state["rf"] = "clean" if (ni is not None and ni < -40) else ("noisy" if ni is not None else "?")
                if age < 5:
                    m["wall"] = time.time()
                    # Stamp the bare gamma (the application's SINR TARGET, constant w.r.t. the
                    # power-control toggle) onto each sample so the GUI can draw it as the fixed
                    # red line. ul_sinr_target_db from telemetry is the loop's OPERATING POINT
                    # (gamma + Cantelli cushion when actuation is on) - a different concept.
                    m["gamma_db"] = state.get("gamma")
                    history.append(m)
            else:
                state["link"] = "down"
        time.sleep(max(0.0, POLL_S - (time.time() - t0)))


def state_refresher():
    while True:
        s = agent_get("/kaiair/state")
        with lock:
            if s:
                state["power"] = bool(s.get("power_control"))
                state["gamma"] = s.get("sinr_target_db")
                state["dl_gamma"] = s.get("dl_sinr_target_db")  # KaiAir DL-SINR separate DL target
                # KaiAir LDP: live ctrl-file deadline (0/absent = off), no restart flow anymore.
                d = s.get("ldp_deadline_ms")
                state["ldp_ms"] = float(d) if d else None
                # KaiAir multi-cell: live ER-gate mode (off | observe | enforce) from the ctrl overlay.
                state["er_gate"] = s.get("er_gate")
        time.sleep(3)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            html = (Path(__file__).parent / "dash.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        if p == "/api/data":
            with lock:
                return self._json(200, {"history": list(history), "state": dict(state)})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        if p == "/api/power":
            r = agent_post("/kaiair/power", {"enable": bool(body.get("on"))})
            return self._json(200, r or {"ok": False})
        if p == "/api/target":
            r = agent_post("/kaiair/params", {"sinr_target_db": float(body.get("db", 5.0))})
            return self._json(200, r or {"ok": False})
        if p == "/api/dltarget":
            # KaiAir DL-SINR: separate DL SINR target (gamma is per-direction).
            r = agent_post("/kaiair/params", {"dl_sinr_target_db": float(body.get("db", 10.0))})
            return self._json(200, r or {"ok": False})
        if p == "/api/ergate":
            # KaiAir multi-cell: live ctrl-file ER-gate mode, the gNB re-reads it within ~1 s.
            mode = str(body.get("mode", "observe"))
            if mode not in ("off", "observe", "enforce"):
                return self._json(400, {"error": "mode must be off|observe|enforce"})
            r = agent_post("/kaiair/params", {"er_gate": mode})
            return self._json(200, {"ok": True, "agent": r})
        if p == "/api/ldp":
            # KaiAir LDP: live ctrl-file toggle, takes effect in ~1 s, no agent/gNB restart.
            ms = float(body.get("deadline_ms", 10.0)) if body.get("on") else 0.0
            r = agent_post("/kaiair/params", {"ldp_deadline_ms": ms})
            return self._json(200, r or {"ok": False})
        self._json(404, {"error": "not found"})


def main():
    threading.Thread(target=poller, daemon=True).start()
    threading.Thread(target=state_refresher, daemon=True).start()
    print(f"KaiAir dashboard: http://localhost:{PORT}  (bench host: {GNB_HOST} via ssh)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
