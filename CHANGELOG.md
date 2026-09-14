# Changelog

## 1.0.0 (first release)

PktR complete:
- UL per-packet power control on the standard closed-loop TPC path (Cantelli target),
  works with any UE; optional exact-power apply on the patched OAI nrUE.
- DL per-packet power control via the per-PDSCH power offset; feedback from either
  standard CQI or the patched UE's 10-bit true-SINR CSI.
- GRK interference model, exclusion-region sizing, K-adaptation.
- Multi-cell coordination: neighbor-RSRP measurement plane, PktR-Signal exchange over
  Xn-AP PRIVATE MESSAGE (TS 38.423), conflict graph, ONAMA slot gate with
  off/observe/enforce modes and a PTP-derived global slot index.
- Runtime control plane (HTTP agent, live control-file overlay), 1 Hz telemetry JSON,
  web dashboard.
- 12 unit-test suites.

Included as experimental (stabilizing in a future release):
- LDP deadline enforcement (per-HARQ deadline abandonment, N(D) retransmission budget,
  urgency-ordered retransmissions). The LDP allocation scheduler (partition bookkeeping,
  density-priority grants, admission control) is not yet included.
