#!/bin/bash
# Reproduces the Part A demonstration. Offline mode (no pip/Mosquitto): uses ../sim.
# With real paho-mqtt + Mosquitto: remove the PYTHONPATH line and the broker start.
cd "$(dirname "$0")"
export MQTT_PORT=18831 PYTHONPATH=../sim
python3 ../sim/mini_broker.py $MQTT_PORT > logs/broker.log 2>&1 & BROKER=$!
sleep 1
python3 dashboard_subscriber.py > logs/dashboard.log 2>&1 & DASH=$!
python3 alert_subscriber.py     > logs/alert.log 2>&1 & ALERT=$!
sleep 1
python3 sensor_publisher.py --interval 1 --seed 2 > logs/publisher.log 2>&1 & PUB=$!
sleep 7
echo "--- step 9: restart dashboard (late subscriber) while publisher keeps running"
kill -TERM $DASH; sleep 0.5
python3 dashboard_subscriber.py --client-id dashboard-late > logs/dashboard_late.log 2>&1 & DASH2=$!
sleep 4
echo "--- step 10: hard-kill publisher (SIGKILL = no clean disconnect)"
kill -9 $PUB; sleep 3
kill $DASH2 $ALERT $BROKER 2>/dev/null
