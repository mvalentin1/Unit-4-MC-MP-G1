#!/usr/bin/env python3
"""Mini Project 4.1 (Part B) - LPWAN link-budget and battery-life comparison.

Scenario: 200 soil sensors, 25 km^2 farm, 12-byte reading every 30 min, max 8 km
sensor-to-gateway, 5 years on a 3.6 V / 19,000 mAh primary lithium cell, no cellular
coverage nearby, prefer no per-device fees.

Usage: python3 link_budget_compare.py [--n 3.5] [--sweep] [--container]
All radio/current numbers are ASSUMPTIONS (flagged ASSUMED) - edit TECHS to test others.
"""
import argparse, math
import numpy as np

# ---------------- scenario ----------------
DIST_KM, PL_D0, D0_KM = 8.0, 91.5, 1.0          # free-space PL @ 1 km, ~900 MHz
N_DEVICES, AREA_KM2 = 200, 25.0
PAYLOAD_B, INTERVAL_S = 12, 30 * 60
BATT_MAH, BATT_V, TARGET_YEARS = 19000.0, 3.6, 5.0
DESIGN_MARGIN_DB = 10.0                         # ASSUMED fade/shadowing margin required
USABLE_FRACTION = 0.85                          # ASSUMED: usable fraction of nameplate capacity
SELF_DISCHARGE_MAH_YR = 0.01 * BATT_MAH         # ASSUMED: ~1 %/yr for Li-SOCl2

