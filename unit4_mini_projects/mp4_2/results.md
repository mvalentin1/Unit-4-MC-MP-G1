# Mini Project 4.2 - Results table (ranked recommendations, score 0-100)

| Scenario | #1 | #2 | #3 | #4 | #5 | Unit 4.3 expects | Match |
|---|---|---|---|---|---|---|---|
| 1. Smart water meter | NB-IoT (100) | LoRaWAN (79) | LTE-M (61) | 5G RedCap (52) | BLE/Zigbee (16) | NB-IoT | yes |
| 2. Fleet-tracked shipping container | LTE-M (89) | 5G RedCap (84) | NB-IoT (70) | LoRaWAN (50) | BLE/Zigbee (24) | LTE-M | yes |
| 3. Factory-floor sensor network | BLE/Zigbee (100) | LoRaWAN (96) | NB-IoT (74) | LTE-M (59) | 5G RedCap (55) | BLE/Zigbee | yes |
| 4a. Wearable health monitor (phone-paired) | BLE/Zigbee (95) | LoRaWAN (85) | NB-IoT (75) | LTE-M (74) | 5G RedCap (69) | BLE/Zigbee | yes |
| 4b. Wearable medical-alert pendant (standalone) | LTE-M (86) | 5G RedCap (80) | NB-IoT (70) | LoRaWAN (55) | BLE/Zigbee (28) | LTE-M | yes |
| 5. NEW: Remote farm soil sensors (Mini Project 4.1 scenario) | LoRaWAN (96) | NB-IoT (44) | BLE/Zigbee (36) | LTE-M (33) | 5G RedCap (0) | LoRaWAN | yes |

Notes: scenario 2 also emits the advisory to add an NTN/satellite link for the ocean leg; scenario 4a emits the BLE-to-phone relay advisory; 4b is the same wearable re-run as a standalone product (coverage = wide_area_cellular, mobility = wide_area), matching the unit's two wearable designs.

Full per-technology justifications: `python3 selector.py` (saved in results_raw.txt).