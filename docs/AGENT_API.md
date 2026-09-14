# Control agent, live overlay, telemetry, dashboard

Every node (gNB or UE host) runs one small HTTP agent, `codesign-api/kaiair_agent.py`.
The agent launches and supervises the modem
process, translates the persistent control state into `KAIAIR_*` environment at launch,
and exposes the runtime control. A separate local web dashboard
(`dashboard/kaiair_dash.py`) drives the agent and plots the telemetry.

```
        browser ── kaiair_dash.py ── kaiair_agent.py ──┬── gnb / nr-uesoftmodem
                                                       ├── /tmp/kaiair_ctrl.json   (control)
                                                       └── /tmp/kaiair_metrics.json (telemetry)
```

## Running the agent

```bash
python3 kaiair_agent.py --role gnb --config agent.gnb.json
```

The JSON config carries per-node facts: working directory and launch command, PCI, SSB
power, gate mode at launch, whether the UE is patched (`dl_sinr_csi`), control/metrics
file paths, and optionally the peer list for the UDP dev fallback. Examples under `codesign-api/`.

## HTTP endpoints (port 5000)

### Process lifecycle

| Endpoint | Effect |
|---|---|
| `GET /health` | `{"role": "gnb", "online": true, "running": <bool>}` |
| `POST /gnb/start`, `POST /gnb/stop` | start / stop the gNB (graceful stop. The agent waits for a clean radio release) |
| `POST /ue/start`, `POST /ue/stop` | same for a UE host |

On start, the agent reads the control file and builds the environment: metrics and GRK
views on, control-file overlay enabled, gamma from `sinr_target_db`, actuation on only if
`codesign` **and** `power_control` are both set, gate mode from `er_gate`, and the DL
true-SINR CSI flag only if the node config says the UE is patched.

### Runtime control

These write the control file. The gNB re-reads it about once per second.

| Endpoint | Body | Effect |
|---|---|---|
| `POST /kaiair/codesign` | `{"on": true}` | master enable |
| `POST /kaiair/power` | `{"enable": true}` | power-control actuation (UL + DL); takes effect within ~1 s |
| `POST /kaiair/params` | `{"sinr_target_db": 12}` | UL gamma, live |
| | `{"dl_sinr_target_db": 15}` | DL gamma, live |
| | `{"ldp_deadline_ms": 20}` | LDP deadline; `0` disables (experimental) |
| | `{"er_gate": "enforce"}` | ONAMA gate mode: `off` / `observe` / `enforce`, live |
| `GET /kaiair/state` | none | current control state |

Control file keys, for driving the system without the agent:

```json
{ "codesign": true, "power_control": true, "sinr_target_db": 12.0,
  "dl_sinr_target_db": 15.0, "ldp_deadline_ms": 0.0, "er_gate": "observe" }
```

### Telemetry

`GET /metrics` returns the latest JSON. The fields most consumers need:

| Field | Meaning |
|---|---|
| `ts`, `rnti` | sample time. Active C-RNTI (absent when no UE is connected) |
| `ul_sinr_db`, `ul_rsrp_dbfs`, `ni_dbfs` | UL per-packet SINR (EWMA), received power, noise+interference floor |
| `ul_sinr_target_db` | the loop's operating point: gamma plus the live Cantelli cushion |
| `dl_sinr_true_db`, `dl_gamma_db`, `dl_pwr_shed_db` | UE-reported DL SINR (patched UE), DL target, current DL power shed |
| `dl_sinr_est_db` | CQI-derived DL estimate (fallback when no true-SINR feedback) |
| `ul_mbps`, `tpc_db` | UL throughput, accumulated closed-loop TPC state |
| `ldp_ul_*`, `ldp_dl_*` | on-time / late / failed delivery percentages and average transmissions per delivered TB |
| `peer_cells`, `peer_links` | Xn mesh state: peers heard from, peer link records held |
| `links[]` | per-UE coordination record, see below |

Each entry of `links[]` describes one of the cell's own links:

```json
{ "rnti": "0x4601", "live": true,
  "serv_rsrp_dbm": -95.0, "nbr_rsrp_dbm": {"2": -94.0},
  "e_max_dbm": -112.5, "k_db": 4.0, "dl_er": 1, "er_pcis": [2],
  "conflicts": 1, "active_frac": 0.5,
  "ul_live": true, "ul_s_dbm": -88.0, "ul_e_max_dbm": -105.0,
  "ul_er": 1, "ul_conflicts": 1, "ul_active_frac": 0.5 }
```

`e_max` is the tolerable-interference budget at that receiver, `dl_er`/`ul_er` count
interferers inside the exclusion region, `conflicts` is the ONAMA slot-contention set size
(same-direction links of other cells), and `active_frac` is the fraction of slots this
link wins over the precomputed mask window.


## Dashboard

```bash
python3 dashboard/kaiair_dash.py     # serves http://localhost:8080
```

Runs on your workstation. The only requirement is that `ssh <gnb-host>` works. It polls
`/metrics` through SSH, keeps a sliding window, and renders: UL PUSCH SINR
with the gamma target line, UL throughput, DL SINR against its own target, UL/DL power,
LDP delivery (experimental), and a multi-cell coordination panel (neighbor RSRP, K, ER, conflicts,
active fraction) that appears when peers exist. The control bar drives the endpoints
above: power toggle, UL and DL gamma sliders and LDP deadline.

## A minimal external controller

Everything the dashboard does is plain HTTP, so closing an experiment loop from a script
is straightforward:

```bash
curl -s -X POST gnb:5000/kaiair/params -d '{"sinr_target_db": 15}'
sleep 30
curl -s gnb:5000/metrics | jq '{sinr: .ul_sinr_db, target: .ul_sinr_target_db}'
```
