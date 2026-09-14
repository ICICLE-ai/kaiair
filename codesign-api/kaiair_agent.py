#!/usr/bin/env python3
# KaiAir Co-Design control/telemetry agent  (stdlib only, runs on the bare containers).
#
# One agent per host. Role = "gnb" or "ue". The GUI talks HTTP to this agent; the agent
# does process lifecycle (start/stop the gNB/UE) and bridges control + telemetry:
#
#   control : GUI -> POST /kaiair/*  -> writes a JSON control file the gNB re-reads
#   telemetry: gNB -> writes metrics JSON  -> agent serves it at GET /metrics
#
# Today (skeleton): start/stop + health + control-file writes + metrics passthrough are REAL.
# The control-file toggles take effect at the NEXT gNB start (env is applied at launch);
# making them live-without-restart is the gNB "runtime-toggle" change (step 2). Telemetry is
# served from the metrics file once the gNB emits it (step 3); until then /metrics is a stub.
#
# Run:  python3 kaiair_agent.py --role gnb   [--config agent.gnb.json] [--port 5000]
#       python3 kaiair_agent.py --role ue    [--config agent.ue.json]

import argparse, json, os, pty, select, signal, subprocess, sys, termios, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ----------------------------------------------------------------- configuration
# Defaults target the current indoor bench; override any field via a --config JSON file.
DEFAULTS = {
    "gnb": {
        "role": "gnb",
        "port": 5000,
        "cwd": "/root/ocudu-kaiair/build/apps/gnb",
        "cmd": ["./gnb", "-c", "gnb_x310_tdd_n78_40mhz.yaml"],
        "log": "/root/gnb_run.log",
        "control_file": "/tmp/kaiair_ctrl.json",
        "metrics_file": "/tmp/kaiair_metrics.json",
        "pty_toggle": True,        # send 't\n' after toggle_after_s to start ocudu metrics
        "toggle_after_s": 12,
    },
    "ue": {
        "role": "ue",
        "port": 5000,
        "cwd": "/root/openairinterface5g-kaiair/cmake_targets/ran_build/build",
        "cmd": ["./nr-uesoftmodem", "-O",
                "../../../targets/PROJECTS/GENERIC-NR-5GC/CONF/ue.conf",
                "-r", "106", "--numerology", "1", "--band", "78",
                "-C", "3489420000", "--ue-fo-compensation", "-E",
                "--ssb", "42", "--usrp-args", "serial=<SERIAL>",
                "--uicc0.imsi", "<IMSI>"],
        "log": "/root/ue_run.log",
        "control_file": "/tmp/kaiair_ue_ctrl.json",
        "pty_toggle": False,
    },
}

# Default control state (what the gNB will honor once the runtime-toggle lands).
DEFAULT_CTRL = {
    "codesign": False,        # master KaiAir enable (off => stock scheduler/power)
    "power_control": False,   # PktR power actuation (UL + DL)
    "sinr_target_db": 3.0,    # required SINR margin gamma / target (UL)
    "dl_sinr_target_db": 10.0, # KaiAir DL-SINR: separate DL SINR target gamma_DL
    "ldp_deadline_ms": 0.0,   # KaiAir LDP: live deadline toggle (0 = off), no gNB restart needed
    "er_gate": "observe",     # KaiAir multi-cell ER gate: off | observe | enforce (applied at gNB launch)
    "scheduler": "pf",        # "pf" (stock) | "ldp" (roadmap, not yet implemented)
    "ul_power_apply": False,  # UE side: KAIAIR_UL_PWR_APPLY
}

CFG = {}
_proc = {"popen": None, "thread": None, "stop": None}  # single managed child per host
_lock = threading.Lock()
_bus = {"bus": None}  # KaiAir multi-cell peer bus instance (gNB role, when peers are configured)


# ----------------------------------------------------------------- control file
def read_ctrl():
    path = CFG["control_file"]
    try:
        with open(path) as f:
            d = json.load(f)
        return {**DEFAULT_CTRL, **d}
    except Exception:
        return dict(DEFAULT_CTRL)


