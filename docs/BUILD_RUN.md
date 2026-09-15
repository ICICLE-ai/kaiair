# Building and running KaiAir

## Host environment

KaiAir runs anywhere OCUDU and OAI run, on bare metal or in containers. The validated
setup is Ubuntu 24.04 with UHD 4.7 and gcc 13 on the gNB side and Ubuntu 22.04 on the UE
side, one container per node on the ARA testbed.

- USRP X310 and N3xx (network attached). The container needs an interface on the radio's
  subnet. A macvlan interface handed into the container works well and is what ARA uses,
  host networking also works.
- USRP B2xx (USB attached). Pass the USB device through, either the specific
  `/dev/bus/usb` device nodes or a privileged container. A device that re-enumerates
  after a crash gets a new device number, so passing the whole bus is more robust than a
  single node.
- Multi-cell timing. PTP (ptp4l and phc2sys) runs on the host. Containers share the host
  kernel clock, so they inherit the time sync. The 10 MHz and PPS distribution from octoclock to the gNB radios is mandatory (or use external sync through GPSDO).

## gNB (OCUDU + KaiAir patches)

```bash
# 1. Get OCUDU at the pinned base (see patches/ocudu/BASE for the exact commit)
git clone https://github.com/ocudu/ocudu.git && cd ocudu
git checkout $(cat ../patches/ocudu/BASE)

# 2. Apply the KaiAir series
git am ../patches/ocudu/*.patch      # or: ./scripts/apply_patches.sh ocudu

# 3. Build
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j"$(nproc)" gnb

# 4. Unit tests (all KaiAir suites)
make -j"$(nproc)" $(ls ../tests/unittests/scheduler/kaiair | grep _test | sed 's/\.cpp//')
ctest -R pktr
```

## UE (OAI nrUE + KaiAir patches)

Only needed for exact UL power apply, DL true-SINR feedback.
Any COTS UE works with gNB without this. Keep `KAIAIR_DL_SINR_CSI` unset in that
case, since the custom 10-bit CSI format must not be enabled against a UE that does not
produce it.

```bash
git clone https://gitlab.eurecom.fr/oai/openairinterface5g.git && cd openairinterface5g
git checkout $(cat ../patches/oai-nrue/BASE)
git am ../patches/oai-nrue/*.patch
cd cmake_targets && ./build_oai -w USRP --nrUE --ninja
```

## Configuration

### gNB YAML

Sample configurations under `configs/`. The KaiAir-relevant keys, beyond default configuration:

```yaml
ru_sdr:
  clock: external          # 10 MHz from OctoClock/GPSDO, required for multi-cell TDD
  sync: external           # PPS, single-cell can run internal

cell_cfg:
  pusch:
    enable_cl_loop_pw_control: true   # required for the UL loop, without it the gNB
                                      # computes f_cl internally but sends neutral TPC
    p0_nominal_with_grant: -112       # keep the UE off its P_CMAX clamp so TPC has headroom
    max_rb_size: 25                   # cap UL grant width on marginal links, wide grants
                                      # spread fixed UE power thin and can collapse the link

cu_cp:
  mobility:                # neighbor-cell measurement config (multi-cell only):
    ...                    # serving cell with periodic report cfg, neighbor cells with
                           # A3 event cfg, see configs/multicell/. The neighbor SMTC must
                           # match the actual SSB (ARFCN/period/offset/duration) exactly,
                           # otherwise F1 setup is rejected.
  xnap:                    # one connection block per peer CU-CP, gnb_id must differ
    connections:
      - bind_addrs: [<own Xn IP>]
        peer_addrs: [<peer Xn IP>]
```

### Environment knobs (gNB)

The agent (docs/AGENT_API.md) sets all of these. They are listed for standalone
runs. Defaults in `lib/scheduler/kaiair/pktr_runtime_config.h`.

| Variable | Default | Meaning |
|---|---|---|
| `KAIAIR_PKTR_METRICS` | off | enable the KaiAir console feedback view + metrics plumbing |
| `KAIAIR_PKTR_METRICS_JSON` | unset | path for the telemetry JSON |
| `KAIAIR_PKTR_CTRL_FILE` | unset | path of the live control overlay file (enables runtime control) |
| `KAIAIR_PKTR_GAMMA_DB` | 10.0 | UL SINR target gamma |
| `KAIAIR_PKTR_DL_GAMMA_DB` | 10.0 | DL SINR target (independent of UL, gamma is per-direction) |
| `KAIAIR_PKTR_BETA` | 0.9 | per-packet reliability target |
| `KAIAIR_PKTR_ACTUATE` / `_DL_ACTUATE` / `_DL_LOOP` | 0 | UL / DL actuation gates (observe-only when 0) |
| `KAIAIR_PKTR_MIN_CUSHION_DB` | 3.0 | floor on the Cantelli cushion |
| `KAIAIR_PKTR_GRK` | off | GRK exclusion-region view |
| `KAIAIR_PKTR_ER_GATE` | off | ONAMA gate mode at launch: `off` / `observe` / `enforce` |
| `KAIAIR_PKTR_PEERS_FILE` | unset | peer snapshot file (UDP dev fallback; unused with Xn) |
| `KAIAIR_PKTR_SSB_DBM` | 16.0 | own SSB power, published to peers for gain reciprocity |
| `KAIAIR_DL_SINR_CSI` | off | expect the 10-bit true-SINR CSI (patched UE ONLY) |
| `KAIAIR_DL_SINR_CSI_REF_DB` / `_STEP_DB` | 20 / 2 | CSI quantization reference and step |
| `KAIAIR_PKTR_DEADLINE_MS`, `_PKT_BETA`, `_TX0_MS`, `_RETX_MS` | off | LDP deadline parameters (experimental) |
| `KAIAIR_PKTR_DEBUG_TPC` | off | rate-limited TPC regulation prints |
| `KAIAIR_REQUIRE_GPS_LOCK` | off | make a missing/unreadable GPSDO lock sensor fatal again |

