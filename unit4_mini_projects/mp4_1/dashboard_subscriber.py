#!/usr/bin/env python3
"""Mini Project 4.1 (Part A) - simulated operator dashboard: prints a timestamped line per event."""
import argparse, os, time
import paho.mqtt.client as mqtt
import signal
signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))  # SIGTERM behaves like Ctrl-C

ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
ap.add_argument("--client-id", default="dashboard")
ap.add_argument("--duration", type=float, default=0, help="exit after N seconds (0 = run until Ctrl-C)")
args = ap.parse_args()
TOPICS = [("factory/line3/temperature", 1), ("factory/line3/status", 1)]

def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(TOPICS)          # subscribing in on_connect re-subscribes after reconnects
    print(f"[{time.strftime('%H:%M:%S')}] DASHBOARD connected, subscribed to {[t for t, _ in TOPICS]}", flush=True)

def on_message(client, userdata, msg):
    tag = " (RETAINED)" if msg.retain else ""
    print(f"[{time.strftime('%H:%M:%S')}] DASHBOARD {msg.topic}: {msg.payload.decode()}{tag}", flush=True)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.client_id)
client.on_connect, client.on_message = on_connect, on_message
client.connect(args.host, args.port, keepalive=30)
client.loop_start()
try:
    time.sleep(args.duration) if args.duration else time.sleep(10**9)
except KeyboardInterrupt:
    pass
client.disconnect()