def write_ctrl(update):
    path = CFG["control_file"]
    cur = read_ctrl()
    cur.update(update)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cur, f, indent=2)
    os.replace(tmp, path)
    return cur


def ctrl_to_env(ctrl):
    """Translate the control state into KAIAIR_* env for a gNB/UE launch."""
    env = dict(os.environ)
    if CFG["role"] == "gnb":
        env["KAIAIR_PKTR_METRICS"] = "1"          # always emit the feedback view
        env["KAIAIR_PKTR_GRK"] = "1"              # observe-only GRK line
        env.setdefault("KAIAIR_PKTR_BETA", "0.9")  # bench reliability target (0.99 over-cushions)
        env["KAIAIR_PKTR_CTRL_FILE"] = CFG["control_file"]  # enable the gNB live-toggle overlay
        env["KAIAIR_PKTR_METRICS_JSON"] = CFG.get("metrics_file", "/tmp/kaiair_metrics.json")  # telemetry egress
        on = bool(ctrl.get("codesign")) and bool(ctrl.get("power_control"))
        env["KAIAIR_PKTR_ACTUATE"] = "1" if on else "0"
        env["KAIAIR_PKTR_DL_ACTUATE"] = "1" if on else "0"
        env["KAIAIR_PKTR_DL_LOOP"] = "1" if on else "0"
        env["KAIAIR_PKTR_GAMMA_DB"] = str(ctrl.get("sinr_target_db", 3.0))
        # KaiAir multi-cell (plan B1-B5): DL true-SINR feedback, peer-bus snapshot file, ER gate mode,
        # SSB power and the cell PCI come from the agent config so a GUI-driven restart can never
        # silently drop them (the 2026-08-11 'powers off' bug).
        # DL true-SINR CSI is our custom 10-bit PUCCH format, ONLY our patched OAI UE produces it.
        # For a COTS UE (e.g. Quectel) it must be OFF or the gNB misreads standard CSI -> RLF. Set
        # "dl_sinr_csi": false in the agent config for commercial-UE tests (DL falls back to CQI).
        if CFG.get("dl_sinr_csi", True):
            env["KAIAIR_DL_SINR_CSI"] = "1"
        env["KAIAIR_PKTR_PEERS_FILE"] = CFG.get("peers_file", "/tmp/kaiair_peers.txt")
        env["KAIAIR_PKTR_ER_GATE"] = str(ctrl.get("er_gate", CFG.get("er_gate", "observe")))
        env["KAIAIR_PKTR_SSB_DBM"] = str(CFG.get("ssb_dbm", 16.0))
    else:
        env["KAIAIR_UL_PWR_APPLY"] = "1" if ctrl.get("ul_power_apply") else "0"
    return env


# ----------------------------------------------------------------- process mgmt
def _pty_run(cmd, cwd, env, logpath, toggle_after, stop_evt):
    """Run a child under a pty, auto-send 't\\n' (ocudu metrics toggle), log output, until stop."""
    master, slave = pty.openpty()
    try:
        a = termios.tcgetattr(slave)
        a[3] &= ~(termios.ICANON | termios.ECHO)   # cbreak so 't' reaches the console
        termios.tcsetattr(slave, termios.TCSANOW, a)
    except Exception:
        pass
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=slave, stdout=slave, stderr=slave,
                         close_fds=True, preexec_fn=os.setsid)
    os.close(slave)
    with _lock:
        _proc["popen"] = p
    logf = open(logpath, "wb")
    start, toggled = time.time(), False
    try:
        while not stop_evt.is_set() and p.poll() is None:
            r, _, _ = select.select([master], [], [], 0.5)
            if master in r:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                logf.write(data); logf.flush()
            if toggle_after and not toggled and time.time() - start >= toggle_after:
                os.write(master, b"t\n"); toggled = True
    finally:
        try: os.killpg(os.getpgid(p.pid), signal.SIGINT)
        except Exception: pass
        time.sleep(3)
        try: os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception: pass
        logf.close()


