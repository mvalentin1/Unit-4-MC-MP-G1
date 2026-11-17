#!/usr/bin/env python3
"""Mini Project 4.1 (Part A) - simulated factory temperature sensor.

Client ID line3-temp-sensor, publishes a random 60-95 reading every 5 s to
factory/line3/temperature at QoS 1, with a Last Will (offline, QoS 1, retained) and an
"online" retained status published right after connecting.

Defaults match the lab sheet; CLI flags let you reuse the script for lab task 1
(a humidity sensor) and shorten the interval for demos.
"""
import argparse, os, random, threading, time
import paho.mqtt.client as mqtt
import signal
signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))  # SIGTERM behaves like Ctrl-C

ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
ap.add_argument("--client-id", default="line3-temp-sensor")
ap.add_argument("--topic", default="factory/line3/temperature")
ap.add_argument("--status-topic", default="factory/line3/status")
ap.add_argument("--interval", type=float, default=5.0)
ap.add_argument("--low", type=float, default=60.0)
ap.add_argument("--high", type=float, default=95.0)
ap.add_argument("--qos", type=int, default=1)
ap.add_argument("--keepalive", type=int, default=10)
ap.add_argument("--seed", type=int, default=None)
ap.add_argument("--retain-first-only", action="store_true",
                help="literal reading of step 5 (only reading #1 retained) - leaves a STALE retained value")
args = ap.parse_args()
if args.seed is not None:
    random.seed(args.seed)

connected = threading.Event()

def on_connect(client, userdata, flags, reason_code, properties):
    # Step 4: announce "online" (retained) immediately after connecting
    client.publish(args.status_topic, "online", qos=1, retain=True)
    print(f"[{time.strftime('%H:%M:%S')}] connected as {args.client_id}; status -> online (retained)", flush=True)
    connected.set()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.client_id)
# Step 4: register the Last Will BEFORE connecting
client.will_set(args.status_topic, "offline", qos=1, retain=True)
client.on_connect = on_connect
client.connect(args.host, args.port, keepalive=args.keepalive)
client.loop_start()
connected.wait(5)

try:
    n = 0
    while True:
        value = round(random.uniform(args.low, args.high), 1)
        # Step 5: retain so a late subscriber gets the LAST KNOWN value. Retaining every
        # reading keeps the broker's copy current; retaining only the first leaves it stale.
        retain = True if not args.retain_first_only else (n == 0)
        client.publish(args.topic, f"{value}", qos=args.qos, retain=retain)
        print(f"[{time.strftime('%H:%M:%S')}] published {args.topic} = {value} (qos={args.qos}, retain={retain})", flush=True)
        n += 1
        time.sleep(args.interval)
except KeyboardInterrupt:
    # A CLEAN exit does not fire the LWT, so say "offline" ourselves or the retained status stays "online".
    client.publish(args.status_topic, "offline", qos=1, retain=True)
    time.sleep(0.2)
    client.disconnect()
    print("clean shutdown: published offline, disconnected")
