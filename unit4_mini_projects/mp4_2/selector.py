#!/usr/bin/env python3
"""Mini Project 4.2 - rule-based IoT connectivity selector (Section 4.3 decision framework).

Every number below is traceable to the Section 4.2 comparison table or the Section 4.3
Decision Summary Table (see METHODOLOGY.md). Run:  python3 selector.py            (validation of 5 scenarios)
                                                   python3 selector.py --interactive
"""
import sys
from dataclasses import dataclass

TECHS = ["NB-IoT", "LTE-M", "LoRaWAN", "5G RedCap", "BLE/Zigbee"]
CARRIER = {"NB-IoT", "LTE-M", "5G RedCap"}
SELF_OWNED = {"LoRaWAN", "BLE/Zigbee"}

# ---- capability matrix, 0-5 (transcribed from Sections 4.2 / 4.3) ------------------------
CAP = {  # tech: data_rate, battery, mobility, self_ownedness, low_cost
    "NB-IoT":     dict(data=1, battery=5, mobility=1, owned=0, cost=4),   # very low | years | none/low | carrier | low
    "LTE-M":      dict(data=3, battery=3, mobility=5, owned=0, cost=3),   # low-mod | months-years | full cellular | carrier | low-mod
    "LoRaWAN":    dict(data=1, battery=5, mobility=3, owned=4, cost=4),   # very low | years | limited | usually self | low
    "5G RedCap":  dict(data=4, battery=3, mobility=5, owned=0, cost=2),   # moderate | months-years | full cellular | carrier | moderate
    "BLE/Zigbee": dict(data=3, battery=3, mobility=2, owned=5, cost=5),   # low-mod short range | days-years | local only | fully self | very low
}
# coverage suitability per requested coverage category (0-5)
COVERAGE = {
    "deep_indoor":        {"NB-IoT": 5, "LTE-M": 3, "LoRaWAN": 3, "5G RedCap": 2, "BLE/Zigbee": 1},
    "wide_area_cellular": {"NB-IoT": 4, "LTE-M": 4, "LoRaWAN": 2, "5G RedCap": 4, "BLE/Zigbee": 0},
    "long_range_rural":   {"NB-IoT": 2, "LTE-M": 2, "LoRaWAN": 5, "5G RedCap": 1, "BLE/Zigbee": 0},
    "short_range_only":   {"NB-IoT": 2, "LTE-M": 2, "LoRaWAN": 3, "5G RedCap": 2, "BLE/Zigbee": 5},
}
WEIGHTS = dict(data=1.0, coverage=1.5, battery=1.5, mobility=1.5, ownership=1.0, cost=1.0)
SHORTFALL_PEN, SURPLUS_PEN = 1.5, 0.25     # per level a capability is below / above the requirement

@dataclass
class Scenario:
    name: str
    msg_bytes: float                 # per message
    interval_s: float                # between messages
    coverage: str                    # key of COVERAGE
    battery_years: float
    mobility: str                    # stationary | local | wide_area | global_roaming
    ownership: str                   # carrier | self_owned | no_preference
    device_count: int
    budget: str                      # tight | moderate | generous
    peak_kbps: float = 0.0           # optional burst rate
    cellular_available: bool = True  # constraint flag: carrier coverage exists at the site?
    offshore_segment: bool = False   # constraint flag: part of the route has no terrestrial coverage

# ---- requirement -> 0..5 level mappings ----------------------------------------------
def level_data(s):
    kbps = max(s.msg_bytes * 8 / s.interval_s / 1000, s.peak_kbps)
    return 1 if kbps <= 10 else 2 if kbps <= 100 else 3 if kbps <= 1000 else 4 if kbps <= 10000 else 5
def level_battery(y):
    return 1 if y < 0.1 else 2 if y < 1 else 3 if y < 3 else 4 if y < 7 else 5
LEVEL_MOBILITY = dict(stationary=1, local=2, wide_area=4, global_roaming=5)
LEVEL_OWNER = dict(carrier=0, self_owned=5)
def level_cost(s):
    return min(5, dict(generous=1, moderate=3, tight=4)[s.budget] + (1 if s.device_count >= 1000 else 0))

def need_fit(req, cap):                       # capability should meet the requirement
    return max(0.0, 5 - SHORTFALL_PEN * max(0, req - cap) - SURPLUS_PEN * max(0, cap - req))

