#!/bin/bash
# Reproduces the 4.3 demonstration (offline mode: ../sim broker + paho stand-in).
cd "$(dirname "$0")"; rm -f logs/*; export MQTT_PORT=18832 PYTHONPATH=../sim
python3 ../sim/mini_broker.py $MQTT_PORT > logs/broker.log 2>&1 & BROKER=$!; sleep 1
python3 aggregator.py --csv logs/readings.csv --summary-interval 6 > logs/aggregator.log 2>&1 & AGG=$!; sleep 1
python3 sensor.py --topic plant1/lineA/temperature --lo 60 --hi 95 --interval 1 --lwt --seed 3 > logs/s_lineA_temp.log 2>&1 & S1=$!
python3 sensor.py --topic plant1/lineA/vibration  --lo 0  --hi 12 --interval 1.5 --lwt --seed 5 > logs/s_lineA_vib.log 2>&1 & S2=$!
python3 sensor.py --topic plant1/lineB/temperature --lo 60 --hi 95 --interval 2 --seed 11 > logs/s_lineB_temp.log 2>&1 & S3=$!
sleep 6
echo "[demo] late-joining subscriber -> retained messages arrive instantly"
python3 aggregator.py --client-id agg-late --csv logs/late.csv --duration 2 > logs/late_subscriber.log 2>&1
sleep 2
echo "[demo] adding NEW sensor plant1/lineB/vibration while running (aggregator code unchanged)"
python3 sensor.py --topic plant1/lineB/vibration --lo 0 --hi 12 --interval 1.5 --seed 9 > logs/s_lineB_vib.log 2>&1 & S4=$!
sleep 6
echo "[demo] SIGKILL lineA vibration sensor -> broker publishes LWT"
kill -9 $S2; sleep 3
echo "[demo] CLEAN shutdown of lineA temperature sensor (publishes offline itself; LWT not used)"
kill -TERM $S1; sleep 2
kill $S3 $S4 $AGG $BROKER 2>/dev/null