def start_child():
    with _lock:
        if _proc["popen"] and _proc["popen"].poll() is None:
            return False, "already running"
    ctrl = read_ctrl()
    env = ctrl_to_env(ctrl)
    stop_evt = threading.Event()
    if CFG.get("pty_toggle"):
        th = threading.Thread(target=_pty_run,
                              args=(CFG["cmd"], CFG["cwd"], env, CFG["log"],
                                    CFG.get("toggle_after_s", 12), stop_evt), daemon=True)
        th.start()
    else:
        logf = open(CFG["log"], "wb")
        p = subprocess.Popen(CFG["cmd"], cwd=CFG["cwd"], env=env,
                             stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
                             preexec_fn=os.setsid)
        with _lock:
            _proc["popen"] = p
        th = None
    with _lock:
        _proc["thread"] = th
        _proc["stop"] = stop_evt
    return True, "started"


def stop_child():
    with _lock:
        p, th, stop_evt = _proc["popen"], _proc["thread"], _proc["stop"]
    if not p or p.poll() is not None:
        return False, "not running"
    if stop_evt:
        stop_evt.set()
    try: os.killpg(os.getpgid(p.pid), signal.SIGINT)
    except Exception: pass
    for _ in range(6):
        if p.poll() is not None:
            break
        time.sleep(1)
    if p.poll() is None:
        try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception: pass
    return True, "stopped"


def child_running():
    with _lock:
        p = _proc["popen"]
    return bool(p and p.poll() is None)


# ----------------------------------------------------------------- telemetry
def read_metrics():
    path = CFG.get("metrics_file")
    if path and os.path.exists(path):
        try:
            with open(path) as f:
                d = json.load(f)
            d["source"] = "live"
            return d
        except Exception:
            pass
    # stub until the gNB emits the metrics file (step 3)
    return {"source": "stub", "ts": None, "ul_sinr_db": None, "ul_rsrp_dbfs": None,
            "ni_dbfs": None, "e_max_dbfs": None, "tpc_db": None, "dl_cqi": None,
            "dl_bler_pct": None, "ul_delay_ms": None, "k_db": None, "er_nodes": None,
            "ul_mbps": None, "dl_mbps": None, "eco_ratio": None}


