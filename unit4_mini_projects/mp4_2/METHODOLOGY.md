# Mini Project 4.2 - Scoring methodology (one page)

**Goal.** Turn the Section 4.3 decision framework into an auditable recommender over NB-IoT, LTE-M, LoRaWAN, 5G RedCap and BLE/Zigbee.

## 1. Inputs (the six Section 4.3 axes)
| Axis | Input | Mapped to level 0-5 |
|---|---|---|
| Data rate | message bytes + interval (+ optional peak kbps) | max(avg, peak) kbps: <=10 -> 1, <=100 -> 2, <=1,000 -> 3, <=10,000 -> 4, else 5 |
| Coverage | deep_indoor / wide_area_cellular / long_range_rural / short_range_only | used directly as a category column (below) |
| Battery | target years | <0.1 -> 1 (nightly charge), <1 -> 2, <3 -> 3, <7 -> 4, >=7 -> 5 |
| Mobility | stationary / local / wide_area / global_roaming | 1 / 2 / 4 / 5 |
| Ownership | carrier / self_owned / no_preference | 0 / 5 / axis switched off (weight 0) |
| Cost | device count + budget tier | tier: generous 1, moderate 3, tight 4; +1 if >= 1,000 devices (cap 5) |

## 2. Capability matrix (0-5), transcribed from the Section 4.2 table and 4.3 Decision Summary Table
| Tech | Data | Battery | Mobility | Self-owned | Low cost | Source wording |
|---|---|---|---|---|---|---|
| NB-IoT | 1 | 5 | 1 | 0 | 4 | very low rate; years; none/low; carrier; low |
| LTE-M | 3 | 3 | 5 | 0 | 3 | low-moderate; months-years; full cellular; carrier; low-moderate |
| LoRaWAN | 1 | 5 | 3 | 4 | 4 | very low; years; limited; usually self-owned; low |
| 5G RedCap | 4 | 3 | 5 | 0 | 2 | moderate; months-years; full cellular; carrier; moderate |
| BLE/Zigbee | 3 | 3 | 2 | 5 | 5 | low-moderate (short range); days-years; local only; fully self-owned; very low |

Coverage suitability by category: deep_indoor NB 5, LTE-M 3, LoRa 3, RedCap 2, BLE 1; wide_area_cellular 4/4/2/4/0; long_range_rural 2/2/5/1/0; short_range_only 2/2/3/2/5 (order NB, LTE-M, LoRa, RedCap, BLE). Rationale: NB-IoT "best deep indoor"; LoRaWAN "very long range (rural)"; cellular options are good only where carrier coverage exists; BLE/Zigbee "very short (meters)".

## 3. Weighted-sum score
Per axis, a *fit* in 0-5. Capability axes (data, battery, mobility, cost): `fit = 5 - 1.5*max(0, need-cap) - 0.25*max(0, cap-need)` - a shortfall hurts six times more than over-provision (which only wastes power/cost). Ownership: `5 - |need - cap|`. Coverage: the category table value.
Weights: coverage 1.5, battery 1.5, mobility 1.5, data 1.0, ownership 1.0, cost 1.0 (coverage, battery, mobility are the axes that can make a technology *unusable*; data, ownership, cost are trade-offs). Base score = 20 x weighted mean fit (0-100).

## 4. Constraint rules (points added to the 0-100 score; each is printed in the justification)
1. LoRaWAN and mobility need >= wide-area: **-20** (no cellular-style handover, Sec. 4.3 mobility axis).
2. Coverage fit <= 1 (cannot close the link, e.g. BLE for a buried meter): **-30**.
3. Technology is carrier-provided but no carrier coverage at the site: **-40** (the unit's "gateway-dependent vs carrier" ownership axis).
4. Fixed-site fleet (stationary), cost level >= 4, >= 100 devices, carrier not preferred: self-owned options **+10** (one-time gateway cost, no recurring fees).
5. Battery need = 5 (non-replaceable multi-year cell) and capability < 4: **-10** (PSM/eDRX or low-duty-cycle needed).
6. Data need >= 4 but capability <= 1: **-30** (beyond very-low-rate LPWAN).
Ranking uses the unclamped sum; displayed scores are clamped to 0-100.
Advisories (not scored): ocean/no-terrestrial leg -> add NTN/satellite link; short-range + mobility -> BLE needs a phone/hub relay.

## 5. Validation (see results.md)
All five unit scenarios (wearable run in both its designs) reproduce the unit's reasoning: water meter -> NB-IoT; container -> LTE-M (+NTN at sea, RedCap a close second, matching "or RedCap where available"); factory -> BLE/Zigbee with private LoRaWAN second ("if the campus is larger"); wearable -> BLE to phone, or LTE-M (RedCap 2nd) standalone. New scenario (4.1 farm) -> LoRaWAN.

## 6. Known limitations
Ordinal 0-5 scores compress real differences; the container pick is a *terrestrial-leg* pick, which the tool cannot express as a combination except through the advisory note; LTE-M vs RedCap separation (5 points) is small and depends on the cost mapping; weights and penalties are judgement values - the audit trail is the printed per-axis fits and rule lines. Sensitivity: change `WEIGHTS`, `SHORTFALL_PEN`, `SURPLUS_PEN` at the top of selector.py.

Observed weakness: in scenario 4a LoRaWAN ranks 2nd for a phone-paired wearable (85) only because the wearable's requirements are so easy (nightly charge, tiny data) that almost any radio "fits"; the tool has no axis for form factor/radio size, so a score near the top says "requirements are met", not "this is a sensible product choice". The top pick is still correct.
