# KaiAir

KaiAir is predictable per-packet power control and scheduling implemented in the
[OCUDU](https://github.com/ocudu) 5G stack. KaiAir brings PktR&sup1; and LDP&sup2; into
the OCUDU 5G stack, providing per-packet transmission power control, GRK interference
modeling with K-adaptation, and multi-cell interference coordination built on
receiver-side exclusion regions and ONAMA slot scheduling. A companion patch set for
the OAI nrUE adds the fine-grained measurement and actuation path needed for power
control. The implementation has been verified and measured on real radios, USRP X310
and B210 deployments on the ARA wireless living lab.

**Tags:** CI4AI, Software

### License

[![License](https://img.shields.io/badge/License-BSD--3--Clause-yellow.svg)](https://github.com/ICICLE-ai/kaiair/blob/main/LICENSE)

The KaiAir contribution is released under the BSD 3-Clause license. OCUDU is licensed
under BSD-3-Clause-Open-MPI by Software Radio Systems Limited. OAI is licensed under the
OAI CSSL. This repository contains the patch series that is applied onto trees
obtained from the respective upstreams.

## References

- PktR: Zhibo Meng, Hongwei Zhang, Joint Scheduling and Power Control for Predictable Per-Packet Reliability in URLLC, IEEE International Conference on Network Protocols (ICNP), 2024
- LDP: Zhibo Meng, Hongwei Zhang, Multi-Cell, Multi-Channel URLLC with Probabilistic Per-Packet Real-Time Guarantee, Technical Report ISU-DNC-TR-2020-01, Iowa State University, 2020
- [OCUDU](https://github.com/ocudu), the 5G O-DU/CU stack the gNB patch series applies to.
- [OpenAirInterface 5G RAN](https://gitlab.eurecom.fr/oai/openairinterface5g), the nrUE
  the UE patch series applies to.
- [ARA Wireless Living Lab](https://arawireless.org), the testbed the implementation was
  validated on.

## Acknowledgements

This work has been funded by grants from the National Science Foundation award 2130889
(ARA Wireless Living Lab) and NIFA award 2021-67021-33775.

*National Science Foundation (NSF) funded AI institute for Intelligent Cyberinfrastructure with Computational Learning in the Environment (ICICLE) (OAC 2112606)*

## Issue reporting

Report issues on the GitHub issue tracker at
https://github.com/ICICLE-ai/kaiair/issues.

---

# How-To Guides

## Requirements

- OCUDU at the pinned base commit (see `patches/ocudu/BASE`), Linux, gcc 11 or newer,
  UHD 4.x.
- A COTS UE works for the UL direction and for CQI-based DL. The full DL true-SINR loop
  needs the patched OAI nrUE. Those patches target the tag in `patches/oai-nrue/BASE`.
- Multi-cell coordination needs a common 10 MHz and PPS reference for the radios
  (OctoClock or GPSDO) and PTP-synchronized hosts. ONAMA takes its global slot index from
  the host clock. A slot is 500 us, so host synchronization must be well under that. PTP
  with hardware timestamping ensures nanosecond sync.

## Install

Clone each upstream at its pinned base and apply the KaiAir patch series.

```bash
# gNB
git clone https://github.com/ocudu/ocudu.git
./scripts/apply_patches.sh ocudu ./ocudu
cd ocudu && mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Release .. && make -j"$(nproc)" gnb

# UE (needed for the full DL true-SINR loop)
git clone https://gitlab.eurecom.fr/oai/openairinterface5g.git
./scripts/apply_patches.sh oai-nrue ./openairinterface5g
cd openairinterface5g/cmake_targets && ./build_oai -w USRP --nrUE --ninja
```

The full walkthrough, including the host environment,
configuration, and multi-cell bring-up, is in
[docs/BUILD_RUN.md](docs/BUILD_RUN.md).

## Run

```bash
# gNB, through the control agent
python3 codesign-api/kaiair_agent.py --role gnb --config agent.gnb.json &
curl -X POST localhost:5000/gnb/start

# dashboard, on your workstation
python3 dashboard/kaiair_dash.py     # serves http://localhost:8080
```

The agent HTTP API, the live control-file overlay, the telemetry JSON, and the dashboard
are documented in [docs/AGENT_API.md](docs/AGENT_API.md).

---

## What is in this release

- UL per-packet power control
- DL per-packet power control
- GRK interference model, exclusion-region, K-adaptation
- Multi-cell measurement plane (neighbor RSRP via RRC, TDD-reciprocity gain map)
- Inter-gNB PktR-Signal exchange over Xn-AP PRIVATE MESSAGE (TS 38.423)
- Conflict graph and ONAMA slot gate with off, observe, and enforce modes
- Live control plane (HTTP agent plus control-file overlay)
- Telemetry (per-link JSON, web dashboard)

## Repository layout

```
patches/ocudu/       KaiAir gNB patch series against the pinned OCUDU base
patches/oai-nrue/    UE patch series against the pinned OAI tag
codesign-api/        per-node control agent (HTTP, stdlib Python) and peer bus
dashboard/           local web dashboard (live SINR, power, and coordination view)
configs/             known-good gNB YAMLs and UE configuration
scripts/             patch apply and build helpers
docs/                architecture, build and run guide, agent API
```

How KaiAir is organized, where every piece lives in the OCUDU tree, and what changed in
the OAI nrUE is covered in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). 

---
