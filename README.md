# KaiAir

KaiAir brings the PRK family of URLLC algorithms into a working 5G stack. It adds PktR
per-packet transmission power control, GRK interference modeling with K-adaptation, and
multi-cell interference coordination built on receiver-centric exclusion regions and ONAMA
slot scheduling. The gNB side lives inside the [OCUDU](https://github.com/ocudu) O-DU/CU
stack. A companion patch set for the OAI nrUE adds the fine-grained measurement and
actuation path we use as a reference arm. All results below were measured on real radios,
USRP X310 and B210 deployments on the ARA wireless testbed.

The goal is easy to state. Hold `Pr{SINR >= gamma} >= beta` for every packet on every
link, using only mechanisms a real network can deploy. That means standard TPC commands,
HARQ feedback, RRC measurement reports, and Xn signaling between gNBs. Where standard
feedback is too coarse, an optional modified UE closes the gap.

## What is in this release

PktR is complete and verified on hardware.

| Component | Status |
|---|---|
| UL per-packet power control (Cantelli target on the stock TPC loop) | verified on hardware |
| DL per-packet power control (per-PDSCH power offset, UE-reported true-SINR feedback) | verified on hardware |
| GRK interference model, exclusion-region sizing, K-adaptation | verified on hardware |
| Multi-cell measurement plane (neighbor RSRP via RRC, TDD-reciprocity gain map) | verified on hardware |
| Inter-gNB PktR-Signal exchange over Xn-AP PRIVATE MESSAGE (TS 38.423) | verified on hardware |
| Conflict graph and ONAMA slot gate with off, observe, and enforce modes | verified on hardware |
| Live control plane (HTTP agent plus control-file overlay, no restarts) | verified on hardware |
| Telemetry (per-link JSON at 1 Hz, web dashboard) | verified on hardware |

LDP ships in this release but is marked experimental. The deadline-enforcement half
(per-HARQ deadline abandonment, the N(D) retransmission budget, urgency-ordered
retransmissions) is included and tested. The allocation half of the LDP scheduler
(partition bookkeeping, density-priority grants, admission control) is planned for the
next release. LDP never feeds back into power control. The two are independent by design,
following LDP-TR.

## Selected results

Measured on ARA indoor nodes, USRP X310 gNB with B210 UE, band n78, 40 MHz TDD.

- UL per-packet reliability at gamma of 17 dB and beta of 0.9. The stock scheduler meets
  the SINR target on 52.1% of packets. With PktR it is 99.1%, from a 115k-packet C-CDF
  with both arms in the same session.
- DL power control with UE-reported true SINR. The loop holds the DL target while
  shedding 10.8 dB of transmit power on average, against a full-power stock baseline at
  equal reliability.
- LDP deadline enforcement. UL on-time delivery of 91%, 99.4%, 99.9% and 100% at
  deadlines of 10, 20, 30 and 50 ms.
- Two co-channel cells under mutual interference in ONAMA enforce mode. Airtime splits
  0.50 and 0.50 (we measured 0.492 to 0.508 across runs), the aggressor cell keeps its
  full offered rate, and the victim's noise floor drops 5 to 7 dB. With three cells in
  mutual conflict the split settles at one third each. The share follows the conflict-set
  size on its own, nothing is configured.

## Repository layout

```
patches/ocudu/       KaiAir gNB patch series against the pinned OCUDU base
patches/oai-nrue/    UE patch series against the pinned OAI tag (reference arm, optional)
codesign-api/        per-node control agent (HTTP, stdlib Python) and peer bus
dashboard/           local web dashboard (live SINR, power, and coordination view)
configs/             known-good gNB YAMLs and UE configuration
scripts/             patch apply and build helpers
docs/                architecture, build and run guide, agent API, experiment notes
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) covers how KaiAir is organized, where every
  piece lives in the OCUDU tree, and what changed in the OAI nrUE.
- [docs/BUILD_RUN.md](docs/BUILD_RUN.md) covers building both sides, the configuration
  knobs, and bring-up for single-cell and multi-cell operation.
- [docs/AGENT_API.md](docs/AGENT_API.md) covers the HTTP control agent, the live
  control-file overlay, the telemetry JSON, and the dashboard.
- [docs/REPRODUCING.md](docs/REPRODUCING.md) walks through the experiments behind the
  results above.

## Requirements

- OCUDU at the pinned base commit (see `patches/ocudu/BASE`), Linux, gcc 11 or newer,
  UHD 4.x.
- A COTS UE works for the UL direction and for CQI-based DL. The full DL true-SINR loop
  needs the patched OAI nrUE. Those patches target the tag in `patches/oai-nrue/BASE`.
- Multi-cell coordination needs a common 10 MHz and PPS reference for the radios
  (OctoClock or GPSDO) and PTP-synchronized hosts. ONAMA takes its global slot index from
  the host clock. A slot is 500 us, so host synchronization must be well under that. PTP
  with hardware timestamping gives tens of microseconds, which is plenty.

## ICICLE component catalog

KaiAir is released as an ICICLE CI component. The component definition following the
[CI-Components-Catalog](https://github.com/ICICLE-ai/CI-Components-Catalog) schema is in
[`icicle-component.yaml`](icicle-component.yaml). Release notes live in
[`CHANGELOG.md`](CHANGELOG.md).

## Acknowledgements

This work has been funded by grants from the National Science Foundation, including the
ICICLE AI Institute (OAC 2112606).

## License

The KaiAir contribution is released under the BSD 3-Clause license. OCUDU is licensed
under BSD-3-Clause-Open-MPI by Software Radio Systems Limited. OAI is licensed under the
OAI CSSL. This repository redistributes neither one. The patch series apply onto trees
you obtain from the respective upstreams.
