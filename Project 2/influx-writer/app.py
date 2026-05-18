import os
import json
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision

# CONFIG
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/data")

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

#  INFLUX CLIENT
influx = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

write_api = influx.write_api()

def write_to_influx(data: dict):

    point = Point("sensor_data")

    # fields
    point.field("proximity", float(data.get("Proximity", 0)))
    point.field("accel_x", float(data.get("AccelX", 0)))
    point.field("accel_y", float(data.get("AccelY", 0)))
    point.field("accel_z", float(data.get("AccelZ", 0)))
    point.field("gyro_x", float(data.get("GyroX", 0)))
    point.field("gyro_y", float(data.get("GyroY", 0)))
    point.field("gyro_z", float(data.get("GyroZ", 0)))
    point.field("button", int(data.get("Button", 0)))

    if "CreatedAt" in data:
        point.field("created_at", float(data["CreatedAt"]))

    if "ReceivedAt" in data:
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(data["ReceivedAt"])
            point.time(ts, WritePrecision.MS)
        except:
            pass
        
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

    print("[INFLUX] written point")


# MQTT CALLBACK
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

        print("[MQTT]", data)

        write_to_influx(data)

    except Exception as e:
        print("[ERROR] processing message:", e)


def main():
    client = mqtt.Client()
    
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)

    client.subscribe(MQTT_TOPIC)

    print("[INFO] Influx writer started")
    client.loop_forever()


if __name__ == "__main__":
    main()