# KaiAir

KaiAir is predictable per-packet power control and scheduling implemented in the
[OCUDU](https://github.com/ocudu) 5G stack. It is based on PktR, the joint scheduling and
power control approach of Zhibo Meng and Hongwei Zhang, "Joint Scheduling and Power
Control for Predictable Per-Packet Reliability in URLLC". KaiAir
implements per-packet transmission power control, GRK interference
modeling with K-adaptation, and multi-cell interference coordination built on
receiver-side exclusion regions and ONAMA slot scheduling. A companion patch set for
the OAI nrUE adds the fine-grained measurement and actuation path needed to
implement power control. The implementation has been verified and measured
on real radios, USRP X310 and B210 deployments on the ARA wireless living lab.

## What is in this release


| Component | Status |
|---|---|
| UL per-packet power control | verified |
| DL per-packet power control | verified |
| GRK interference model, exclusion-region, K-adaptation | verified |
| Multi-cell measurement plane (neighbor RSRP via RRC, TDD-reciprocity gain map) | verified |
| Inter-gNB PktR-Signal exchange over Xn-AP PRIVATE MESSAGE (TS 38.423) | verified |
| Conflict graph and ONAMA slot gate with off, observe, and enforce modes | verified |
| Live control plane (HTTP agent plus control-file overlay) | verified |
| Telemetry (per-link JSON, web dashboard) | verified |

## Repository layout

```
patches/ocudu/       KaiAir gNB patch series against the pinned OCUDU base
patches/oai-nrue/    UE patch series against the pinned OAI tag
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

## Requirements

- OCUDU at the pinned base commit (see `patches/ocudu/BASE`), Linux, gcc 11 or newer,
  UHD 4.x.
- A COTS UE works for the UL direction and for CQI-based DL. The full DL true-SINR loop
  needs the patched OAI nrUE. Those patches target the tag in `patches/oai-nrue/BASE`.
- Multi-cell coordination needs a common 10 MHz and PPS reference for the radios
  (OctoClock or GPSDO) and PTP-synchronized hosts. ONAMA takes its global slot index from
  the host clock. A slot is 500 us, so host synchronization must be well under that. PTP
  with hardware timestamping ensures nanosecond sync.

## ICICLE component catalog

KaiAir is released as an ICICLE CI component. The component definition following the
[CI-Components-Catalog](https://github.com/ICICLE-ai/CI-Components-Catalog) schema is in
[`icicle-component.yaml`](icicle-component.yaml). Release notes live in
[`CHANGELOG.md`](CHANGELOG.md).

## Acknowledgements

This work has been funded by grants from the National Science Foundation awards 2130889 (ARA Wireless Living Lab) and 2112606 (ICICLE AI Institute) and NIFA award 2021-67021-33775.

## License

The KaiAir contribution is released under the BSD 3-Clause license. OCUDU is licensed
under BSD-3-Clause-Open-MPI by Software Radio Systems Limited. OAI is licensed under the
OAI CSSL. This repository contains the patch series that is applied onto trees
obtained from the respective upstreams.
