# CE80762 Unit 4 - Mini Projects 4.1, 4.2, 4.3

| Folder | Contents |
|---|---|
| `mp4_1/` | `sensor_publisher.py`, `dashboard_subscriber.py`, `alert_subscriber.py` (Part A), `link_budget_compare.py` (Part B), `run_part_a_demo.sh`, `logs/` (broker/publisher/dashboard/late-dashboard/alert logs + `part_b_results.txt`) |
| `mp4_2/` | `selector.py` (rule-based recommender), `METHODOLOGY.md` (one-page writeup), `results.md` (ranked table for 4 unit scenarios + 1 new), `results_raw.txt` (full justifications) |
| `mp4_3/` | `sensor.py`, `aggregator.py`, `run_demo.sh`, `logs/` (aggregator, late subscriber, broker, readings.csv), `report.md` (705-word report) |
| `sim/` | `mini_broker.py` + a minimal `paho` stand-in, used ONLY because this sandbox had no internet, no paho-mqtt and no Mosquitto |

## Running on your own machine (real paho-mqtt, paper-spec setup)
```
python3 -m venv venv && source venv/bin/activate && pip install paho-mqtt numpy   # paho-mqtt >= 2.0
# broker: local `mosquitto` or  export MQTT_HOST=test.mosquitto.org  (port 1883)
python3 mp4_1/dashboard_subscriber.py &  python3 mp4_1/alert_subscriber.py &  python3 mp4_1/sensor_publisher.py
python3 mp4_1/link_budget_compare.py --sweep --container
python3 mp4_2/selector.py            # or --interactive
```
Do not put `sim/` on PYTHONPATH there. Re-capture the logs against Mosquitto for submission if your marker requires a real broker.

## Things to know
* Logs here come from the sim broker and paho stand-in speaking real MQTT 3.1.1 over TCP; QoS 2 is not implemented (granted as QoS 1), so lab tasks 2-3 (QoS 0/2 comparisons) are not run. Lab task 1 is supported by CLI flags (`--topic`, `--filter factory/line3/+`); lab tasks 4, 5, 6 are in `link_budget_compare.py` (`--container`, RedCap row, `--sweep`).
* Step 5 deviation: the sheet says to retain only the first reading, which would leave a stale value for late joiners. The scripts retain every reading (`--retain-first-only` reproduces the literal version).
* Battery/current figures in Part B are stated assumptions (flagged in the script), so the 5-yr pass/fail for NB-IoT (5.3 yr) and LTE-M (4.0 yr) is close to the line and assumption-sensitive.