def lora_airtime_s(payload_b, sf=12, bw=125e3, cr=1, preamble=8, header_b=13):
    """Semtech LoRa airtime formula (explicit header, CRC on, low-data-rate optimise at SF11/12)."""
    de = 1 if sf >= 11 else 0
    pl = payload_b + header_b
    ts = 2 ** sf / bw
    n_pay = 8 + max(math.ceil((8 * pl - 4 * sf + 28 + 16) / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (preamble + 4.25 + n_pay) * ts

LORA_TOA = lora_airtime_s(PAYLOAD_B)

# phases = (label, current mA, seconds) per reporting cycle; sleep current in uA
TECHS = {
    "NB-IoT":       dict(tx_dbm=23, sens_dbm=-129, sleep_ua=5,
                         phases=[("UL tx + repetitions", 220, 2.0), ("RX / connected tail", 46, 3.0)],
                         infra="carrier", fee="per-device plan"),
    "LTE-M (CE-B)": dict(tx_dbm=23, sens_dbm=-125, sleep_ua=10,
                         phases=[("UL tx + repetitions", 250, 2.5), ("RX / connected tail", 50, 3.0)],
                         infra="carrier", fee="per-device plan"),
    "LoRaWAN SF12": dict(tx_dbm=14, sens_dbm=-137, sleep_ua=2,
                         phases=[("SF12 uplink", 44, LORA_TOA), ("RX1+RX2 windows", 12, 1.0), ("MCU + sensor", 5, 0.5)],
                         infra="private gateway", fee="none"),
}
# Task 5: 5G RedCap. 20 MHz: noise = -174 + 10log10(20e6) + 7 dB NF = -94 dBm; SNR ~ -2 dB -> ~ -96 dBm
TECHS_REDCAP = {"5G RedCap": dict(tx_dbm=23, sens_dbm=-96, sleep_ua=30,
                phases=[("UL tx", 300, 1.5), ("RX / connected tail", 80, 2.0)],
                infra="carrier", fee="per-device plan")}

def path_loss(d_km, n):
    return PL_D0 + 10 * n * np.log10(d_km / D0_KM)

def battery_years(t):
    active_s = sum(s for _, _, s in t["phases"])
    mah_cycle = sum(i * s for _, i, s in t["phases"]) / 3600 + t["sleep_ua"] / 1000 * (INTERVAL_S - active_s) / 3600
    cycles_yr = 365 * 24 * 3600 / INTERVAL_S
    annual = mah_cycle * cycles_yr
    return mah_cycle, annual, BATT_MAH * USABLE_FRACTION / (annual + SELF_DISCHARGE_MAH_YR)

def analyse(techs, n):
    pl = float(path_loss(DIST_KM, n))
    rows = []
    for name, t in techs.items():
        mcl = t["tx_dbm"] - t["sens_dbm"]
        mah, annual, yrs = battery_years(t)
        rows.append(dict(name=name, mcl=mcl, pl=pl, margin=mcl - pl, mah=mah, annual=annual, years=yrs, **t))
    return rows

def print_table(rows, title):
    print(f"\n{title}")
    print(f"{'Technology':<14}{'Tx dBm':>7}{'Sens dBm':>9}{'MCL dB':>8}{'PL@8km':>8}{'Margin':>8}{'>=10dB?':>8}"
          f"{'mAh/cyc':>9}{'mAh/yr':>8}{'Life yr':>8}{'>=5yr?':>7}  Infra / fees")
    for r in rows:
        print(f"{r['name']:<14}{r['tx_dbm']:>7}{r['sens_dbm']:>9}{r['mcl']:>8.1f}{r['pl']:>8.1f}{r['margin']:>8.1f}"
              f"{'yes' if r['margin'] >= DESIGN_MARGIN_DB else 'NO':>8}{r['mah']:>9.4f}{r['annual']:>8.0f}"
              f"{r['years']:>8.1f}{'yes' if r['years'] >= TARGET_YEARS else 'NO':>7}  {r['infra']}, {r['fee']}")

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=float, default=3.5)
ap.add_argument("--sweep", action="store_true", help="Task 6: vary path-loss exponent")
ap.add_argument("--container", action="store_true", help="Task 4: shipping-container ocean-crossing scenario")
a = ap.parse_args()

print("=== Part B: LPWAN link budget + battery life ===")
print(f"Model: PL(d) = {PL_D0} + 10*n*log10(d/{D0_KM:g} km), n = {a.n}  ->  PL(8 km) = {path_loss(DIST_KM, a.n):.1f} dB")
print(f"LoRa SF12 airtime for {PAYLOAD_B} B payload (+13 B LoRaWAN overhead): {LORA_TOA:.3f} s")
rows = analyse({**TECHS, **TECHS_REDCAP}, a.n)
print_table(rows[:3], "Assigned comparison (steps 11-13)")
print_table(rows, "Including 5G RedCap (Task 5)")
print(f"(battery: {BATT_MAH:.0f} mAh x {USABLE_FRACTION:.0%} usable, {SELF_DISCHARGE_MAH_YR:.0f} mAh/yr self-discharge; "
      f"{365*24*3600/INTERVAL_S:.0f} reports/yr)")

# scalability sanity check for the recommended option
G = N_DEVICES * LORA_TOA / INTERVAL_S
print(f"\nLoRaWAN load check: duty cycle per device = {LORA_TOA/INTERVAL_S:.3%} (limit 1 % in EU868);"
      f" pure-ALOHA offered load G = {G:.3f} -> worst-case collision prob if ALL 200 use SF12 on one channel ~ {1-math.exp(-2*G):.0%}"
      f" (ADR, multiple channels and gateways cut this sharply)")
side = math.sqrt(AREA_KM2)
print(f"Geometry: 25 km^2 = {side:.0f} x {side:.0f} km; corner-to-corner = {side*math.sqrt(2):.1f} km, so 8 km covers the worst case from a corner gateway")

if a.sweep:
    print("\nTask 6 - sensitivity to path-loss exponent n (margin in dB at 8 km; negative = link fails)")
    print(f"{'n':>5}{'PL dB':>8}" + "".join(f"{r['name']:>15}" for r in rows))
    for n in (2.5, 3.0, 3.5, 4.0, 4.5, 5.0):
        rr = analyse({**TECHS, **TECHS_REDCAP}, n)
        print(f"{n:>5}{rr[0]['pl']:>8.1f}" + "".join(f"{r['margin']:>15.1f}" for r in rr))
    print("Break-even exponent (margin = 0): " + ", ".join(
        f"{r['name']} n={(r['mcl']-PL_D0)/(10*np.log10(DIST_KM/D0_KM)):.2f}" for r in rows))
    print("Even n=4 (dense clutter) leaves 20+ dB on NB-IoT/LTE-M/LoRaWAN, so the RANKING of the three is insensitive to n;\n"
          "only RedCap is sensitive: its link closes at all only for n < 3.05 (and never with the 10 dB design margin). Battery life does not depend on n in this model, so the\n"
          "choice is driven by infrastructure/fees, not by propagation uncertainty.")

if a.container:
    print("\nTask 4 - fleet-tracked shipping container (ocean crossing)")
    for d in (10, 100, 1000):
        pl = float(path_loss(d, a.n))
        print(f"  nearest tower {d:>5} km: PL = {pl:6.1f} dB vs MCLs " +
              ", ".join(f"{r['name']} {r['mcl']:.0f} ({'ok' if r['mcl']>pl else 'FAIL'})" for r in rows))
    print("  A single-distance budget cannot justify a choice here: (1) the question is not 'is the margin positive at one\n"
          "  distance' but 'is any terrestrial tower within reach at all' - mid-ocean the nearest one is hundreds of km away and\n"
          "  beyond the radio horizon, so every terrestrial option fails regardless of MCL; (2) the distance, the serving carrier and\n"
          "  the roaming agreement change continuously along the route (truck, rail, port, ship); (3) mobility/handover and roaming\n"
          "  are binary capabilities that a dB figure cannot express; (4) the ocean leg needs a different link budget altogether\n"
          "  (satellite/NTN: ~500-2,000 km LEO slant range, Doppler, long delay). Hence the unit's answer: LTE-M/RedCap inland + NTN at sea.")

best = max(rows[:3], key=lambda r: (r['infra'] == 'private gateway', r['years']))
print(f"\nRECOMMENDATION: {best['name']} with 1-2 owned gateways. Margin {best['margin']:.1f} dB at 8 km, est. life {best['years']:.0f} yr "
      f"(real life is capped by cell shelf life ~10-15 yr), no recurring fees. NB-IoT/LTE-M close the link on paper but need a carrier "
      f"network that is not there and would add per-device fees across 200 units; LTE-M is also the worst on battery ({rows[1]['years']:.1f} yr, "
      f"{'below' if rows[1]['years']<TARGET_YEARS else 'near'} the 5-yr target).")
