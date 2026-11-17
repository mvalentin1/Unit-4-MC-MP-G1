#!/usr/bin/env python3
"""Mini Project 4.3 - one independent simulated sensor publisher (run one process per sensor).

Examples:
  python3 sensor.py --topic plant1/lineA/temperature --lo 60 --hi 95 --lwt
  python3 sensor.py --topic plant1/lineA/vibration  --lo 0  --hi 12 --interval 2 --lwt
  python3 sensor.py --topic plant1/lineB/temperature --lo 60 --hi 95
QoS 1 by default. Every reading is retained (the broker always holds the latest value).
With --lwt: registers a Last Will "offline" on <topic>_status (QoS 1, retained) before
connecting and publishes "online" right after.
"""
import argparse, os, random, threading, time
import paho.mqtt.client as mqtt
import signal
signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))  # SIGTERM behaves like Ctrl-C

ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
ap.add_argument("--topic", required=True)
ap.add_argument("--client-id", default=None)
ap.add_argument("--interval", type=float, default=2.0)
ap.add_argument("--lo", type=float, default=60.0)
ap.add_argument("--hi", type=float, default=95.0)
ap.add_argument("--qos", type=int, default=1)
ap.add_argument("--no-retain", action="store_true")
ap.add_argument("--lwt", action="store_true")
ap.add_argument("--keepalive", type=int, default=5)
ap.add_argument("--seed", type=int, default=None)
args = ap.parse_args()
if args.seed is not None:
    random.seed(args.seed)
cid = args.client_id or "sensor-" + args.topic.replace("/", "-")
status_topic = args.topic + "_status"
up = threading.Event()

def on_connect(client, userdata, flags, rc, properties):
    if args.lwt:
        client.publish(status_topic, "online", qos=1, retain=True)
    print(f"[{time.strftime('%H:%M:%S')}] {cid} connected" + (f"; {status_topic} -> online" if args.lwt else ""), flush=True)
    up.set()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)
if args.lwt:
    client.will_set(status_topic, "offline", qos=1, retain=True)      # must precede connect()
client.on_connect = on_connect
client.connect(args.host, args.port, keepalive=args.keepalive)
client.loop_start()
up.wait(5)
try:
    while True:
        v = round(random.uniform(args.lo, args.hi), 1)
        client.publish(args.topic, str(v), qos=args.qos, retain=not args.no_retain)
        print(f"[{time.strftime('%H:%M:%S')}] {cid} published {args.topic} = {v}", flush=True)
        time.sleep(args.interval)
except KeyboardInterrupt:
    if args.lwt:                       # clean exit does NOT fire the LWT -> publish offline ourselves
        client.publish(status_topic, "offline", qos=1, retain=True)
        time.sleep(0.2)
    client.disconnect()
