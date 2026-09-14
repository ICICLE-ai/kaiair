# Changelog

## v1.0.0 (first release)

PktR complete:
- UL per-packet power control on the standard closed-loop TPC path,
  works with any UE. Optional exact-power apply on the patched OAI nrUE.
- DL per-packet power control via the per-PDSCH power offset. Feedback from either
  standard CQI or the patched UE's 10-bit true-SINR CSI.
- GRK interference model, exclusion-region sizing, K-adaptation.
- Multi-cell coordination: neighbor-RSRP measurement plane, PktR-Signal exchange over
  Xn-AP PRIVATE MESSAGE (TS 38.423), conflict graph, ONAMA slot gate with
  off/observe/enforce modes and a PTP-derived global slot index.
- Runtime control plane (HTTP agent, live control-file overlay), telemetry JSON,
  web dashboard.
- 12 unit-test suites.

Included as experimental (future release):
- LDP scheduler (priority-based scheduling, admission control) is not yet included.
