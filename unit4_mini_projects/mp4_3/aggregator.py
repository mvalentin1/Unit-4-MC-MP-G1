#!/usr/bin/env python3
"""Mini Project 4.3 - aggregator/logger + per-topic threshold alerting.

ONE wildcard subscription ("plant1/+/+", QoS 1) feeds everything: every reading is timestamped
and appended to a CSV, the latest value per topic is kept in memory and summarised periodically,
and thresholds are applied per topic (exact-topic override first, then per measurement type).
A new sensor topic under the hierarchy is picked up with no code change.
"""
import argparse, csv, os, threading, time
import paho.mqtt.client as mqtt
import signal
signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))  # SIGTERM behaves like Ctrl-C

# Per-measurement-type thresholds (last topic level) + optional per-topic overrides.
THRESHOLDS = {"temperature": 90.0, "vibration": 8.0}
TOPIC_OVERRIDES = {"plant1/lineB/temperature": 85.0}      # lineB runs a lower limit

ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
ap.add_argument("--client-id", default="aggregator")
ap.add_argument("--filter", default="plant1/+/+")
ap.add_argument("--csv", default="readings.csv")
ap.add_argument("--summary-interval", type=float, default=5.0)
ap.add_argument("--duration", type=float, default=0)
args = ap.parse_args()

latest, status, lock = {}, {}, threading.Lock()
now = lambda: time.strftime("%H:%M:%S")
csvf = open(args.csv, "a", newline="")
writer = csv.writer(csvf)

def threshold_for(topic):
    return TOPIC_OVERRIDES.get(topic, THRESHOLDS.get(topic.rsplit("/", 1)[-1]))

def on_connect(client, userdata, flags, rc, properties):
    client.subscribe(args.filter, qos=1)
    print(f"[{now()}] AGG {args.client_id} subscribed to {args.filter}", flush=True)

def on_message(client, userdata, msg):
    payload, tag = msg.payload.decode(), " (RETAINED)" if msg.retain else ""
    if msg.topic.endswith("_status"):                      # LWT / online announcements
        with lock:
            status[msg.topic] = payload
        print(f"[{now()}] STATUS {msg.topic} = {payload}{tag}", flush=True)
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), msg.topic, payload, int(msg.retain)]); csvf.flush()
        if payload == "offline":
            print(f"[{now()}] ALERT {msg.topic.replace('_status', '')} sensor is OFFLINE (LWT)", flush=True)
        return
    try:
        v = float(payload)
    except ValueError:
        return
    with lock:
        new = msg.topic not in latest
        latest[msg.topic] = (v, time.time())
    writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), msg.topic, v, int(msg.retain)]); csvf.flush()
    print(f"[{now()}] READ {msg.topic} = {v}{tag}" + ("   <-- NEW TOPIC discovered via wildcard" if new else ""), flush=True)
    th = threshold_for(msg.topic)
    if th is not None and v > th:
        print(f"[{now()}] ALERT {msg.topic} = {v} > {th}", flush=True)

def summary_loop():
    while True:
        time.sleep(args.summary_interval)
        with lock:
            rows = sorted(latest.items())
            st = dict(status)
        print(f"[{now()}] --- SUMMARY ({len(rows)} topics) ---", flush=True)
        for t, (v, ts) in rows:
            th = threshold_for(t)
            flag = "  ABOVE LIMIT" if th is not None and v > th else ""
            print(f"    {t:<28} latest={v:<6} age={time.time()-ts:4.1f}s limit={th}{flag}", flush=True)
        for t, s in sorted(st.items()):
            print(f"    {t:<28} {s}", flush=True)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.client_id)
client.on_connect, client.on_message = on_connect, on_message
client.connect(args.host, args.port, keepalive=30)
client.loop_start()
threading.Thread(target=summary_loop, daemon=True).start()
try:
    time.sleep(args.duration) if args.duration else time.sleep(10**9)
except KeyboardInterrupt:
    pass
client.disconnect()
