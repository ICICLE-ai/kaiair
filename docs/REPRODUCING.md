# Reproducing the headline results

All experiments below ran on the ARA testbed indoor sandbox: USRP X310 gNBs (one per
cell), USRP B210 UEs, band n78, 40 MHz, 30 kHz SCS, TDD period 5 (3 DL, 1 S, 1 UL).
Numbers will differ on other RF setups. The shapes should not.

Common to all runs. The gNB is launched through the agent with the control overlay
enabled, a light UL keepalive (10 Hz ping over the UE tunnel) runs whenever a statistic
depends on UL traffic, and per-packet UL SINR comes from `pusch_sinr_calc_method: channel_estimator`.

## 1. UL per-packet reliability C-CDF (stock vs PktR)

The claim. At gamma 17 dB and beta 0.9, the stock scheduler satisfies the per-packet SINR
target about half the time. PktR raises it to 99%.

1. Single cell, one UE, steady light traffic.
2. Arm A (stock): `power_control` off. Arm B (PktR): on. Alternate arms on a timer
   (75 s each) via the control endpoint so both see the same channel. Run 30 minutes or more.
3. Collect per-packet UL SINR from the PHY debug log (`phy_level: debug`) or the JSON
   stream. Split by arm using the `ul_sinr_target_db` field as the arm label.
4. Plot the C-CDF of SINR per arm and read `P(SINR >= gamma)` at gamma.

Our run had 115,621 PUSCH samples. Stock 0.521, PktR 0.991, and the beta-quantile moved up 3.2 dB.

## 2. DL power shed at constant reliability (true-SINR loop)

The claim. With UE-reported true SINR, the DL loop holds its target while shedding double-digit
dB of transmit power against the full-power baseline.

Requires the patched UE (`KAIAIR_DL_SINR_CSI=1` on both sides).

1. Arm A: DL loop off, stock full-power PDSCH. Record `dl_sinr_true_db`.
2. Arm B: DL loop on with `dl_sinr_target_db` chosen inside the actuator's reachable
   range (the per-PDSCH offset spans 15 dB, so pick a target 8 to 10 dB under the full-power
   SINR). Record `dl_sinr_true_db` and `dl_pwr_shed_db`.
3. Compare: arm B should sit on target (plus cushion) with a steady shed.

In our run, full power gave 24.4 dB DL SINR and the loop held a 10 dB target with a mean shed
of 10.8 dB.

## 3. LDP deadline sweep (experimental feature)

The claim. On-time delivery rises with the deadline exactly as the retransmission budget
predicts.

1. Single cell, steady traffic, LDP off: record the `ldp_ul_ontime_pct` family (packets
   are classified against a display deadline even with LDP off, so both arms share a
   yardstick).
2. Sweep `ldp_deadline_ms` over 10 / 20 / 30 / 50 via the live endpoint, a few minutes
   per point.

Our run: UL on-time 91.1 / 99.4 / 99.9 / 100 percent.

## 4. Two-cell coordination (observe vs enforce)

The claim. With two co-channel cells in mutual conflict, enforce partitions the airtime
0.5/0.5, the aggressor keeps its full offered rate, and the victim's floor cleans up.

Setup: two cells, same ARFCN, shared 10 MHz + PPS at the radios, PTP-disciplined hosts,
Xn connected (`peer_cells` = 1 on each), one UE per cell (see the multi-cell bring-up
notes in BUILD_RUN.md), sustained UL load on both (a couple of Mbps each is plenty at
this geometry).

1. Both cells `er_gate: observe`. Record: `ul_conflicts`, `ul_active_frac` (computed but
   not enforced), each cell's `ni_dbfs`, UL SINR, and delivered throughput. One cell will
   typically emerge as the victim.
2. Switch both to `enforce` (live). Within seconds the masks apply.
3. Compare the same fields. Expect: `ul_active_frac` ~0.5 on both and complementary
   (the two fractions sum to ~1), the victim's `ni_dbfs` down several dB, the aggressor's
   delivery unchanged.

In our run the shares sat at 0.49 to 0.51 against each other throughout, the victim floor
went from -33 to -45 dBFS on one arm pair, and the aggressor kept its full offered rate
in every enforce sample.

With a third cell in mutual conflict the same fields converge to shares of about one third without
any configuration change. The share follows the conflict-set size.

## Pitfalls that will eat your afternoon

- Comparing absolute RSRP across sessions. Per-session radio calibration shifts several
  dB, so compare within a session, or against the same-session baseline arm.
- Idle-link UL SINR. Without UL traffic the estimate pins at an artifact. Keep the
  keepalive on.
- Co-channel synchronized cells and UE attach. SSBs collide by construction, so attach one
  UE at a time with the neighbor cells quiet. Established links survive the neighbors
  returning.
- iperf3 servers accept one test per port at a time, so give each concurrent stream its own
  port.
