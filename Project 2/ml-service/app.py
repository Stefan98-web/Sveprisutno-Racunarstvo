import json
import numpy as np
import os
import requests
import paho.mqtt.client as mqtt
from collections import deque

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

INPUT_TOPIC = os.getenv("INPUT_MQTT_TOPIC")
OUTPUT_TOPIC = os.getenv("OUTPUT_MQTT_TOPIC")
EI_URL = os.getenv("EI_URL")

WINDOW_SIZE = 40
buffer = deque(maxlen=WINDOW_SIZE)

client = mqtt.Client()


def classify(window):
    payload = {"features": window.flatten().tolist()}
    r = requests.post(EI_URL, json=payload)

    if r.status_code != 200:
        return {"error": r.text}

    return r.json()

def filter_result(result):
    try:
        classes = result["result"]["classification"]

        filtered = {
            "idle": float(classes.get("idle", 0)),
            "movement": float(classes.get("movement", 0)),
            "violent_movement": float(classes.get("violent_movement", 0))
        }

        return filtered

    except Exception as e:
        return {"error": str(e)}

def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())

    features = [
        float(data["AccelX"]),
        float(data["AccelY"]),
        float(data["AccelZ"]),
        float(data["GyroX"]),
        float(data["GyroY"]),
        float(data["GyroZ"]),
    ]

    buffer.append(features)

    if len(buffer) == WINDOW_SIZE:
        window = np.array(buffer)

        result = classify(window)

        filtered = filter_result(result)

        client.publish(OUTPUT_TOPIC, json.dumps(filtered))
        print("[ML]", filtered)


client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.subscribe(INPUT_TOPIC)

print("ML service started")
client.loop_forever()