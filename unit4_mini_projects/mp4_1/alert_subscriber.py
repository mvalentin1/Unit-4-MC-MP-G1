#!/usr/bin/env python3
"""Mini Project 4.1 (Part A) - wildcard alert subscriber: ALERT only when a reading exceeds the threshold."""
import argparse, os, time
import paho.mqtt.client as mqtt
import signal
signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))  # SIGTERM behaves like Ctrl-C

ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
ap.add_argument("--client-id", default="alert-service")
ap.add_argument("--filter", default="factory/+/temperature", help="lab task 1: use factory/line3/+")
ap.add_argument("--threshold", type=float, default=90.0)
ap.add_argument("--duration", type=float, default=0)
args = ap.parse_args()

def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(args.filter, qos=1)
    print(f"[{time.strftime('%H:%M:%S')}] ALERT-SVC connected, subscribed to {args.filter} (threshold {args.threshold})", flush=True)

def on_message(client, userdata, msg):
    try:
        value = float(msg.payload.decode())
    except ValueError:
        return                          # ignore non-numeric payloads
    if value > args.threshold:
        print(f"[{time.strftime('%H:%M:%S')}] ALERT {msg.topic} = {value} exceeds {args.threshold}", flush=True)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.client_id)
client.on_connect, client.on_message = on_connect, on_message
client.connect(args.host, args.port, keepalive=30)
client.loop_start()
try:
    time.sleep(args.duration) if args.duration else time.sleep(10**9)
except KeyboardInterrupt:
    pass
client.disconnect()
