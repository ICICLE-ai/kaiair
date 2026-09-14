#!/usr/bin/env python3
# KaiAir / PktR, inter-gNB peer bus ("PktR-Signal", pktR §V; plan step B2).
#
# Each gNB agent periodically broadcasts a compact JSON datagram with its cell's per-link PktR state
# (K, TX power, PRB-occupancy beta, ER size, the serving RSRP its UEs see, and what its UEs hear
# from every neighbor cell), and writes everything it receives from peers into a flat text file the
# gNB re-reads at ~2 Hz (pktr_neighbor_store::refresh_peers_from_file). Staleness is tolerated by
# design (PRKS: use the newest K you have); records older than MAX_AGE_S are dropped.
#
# Wire format (UDP, one JSON object per datagram):
#   {"pci": 7, "ssb_dbm": 16.0, "ts": 1786..., "links": [
#       {"rnti": "0x4601", "k_db": 8.5, "tx_dbm": 20.0, "beta": 0.35, "er": 1,
#        "signal_dbm": -78.0, "rxpwr": {"2": -84.0, "3": -95.0}} ]}
# File format (consumed by the gNB), one record per line:
#   cell <pci> <ssb_dbm> <ts>
#   link <pci> <rnti_hex> <k_db> <tx_dbm> <beta> <er> <signal_dbm>
#   rxpwr <pci> <rnti_hex> <from_pci> <rx_dbm>
import json, os, socket, threading, time

MAX_AGE_S = 5.0


class PeerBus:
    def __init__(self, my_pci, peers, port=5600, peers_file="/tmp/kaiair_peers.txt",
                 metrics_reader=None, period_s=0.5, bind_ip="0.0.0.0", ssb_dbm=16.0):
        """peers: list of "ip[:port]" strings of the other gNB agents."""
        self.my_pci, self.port, self.peers_file = int(my_pci), int(port), peers_file
        self.peers = [(p.split(":")[0], int(p.split(":")[1]) if ":" in p else self.port) for p in peers]
        self.metrics_reader = metrics_reader or (lambda: {})
        self.period_s, self.bind_ip, self.ssb_dbm = period_s, bind_ip, float(ssb_dbm)
        self.state = {}           # pci -> last datagram (dict)
        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((bind_ip, self.port))
        self.sock.settimeout(0.5)
        self.stop = threading.Event()
        self.sent = self.received = 0

    # ---- what we publish: derived from the gNB's metrics JSON ("links" array emitted by ocudu)
    def own_datagram(self):
        m = self.metrics_reader() or {}
        links = []
        for l in m.get("links", []) or []:
            links.append({
                "rnti": l.get("rnti"), "k_db": l.get("dl_k_db"), "tx_dbm": l.get("dl_tx_dbm"),
                "beta": l.get("beta"), "er": l.get("dl_er"), "signal_dbm": l.get("serv_rsrp_dbm"),
                "rxpwr": l.get("nbr_rsrp_dbm") or {},
            })
        return {"pci": self.my_pci, "ssb_dbm": m.get("ssb_dbm", self.ssb_dbm),
                "ts": time.time(), "links": links}

    def write_peers_file(self):
        now = time.time()
        lines = ["# KaiAir peer bus snapshot written %.3f" % now]
        with self.lock:
            for pci, d in sorted(self.state.items()):
                if now - float(d.get("ts", 0)) > MAX_AGE_S:
                    continue
                lines.append("cell %d %.2f %.3f" % (pci, float(d.get("ssb_dbm", 0.0)), float(d.get("ts", 0))))
                for l in d.get("links", []) or []:
                    try:
                        rnti = int(str(l.get("rnti")), 0)
                    except (TypeError, ValueError):
                        continue
                    def f(k, default=0.0):
                        v = l.get(k)
                        return float(v) if v is not None else default
                    lines.append("link %d %04x %.2f %.2f %.3f %d %.2f" % (
                        pci, rnti, f("k_db"), f("tx_dbm"), f("beta"), int(l.get("er") or 0), f("signal_dbm", -999.0)))
                    for frm, v in (l.get("rxpwr") or {}).items():
                        try:
                            lines.append("rxpwr %d %04x %d %.2f" % (pci, rnti, int(frm), float(v)))
                        except (TypeError, ValueError):
                            pass
        tmp = self.peers_file + ".tmp"
        with open(tmp, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(tmp, self.peers_file)

    def _tx_loop(self):
        while not self.stop.is_set():
            try:
                payload = json.dumps(self.own_datagram()).encode()
                for ip, port in self.peers:
                    self.sock.sendto(payload, (ip, port))
                    self.sent += 1
            except Exception:
                pass
            self.write_peers_file()
            self.stop.wait(self.period_s)

    def _rx_loop(self):
        while not self.stop.is_set():
            try:
                data, _ = self.sock.recvfrom(65535)
                d = json.loads(data.decode())
                pci = int(d.get("pci"))
                if pci == self.my_pci:
                    continue
                with self.lock:
                    self.state[pci] = d
                self.received += 1
            except socket.timeout:
                continue
            except Exception:
                continue

    def start(self):
        threading.Thread(target=self._rx_loop, daemon=True).start()
        threading.Thread(target=self._tx_loop, daemon=True).start()
        return self

    def snapshot(self):
        with self.lock:
            return {pci: dict(d) for pci, d in self.state.items()}