def score(s: Scenario, weights=WEIGHTS):
    req = dict(data=level_data(s), battery=level_battery(s.battery_years), mobility=LEVEL_MOBILITY[s.mobility],
               cost=level_cost(s))
    out = []
    for t in TECHS:
        c = CAP[t]
        fit = dict(data=need_fit(req["data"], c["data"]), coverage=float(COVERAGE[s.coverage][t]),
                   battery=need_fit(req["battery"], c["battery"]), mobility=need_fit(req["mobility"], c["mobility"]),
                   cost=need_fit(req["cost"], c["cost"]))
        w = dict(weights)
        if s.ownership == "no_preference":
            fit["ownership"], w["ownership"] = 0.0, 0.0
        else:
            fit["ownership"] = 5 - abs(LEVEL_OWNER[s.ownership] - c["owned"])
        base = 20 * sum(w[a] * fit[a] for a in fit) / sum(w.values())     # 0..100
        adj, why = 0.0, []
        # ---- rule-based constraints (points on the 0-100 scale) ----
        if t == "LoRaWAN" and req["mobility"] >= 4:
            adj -= 20; why.append("LoRaWAN lacks cellular-style handover (mobility>=wide-area) -20")
        if fit["coverage"] <= 1:
            adj -= 30; why.append("cannot close the link for this coverage category -30")
        if t in CARRIER and not s.cellular_available:
            adj -= 40; why.append("no carrier coverage at site -40")
        if (req["cost"] >= 4 and s.device_count >= 100 and req["mobility"] <= 1 and s.ownership != "carrier"
                and t in SELF_OWNED and s.cellular_available):
            adj += 10; why.append("fixed-site fleet + severe cost sensitivity favours self-owned (no per-device fees) +10")
        if req["battery"] == 5 and c["battery"] < 4:
            adj -= 10; why.append("multi-year non-replaceable battery needs PSM/duty-cycle class -10")
        if req["data"] >= 4 and c["data"] <= 1:
            adj -= 30; why.append("data-rate need beyond very-low-rate LPWAN -30")
        out.append(dict(tech=t, base=base, adj=adj, raw=base + adj, total=min(100.0, max(0.0, base + adj)), fit=fit, why=why))
    out.sort(key=lambda r: -r["raw"])      # rank on the unclamped score; display is clamped to 0-100
    notes = []
    if s.offshore_segment:
        notes.append("Part of the journey has no terrestrial coverage: add an NTN/satellite IoT messaging link (Sec. 4.5) "
                     "for that leg - real deployments combine technologies.")
    if s.coverage == "short_range_only" and s.mobility in ("local", "wide_area", "global_roaming"):
        notes.append("Short-range radio needs a relay: pair via BLE to a smartphone/hub that provides the wide-area backhaul; "
                     "if the product must work standalone, re-run with coverage=wide_area_cellular.")
    return req, out, notes

def justify(r, req, s):
    f = {a: v for a, v in r["fit"].items() if not (a == "ownership" and s.ownership == "no_preference")}
    best = sorted(f, key=lambda a: -f[a] * WEIGHTS[a])[:2]
    worst = min(f, key=lambda a: f[a])
    txt = f"Strong on {best[0]} and {best[1]}; " + (f"weakest on {worst} ({f[worst]:.1f}/5)." if f[worst] < 4.5 else "no weak axis.")
    if r["why"]:
        txt += " Rule: " + "; ".join(r["why"]) + "."
    return txt

def report(s: Scenario, verbose=True):
    req, ranked, notes = score(s)
    print(f"\n### {s.name}")
    print(f"requirement levels (0-5): data={req['data']} battery={req['battery']} mobility={req['mobility']} cost={req['cost']} | "
          f"coverage={s.coverage} | ownership={s.ownership}")
    for i, r in enumerate(ranked, 1):
        print(f"{i}. {r['tech']:<11} {r['total']:5.1f}  (weighted fit {r['base']:.1f}, rules {r['adj']:+.0f})  {justify(r, req, s) if verbose else ''}")
    for n in notes:
        print("   NOTE:", n)
    return ranked

SCENARIOS = [
    Scenario("1. Smart water meter", 20, 86400, "deep_indoor", 9, "stationary", "carrier", 1_000_000, "moderate"),
    Scenario("2. Fleet-tracked shipping container", 200, 3600, "wide_area_cellular", 2, "global_roaming", "no_preference",
             10_000, "moderate", offshore_segment=True),
    Scenario("3. Factory-floor sensor network", 100, 10, "short_range_only", 5, "stationary", "self_owned", 500, "tight"),
    Scenario("4a. Wearable health monitor (phone-paired)", 200, 1, "short_range_only", 0.003, "local", "no_preference",
             100_000, "moderate"),
    Scenario("4b. Wearable medical-alert pendant (standalone)", 200, 1, "wide_area_cellular", 0.003, "wide_area", "no_preference",
             100_000, "moderate"),
    Scenario("5. NEW: Remote farm soil sensors (Mini Project 4.1 scenario)", 12, 1800, "long_range_rural", 5, "stationary",
             "no_preference", 200, "moderate", cellular_available=False),
]
EXPECTED = {"1": "NB-IoT", "2": "LTE-M", "3": "BLE/Zigbee", "4a": "BLE/Zigbee", "4b": "LTE-M", "5": "LoRaWAN"}

def interactive():
    print("Enter a new scenario (Enter = default)")
    ask = lambda q, d: (input(f"{q} [{d}]: ").strip() or str(d))
    s = Scenario(ask("name", "my scenario"), float(ask("message bytes", 20)), float(ask("interval seconds", 3600)),
                 ask("coverage (deep_indoor|wide_area_cellular|long_range_rural|short_range_only)", "wide_area_cellular"),
                 float(ask("battery target years", 5)), ask("mobility (stationary|local|wide_area|global_roaming)", "stationary"),
                 ask("ownership (carrier|self_owned|no_preference)", "no_preference"), int(ask("device count", 1000)),
                 ask("budget (tight|moderate|generous)", "moderate"),
                 cellular_available=ask("cellular coverage at site? (y/n)", "y").lower().startswith("y"))
    report(s)

if __name__ == "__main__":
    if "--interactive" in sys.argv:
        interactive()
    else:
        print("# Validation run: ranked recommendations (score 0-100)")
        ok = 0
        for sc in SCENARIOS:
            top = report(sc)[0]["tech"]
            key = sc.name.split(".")[0]
            ok += top == EXPECTED[key]
            print(f"   -> top pick {top}; unit's reasoning expects {EXPECTED[key]}: {'MATCH' if top == EXPECTED[key] else 'DIVERGES'}")
        print(f"\n{ok}/{len(SCENARIOS)} top picks match Section 4.3 reasoning")
