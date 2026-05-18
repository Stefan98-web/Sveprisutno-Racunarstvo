import asyncio
import os
import json
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakScanner

# CONFIG
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/data")

DEVICE_NAME = "Nano33-Sensors"
CHAR_UUID = "2A56"
# MQTT
client = mqtt.Client()
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

# PARSER (string -> dict)
def parse_payload(data: str):
    try:
        parts = data.split(",")

        result = {}
        for p in parts:
            if ":" in p:
                k, v = p.split(":")
                result[k.strip()] = v.strip()

        # convert numeric fields
        for k in result:
            try:
                result[k] = float(result[k])
            except:
                pass

        return result
    except:
        return None

# BLE HANDLER
async def handle_device(device):
    print(f"[BLE] Connecting to {device.name} ...")

    try:
        async with BleakClient(device) as client_ble:
            print("[BLE] Connected!")

            def callback(sender, data):
                try:
                    text = data.decode("utf-8").strip()
                    print("[BLE RAW]", text)

                    parsed = parse_payload(text)
                    if parsed:
                        parsed["ReceivedAt"] = datetime.now(timezone.utc).isoformat()

                        payload = json.dumps(parsed)

                        client.publish(MQTT_TOPIC, payload)
                        print("[MQTT] sent:", payload)

                except Exception as e:
                    print("Parse error:", e)

            await client_ble.start_notify(CHAR_UUID, callback)

            while client_ble.is_connected:
                await asyncio.sleep(0.5)

            print(f"[BLE] Device {device.name} disconnected.")

    except Exception as e:
        print("[BLE] connection error:", e)

# SCAN LOOP
async def run():
    print("[BLE] Scanning...")

    while True:
        devices = await BleakScanner.discover()

        target = None
        for d in devices:
            if d.name == DEVICE_NAME:
                target = d
                break

        if target:
            try:
                await handle_device(target)
            except Exception as e:
                print("[BLE] disconnected:", e)

        await asyncio.sleep(3)


if __name__ == "__main__":
    print("[APP STARTED]")
    asyncio.run(run())