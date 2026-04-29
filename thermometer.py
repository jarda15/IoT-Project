import network
import machine
import time
from simple import MQTTClient
from simple import MQTTException
import ujson
import ahtx0

# ============ CONFIGURATION ============
WIFI_SSID = "LPWAN-IoT-06"
WIFI_PWD = "LPWAN-IoT-06-WiFi"

BROKER_IP = "147.229.148.105"
BROKER_PORT = 11883
GROUP_NUM = "9"

TOPIC_DATA = f"IoTProject/{GROUP_NUM}/grill/teplota"
TOPIC_TARGET_GRILL = f"IoTProject/{GROUP_NUM}/grill/Tgrill"
TOPIC_TARGET_MASO = f"IoTProject/{GROUP_NUM}/grill/Tmaso"
CLIENT_ID = f"grill_sensor_{GROUP_NUM}"

INTERVAL_FAR = 30
INTERVAL_MEDIUM = 10
INTERVAL_CLOSE = 5

# ============ HARDWARE INIT ============
i2c1 = machine.I2C(1, scl=machine.Pin(3), sda=machine.Pin(2), freq=400000)
tmp_sensor1 = ahtx0.AHT20(i2c1)
tmp_sensor1.initialize()


i2c0 = machine.I2C(0, scl=machine.Pin(5), sda=machine.Pin(4), freq=400000)
tmp_sensor2 = ahtx0.AHT20(i2c0)
tmp_sensor2.initialize()


led = machine.Pin("LED", machine.Pin.OUT)

# ============ STATE ============
target_temp_maso = 75.0
target_temp_grill = 200.0

publish_interval = INTERVAL_FAR


def get_interval(current_temp, target):
    diff = target - current_temp
    if diff <= 5:
        return INTERVAL_CLOSE
    elif diff <= 20:
        return INTERVAL_MEDIUM
    else:
        return INTERVAL_FAR


# ============ FUNKCIE ============
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)
    time.sleep(1)
    wlan.connect(WIFI_SSID, WIFI_PWD)

    print("Connecting to WiFi...")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.5)

    print(f"\nConnected - IP: {wlan.ifconfig()[0]}")
    return wlan


def on_message(topic, msg):
    global target_temp_maso, target_temp_grill
    try:
        js = ujson.loads(msg)
        if "masoTarget" in js:
            target_temp_maso = float(js["masoTarget"])
        if "grillTarget" in js:
            target_temp_grill = float(js["grillTarget"])
    except Exception as e:
        print(f"  Parse error: {e}")


def connect_mqtt():
    client = MQTTClient(
        CLIENT_ID,
        BROKER_IP,
        port=BROKER_PORT,
        keepalive=60
    )
    client.set_callback(on_message)
    client.connect()
    print(f"MQTT connected as '{CLIENT_ID}'")

    client.subscribe(TOPIC_TARGET_GRILL)
    print(f"Subscribed to: {TOPIC_TARGET_GRILL}")

    client.subscribe(TOPIC_TARGET_MASO)
    print(f"Subscribed to: {TOPIC_TARGET_MASO}")
    return client


# ============ MAIN ============
print("=" * 40)
print("IoTMasterChef - Grill Thermometer")
print("=" * 40)

wlan = connect_wifi()
client = connect_mqtt()

led.on()
msg_counter = 0
keepalive_counter = 9999

print(f"\nPublishing to: {TOPIC_DATA}")
print(f"Default target: {target_temp_maso} C,{target_temp_grill} C")
print(f"Intervals: far={INTERVAL_FAR}s, medium={INTERVAL_MEDIUM}s, close={INTERVAL_CLOSE}s")
print("-" * 40)

while True:
    try:
        client.check_msg()
        keepalive_counter += 1

        if keepalive_counter >= (publish_interval * 2):
            keepalive_counter = 0
            msg_counter += 1

            meat_temp = tmp_sensor1.temperature
            grill_temp = tmp_sensor2.temperature

            int_m = get_interval(meat_temp, target_temp_maso)
            int_g = get_interval(grill_temp, target_temp_grill)
            publish_interval = min(int_m, int_g)

            payload = ujson.dumps({
                "maso": round(meat_temp, 1),
                "gril": round(grill_temp, 1)
            })
            client.publish(TOPIC_DATA, payload)
            
            status_m = "ALARM!" if meat_temp >= target_temp_maso else "ok"
            status_g = "ALARM!" if grill_temp >= target_temp_grill else "ok"

            print(f"[{msg_counter}] "
                  f"MEAT: {meat_temp:.1f}/{target_temp_maso:.0f} C ({status_m}) | "
                  f"GRILL: {grill_temp:.1f}/{target_temp_grill:.0f} C ({status_g}) | "
                  f"Next in: {publish_interval}s")

        time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nDisconnecting...")
        client.disconnect()
        wlan.disconnect()
        wlan.active(False)
        led.off()
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)