### Environment knobs (patched UE)

| Variable | Default | Meaning |
|---|---|---|
| `KAIAIR_UL_PWR_APPLY` | 0 | apply the computed UL power in the digital domain |
| `KAIAIR_UL_PWR_MIN_DB` | 20 | maximum digital backoff depth in dB. Keep this moderate (6 was used on B210s): the PA emits its broadband noise floor regardless of digital amplitude, so unbounded digital backoff sinks the signal into the transmitter's own noise |
| `KAIAIR_DL_SINR_CSI` (+`_REF_DB`, `_DEBUG`) | 0 | produce the 10-bit true-SINR CSI |

## Bring-up

### Single cell

```bash
# gNB (through the agent, see docs/AGENT_API.md)
python3 codesign-api/kaiair_agent.py --role gnb --config agent.gnb.json &
curl -X POST localhost:5000/gnb/start

# UE (patched OAI example)
KAIAIR_UL_PWR_APPLY=1 KAIAIR_UL_PWR_MIN_DB=6 KAIAIR_DL_SINR_CSI=1 \
./nr-uesoftmodem -O ue.conf -r 106 --numerology 1 --band 78 -C <freq> \
  --ue-fo-compensation -E --ssb 42 --ue-rxgain 120 --usrp-args "serial=<sn>"
```

The gNB can also be started manually, equivalent to what the agent launches:

```bash
cd <path_to_ocudu>/build/apps/gnb

KAIAIR_PKTR_METRICS=1 \
KAIAIR_PKTR_GRK=1 \
KAIAIR_PKTR_BETA=0.9 \
KAIAIR_PKTR_GAMMA_DB=10 \
KAIAIR_PKTR_DL_GAMMA_DB=10 \
KAIAIR_PKTR_ACTUATE=1 \
KAIAIR_PKTR_DL_ACTUATE=1 \
KAIAIR_PKTR_DL_LOOP=1 \
KAIAIR_PKTR_ER_GATE=observe \
KAIAIR_PKTR_SSB_DBM=16 \
KAIAIR_PKTR_CTRL_FILE=/tmp/kaiair_ctrl.json \
KAIAIR_PKTR_METRICS_JSON=/tmp/kaiair_metrics.json \
KAIAIR_DL_SINR_CSI=1 \
./gnb -c gnb.yaml
```

Notes for the manual run.

- Press `t` in the gNB console after start. The metrics printout and the telemetry JSON
  are gated behind the console metrics toggle, which the agent normally sends for you.
- `KAIAIR_DL_SINR_CSI=1` only with the patched UE. Leave it out for a COTS UE, otherwise
  the gNB misreads standard CSI.
- For an observe-only run set `KAIAIR_PKTR_ACTUATE=0 KAIAIR_PKTR_DL_ACTUATE=0
  KAIAIR_PKTR_DL_LOOP=0`.
- `KAIAIR_PKTR_CTRL_FILE` is optional. When set, the values in that file override gamma,
  power on and off, gate mode and the LDP deadline at runtime, which is how the agent and
  dashboard steer a running gNB. Without it the env values above are fixed for the run.
- `KAIAIR_PKTR_SSB_DBM` should match `ssb_block_power_dbm` in the YAML. Peers use it for
  the reciprocity gain math.

UL SINR statistics are only meaningful under UL traffic. Keep a light keepalive flowing
(100 Kbps is enough).

### Multi-cell

1. Give every radio the shared 10 MHz + PPS and set `clock/sync: external`. Verify the
   hosts are PTP-disciplined. ONAMA needs host clocks aligned to well under 10 us.
2. Assign distinct `gnb_id` and `pci` per cell, configure the `cu_cp.mobility` neighbor
   blocks and the `xnap` connections crosswise, and start all gNBs. Confirm the mesh:
   `peer_cells` in the telemetry JSON equals the number of peers.
3. Attach UEs one cell at a time. Time-synchronized co-channel cells transmit their SSBs
   in the same symbols, so a searching UE near equal-power cells sees a collision. The
   reliable way is to bring a UE up while its non-serving neighbors are quiet (stopped),
   then restore them.
   Attach order and a few dB of TX asymmetry decide which cell a free UE
   picks. Check the UE's serving PCI and retry if it camped wrong.
4. Coordination runs by itself from there. Measurement reports feed each gNB over RRC,
   the link records travel between gNBs over Xn, exclusion regions and conflicts form
   when there is actual load, and the gate mode is switched live per cell
   (`off` / `observe` / `enforce`) through the agent.
