import network
import machine
import time
from umqtt.simple import MQTTClient
from umqtt.simple import MQTTException
import ujson
import ahtx0

# ============ CONFIGURATION ============
WIFI_SSID = "SSID"
WIFI_PWD = "PASSWORD"

BROKER_IP = "147.229.148.105"
BROKER_PORT = 11883
GROUP_NUM = "9"

TOPIC_DATA = f"IoTProject/{GROUP_NUM}/grill/teplota"
TOPIC_TARGET = f"IoTProject/{GROUP_NUM}/grill/target"
CLIENT_ID = f"grill_sensor_{GROUP_NUM}"

INTERVAL_FAR = 30
INTERVAL_MEDIUM = 10
INTERVAL_CLOSE = 5

# ============ HARDWARE INIT ============
i2c1 = machine.I2C(1, scl=machine.Pin(3), sda=machine.Pin(2), freq=400000)
tmp_sensor = ahtx0.AHT20(i2c1)
tmp_sensor.initialize()

led = machine.Pin("LED", machine.Pin.OUT)

# ============ STATE ============
target_temp = 75.0
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
    global target_temp
    try:
        js = ujson.loads(msg)
        if "target" in js:
            target_temp = float(js["target"])
            print(f"  [RX] New target: {target_temp}C")
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

    client.subscribe(TOPIC_TARGET)
    print(f"Subscribed to: {TOPIC_TARGET}")
    return client


# ============ MAIN ============
print("=" * 40)
print("IoTMasterChef - Grill Thermometer")
print("=" * 40)

wlan = connect_wifi()
client = connect_mqtt()

led.on()
msg_counter = 0
keepalive_counter = 0

print(f"\nPublishing to: {TOPIC_DATA}")
print(f"Default target: {target_temp}C")
print(f"Intervals: far={INTERVAL_FAR}s, medium={INTERVAL_MEDIUM}s, close={INTERVAL_CLOSE}s")
print("-" * 40)

while True:
    try:
        client.check_msg()

        keepalive_counter += 1

        if keepalive_counter >= publish_interval * 2:
            keepalive_counter = 0
            msg_counter += 1

            meat_temp = tmp_sensor.temperature
            grill_temp = meat_temp + 80.0

            publish_interval = get_interval(meat_temp, target_temp)

            payload = ujson.dumps({
                "maso": round(meat_temp, 1),
                "gril": round(grill_temp, 1)
            })
            client.publish(TOPIC_DATA, payload)

            status = "ALARM!" if meat_temp >= target_temp else "OK"
            print(f"[{msg_counter}] Maso:{meat_temp:.1f}C Gril:{grill_temp:.1f}C Target:{target_temp:.1f}C Interval:{publish_interval}s [{status}]")

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