# ----------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "KaiAirAgent/0.1"

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def log_message(self, *a):
        pass  # quiet

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        p = self.path.split("?")[0].rstrip("/") or "/"
        if p == "/health":
            return self._send(200, {"role": CFG["role"], "online": True,
                                    "running": child_running()})
        if p == "/kaiair/state":
            return self._send(200, read_ctrl())
        if p == "/metrics":
            return self._send(200, read_metrics())
        if p == "/peers":
            return self._send(200, {"bus": bool(_bus["bus"]),
                                    "peers": (_bus["bus"].snapshot() if _bus["bus"] else {}),
                                    "sent": (_bus["bus"].sent if _bus["bus"] else 0),
                                    "received": (_bus["bus"].received if _bus["bus"] else 0)})
        return self._send(404, {"error": "unknown route", "path": p})

    def do_POST(self):
        p = self.path.split("?")[0].rstrip("/") or "/"
        role = CFG["role"]
        body = self._body()

        # ---- process lifecycle ----
        if (role == "gnb" and p == "/gnb/start") or (role == "ue" and p == "/ue/start"):
            ok, msg = start_child();  return self._send(200 if ok else 409, {"ok": ok, "msg": msg})
        if (role == "gnb" and p == "/gnb/stop") or (role == "ue" and p == "/ue/stop"):
            ok, msg = stop_child();   return self._send(200 if ok else 409, {"ok": ok, "msg": msg})

        # ---- KaiAir control (gNB host) ----
        if role == "gnb" and p == "/kaiair/codesign":
            on = _as_bool(body.get("on", body.get("enable")))
            return self._send(200, {"ok": True, "state": write_ctrl({"codesign": on})})
        if role == "gnb" and p == "/kaiair/power":
            on = _as_bool(body.get("enable", body.get("on")))
            return self._send(200, {"ok": True, "state": write_ctrl({"power_control": on})})
        if role == "gnb" and p == "/kaiair/params":
            upd = {}
            if "sinr_target_db" in body:
                try: upd["sinr_target_db"] = float(body["sinr_target_db"])
                except Exception: return self._send(400, {"error": "sinr_target_db must be a number"})
            # KaiAir DL-SINR: separate DL SINR target (gamma is per-link/per-direction).
            if "dl_sinr_target_db" in body:
                try: upd["dl_sinr_target_db"] = float(body["dl_sinr_target_db"])
                except Exception: return self._send(400, {"error": "dl_sinr_target_db must be a number"})
            # KaiAir LDP: live deadline toggle (0 = off); the gNB re-reads the ctrl file at ~2 Hz.
            if "ldp_deadline_ms" in body:
                try: upd["ldp_deadline_ms"] = float(body["ldp_deadline_ms"])
                except Exception: return self._send(400, {"error": "ldp_deadline_ms must be a number"})
            if "er_gate" in body and str(body["er_gate"]) in ("off", "observe", "enforce"):
                upd["er_gate"] = str(body["er_gate"])
            return self._send(200, {"ok": True, "state": write_ctrl(upd)})
        if role == "gnb" and p == "/kaiair/scheduler":
            s = str(body.get("scheduler", "")).lower()
            if s not in ("pf", "ldp"):
                return self._send(400, {"error": "scheduler must be 'pf' or 'ldp'"})
            note = "LDP not yet implemented, recorded, effective when the LDP scheduler lands" if s == "ldp" else ""
            return self._send(200, {"ok": True, "state": write_ctrl({"scheduler": s}), "note": note})

        # ---- UE UL-power toggle (UE host) ----
        if role == "ue" and p == "/ue/power":
            on = _as_bool(body.get("enable", body.get("on")))
            return self._send(200, {"ok": True, "state": write_ctrl({"ul_power_apply": on})})

        return self._send(404, {"error": "unknown route for role", "role": role, "path": p})


def _as_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "on", "enable", "enabled", "yes")


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["gnb", "ue"], default=os.environ.get("KAIAIR_AGENT_ROLE"))
    ap.add_argument("--config")
    ap.add_argument("--port", type=int)
    args = ap.parse_args()
    if not args.role:
        sys.exit("--role gnb|ue required (or KAIAIR_AGENT_ROLE)")
    global CFG
    CFG = dict(DEFAULTS[args.role])
    if args.config:
        with open(args.config) as f:
            CFG.update(json.load(f))
    if args.port:
        CFG["port"] = args.port
    # ensure the control file exists so the GUI reads a defined state from the start
    if not os.path.exists(CFG["control_file"]):
        write_ctrl({})
    # KaiAir multi-cell peer bus (PktR-Signal): started when the config lists peers.
    # Transport: "xn" (default, 3GPP XNAP PRIVATE MESSAGE inside the gNB, no agent involvement),
    # "udp" (the PktR-prototype-style UDP bus between agents), or "both" (debug).
    if CFG["role"] == "gnb" and CFG.get("peers") and CFG.get("peer_transport", "xn") in ("udp", "both"):
        try:
            from peer_bus import PeerBus
            _bus["bus"] = PeerBus(CFG.get("pci", 0), CFG["peers"], port=int(CFG.get("bus_port", 5600)),
                                  peers_file=CFG.get("peers_file", "/tmp/kaiair_peers.txt"),
                                  metrics_reader=read_metrics, ssb_dbm=CFG.get("ssb_dbm", 16.0)).start()
            print(f"KaiAir peer bus: pci={CFG.get('pci')} peers={CFG['peers']} port={CFG.get('bus_port', 5600)}", flush=True)
        except Exception as e:
            print(f"KaiAir peer bus disabled: {e}", flush=True)
    srv = ThreadingHTTPServer(("0.0.0.0", CFG["port"]), Handler)
    print(f"KaiAir agent [{CFG['role']}] on :{CFG['port']}  ctrl={CFG['control_file']}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
