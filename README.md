# IoTMasterChef — Bezdrátový teploměr do grilu

> **BPC-IoT Projekt #5** — Bezdrátový teploměr měřící teplotu uvnitř potraviny a v prostoru grilu, s přenosem dat přes Wi-Fi/MQTT na uživatelskou aplikaci s vizualizací a zvukovou notifikací.

---

## Obsah

- [Popis projektu](#popis-projektu)
- [Architektura řešení](#architektura-řešení)
- [Teoretická část — zdůvodnění návrhu](#teoretická-část--zdůvodnění-návrhu)
  - [Volba platformy: Raspberry Pi Pico W](#volba-platformy-raspberry-pi-pico-w)
  - [Volba bezdrátové technologie: Wi-Fi](#volba-bezdrátové-technologie-wi-fi)
  - [Volba aplikačního protokolu: MQTT](#volba-aplikačního-protokolu-mqtt)
  - [Senzory: prototyp vs. reálné nasazení](#senzory-prototyp-vs-reálné-nasazení)
  - [Napájení a výdrž baterie](#napájení-a-výdrž-baterie)
  - [Úspora energie a adaptivní interval](#úspora-energie-a-adaptivní-interval)
- [Reálné provedení](#reálné-provedení)
  - [Hardware](#hardware)
  - [Struktura projektu](#struktura-projektu)
  - [Instalace a spuštění](#instalace-a-spuštění)
  - [MQTT topiky a formát zpráv](#mqtt-topiky-a-formát-zpráv)
  - [Funkce aplikace](#funkce-aplikace)
- [Známá omezení](#známá-omezení)
- [Odkazy](#odkazy)

---

## Popis projektu

Cílem projektu je realizace bezdrátového teploměru do grilu, který:

- měří teplotu **uvnitř potraviny** (sonda v mase) a teplotu **v prostoru grilu**,
- přenáší naměřená data v pravidelných intervalech přes Wi-Fi na server (MQTT broker),
- zobrazuje hodnoty v reálném čase v uživatelské aplikaci na notebooku,
- umožňuje uživateli **nastavit cílovou teplotu** masa a grilu,
- při dosažení cílové teploty spustí **zvukovou notifikaci**,
- je napájeno bateriově (v okolí grilu nejsou silové ani datové rozvody),
- využívá **adaptivní interval měření** pro úsporu energie.

## Architektura řešení

```
┌────────────────────────────┐                ┌────────────────────────────┐
│  Raspberry Pi Pico W       │                │  Notebook                  │
│  (umístění u grilu)        │                │                            │
│                            │                │  ┌──────────────────────┐  │
│  ┌──────────────────────┐  │                │  │  Mosquitto broker    │  │
│  │  AHT20 (maso)   I2C1 │──┤                │  │  (port 11883)        │  │
│  └──────────────────────┘  │   Wi-Fi        │  └──────────┬───────────┘  │
│  ┌──────────────────────┐  │   ──────►      │             │              │
│  │  AHT20 (gril)   I2C0 │──┤   MQTT         │  ┌──────────▼───────────┐  │
│  └──────────────────────┘  │   ◄──────      │  │  Tkinter dashboard   │  │
│                            │                │  │  (app.py)            │  │
│  Napájení: Li-Ion 18650    │                │  │  + zvuková notif.    │  │
│           + TP4056         │                │  │  + CSV export        │  │
└────────────────────────────┘                │  └──────────────────────┘  │
                                              └────────────────────────────┘

  publish: IoTProject/9/grill/teplota   ──►
  subscribe: IoTProject/9/grill/Tmaso   ◄── (cílová teplota masa)
             IoTProject/9/grill/Tgrill  ◄── (cílová teplota grilu)
```

---

## Teoretická část — zdůvodnění návrhu

> Detailní technický popis včetně tabulek porovnání, výpočtů spotřeby a alternativ je v samostatném dokumentu `docs/technicka_cast_hw_uspora_iotmasterchef.docx`. Následuje stručné shrnutí.

### Volba platformy: Raspberry Pi Pico W

Jako MCU bylo zvoleno **Raspberry Pi Pico W**. Důvody:

- dostupnost ve školním prostředí,
- dostatečný výkon pro měření, agregaci dat a Wi-Fi/MQTT komunikaci,
- podpora MicroPythonu (rychlý vývoj),
- I2C rozhraní pro připojení teplotních senzorů,
- vestavěná Wi-Fi konektivita.

> **Poznámka:** Wi-Fi nebyla zvolena proto, že ji Pico W nativně podporuje — Pico W je pouze platforma pro realizaci. Volba Wi-Fi je zdůvodněna níže nezávisle na použitém HW.

### Volba bezdrátové technologie: Wi-Fi

Zařízení je provozováno v blízkosti rodinného domu (např. pod pergolou), kde lze realisticky předpokládat dostupnost domácí Wi-Fi sítě. Wi-Fi umožňuje **přímé připojení na notebook/lokální server bez další gateway**.

| Technologie  | Hodnocení pro projekt                                                                |
|--------------|---------------------------------------------------------------------------------------|
| **Wi-Fi**    | **Zvolena** — přímé spojení s notebookem, dostupnost v domácnosti, bez gateway        |
| BLE          | Nízká spotřeba, ale menší dosah a horší integrace se serverem                         |
| Zigbee       | Nízká spotřeba, ale vyžaduje koordinátor/gateway — pro 1 zařízení zbytečně složité    |
| LoRa         | Velký dosah je pro domácí gril zbytečný; nutná gateway                                |
| NB-IoT       | Vyžaduje SIM, operátora a pokrytí — nepřiměřeně komplikované pro lokální použití      |

Hlavní nevýhodou Wi-Fi je vyšší spotřeba — řešena cyklickým provozním režimem (viz [Úspora energie](#úspora-energie-a-adaptivní-interval)).

### Volba aplikačního protokolu: MQTT

Protokolem aplikační vrstvy je **MQTT** (publish/subscribe model nad TCP). Vhodné pro telemetrická data odesílaná v pravidelných intervalech.

| Vlastnost                        | MQTT                              | CoAP                              |
|----------------------------------|-----------------------------------|-----------------------------------|
| Komunikační model                | Publish/subscribe                 | Request/response (REST nad UDP)   |
| Typické použití                  | Telemetrie, senzory, události     | Přístup ke zdrojům zařízení       |
| Provoz s úsporným režimem        | Snadné: zobudit → publish → sleep | Méně výhodné                      |
| **Vhodnost pro projekt**         | **Velmi vhodné**                  | Použitelné, ale méně praktické    |

MQTT umožňuje, aby zařízení **publikovalo data a šlo spát** — nemusí být trvale dostupné jako server (což by CoAP REST model vyžadoval). Pro broker se používá Mosquitto na notebooku.

### Senzory: prototyp vs. reálné nasazení

Ve školním prototypu jsou použity **dva senzory AHT20** (I2C, 3.3 V). AHT20 je dostupný školní senzor vhodný pro **ověření principu** — čtení dat z I2C, zpracování, odeslání přes MQTT.

> ⚠️ **AHT20 NENÍ vhodný pro reálné nasazení v grilu.** Je to senzor okolního prostředí (teplota + vlhkost), s rozsahem max. ~85 °C. Není určen k zapichování do potraviny ani k vystavení vysokým teplotám v grilu. V prototypu slouží pouze pro demonstraci datového toku.

Pro **reálné nasazení** je v technickém návrhu doporučena tato kombinace:

| Měřená veličina         | Doporučený senzor                                  | Důvod                                            |
|-------------------------|----------------------------------------------------|--------------------------------------------------|
| Teplota potraviny       | **DS18B20** v kovové sondě (1-Wire)                | Rozsah ~50–90 °C, jednoduché zapojení            |
| Teplota prostoru grilu  | **Termočlánek typu K + MAX6675 / MAX31855** (SPI)  | Rozsah ~150–300 °C, odolnost v prostředí grilu   |

### Napájení a výdrž baterie

Zařízení je napájeno **Li-Ion článkem 18650** (3.7 V, ~2600 mAh) doplněným o:

- nabíjecí modul **TP4056** s ochranou proti podvybití,
- mechanický vypínač (zařízení je aktivní pouze během grilování).

Důvody volby 18650 oproti alternativám: vysoká kapacita, schopnost dodat proudové špičky při Wi-Fi vysílání, opakovaná nabíjitelnost, běžná dostupnost.

### Úspora energie a adaptivní interval

Největším zdrojem spotřeby je Wi-Fi vysílání. Implementovaná opatření:

**1. Cyklický provozní režim** — zařízení se zobudí, změří, odešle, přijme cílovou teplotu, odpojí se a jde spát.

**2. Adaptivní interval** — frekvence měření závisí na vzdálenosti od cílové teploty:

| Rozdíl od cíle | Interval | Konstanta v kódu |
|----------------|----------|------------------|
| > 20 °C        | 30 s     | `INTERVAL_FAR`    |
| 5–20 °C        | 10 s     | `INTERVAL_MEDIUM` |
| < 5 °C         | 5 s      | `INTERVAL_CLOSE`  |
| dosaženo       | alarm    | —                |

Logika: na začátku grilování se teplota mění pomalu, časté odesílání není potřeba. Při blížení se k cíli interval klesá pro rychlou odezvu.

**Odhadovaná výdrž** (kapacita 2080 mAh využitelně, aktivní odběr 100 mA, sleep 2 mA, 4 s aktivní fáze):

| Konstantní interval 30 s | Konstantní interval 10 s | Konstantní interval 5 s | **Adaptivní režim**       |
|--------------------------|--------------------------|-------------------------|---------------------------|
| ~138 h                   | ~50 h                    | ~26 h                   | **~80–120 h**             |

V adaptivním režimu to odpovídá zhruba **10–20 grilovacím cyklům po 6 hodinách** mezi nabíjeními.

---

## Reálné provedení

### Hardware

| Komponenta                       | Popis                                                  |
|----------------------------------|--------------------------------------------------------|
| Raspberry Pi Pico W              | Hlavní MCU s vestavěnou Wi-Fi                          |
| AHT20 (×2)                       | Teplotní senzory na I2C0 a I2C1                        |
| Li-Ion 18650 + TP4056            | Napájení s nabíjecím modulem                           |
| Mechanický vypínač               | Hlavní vypínač zařízení                                |

**Zapojení I2C:**

| Senzor              | I2C kanál | SCL pin | SDA pin |
|---------------------|-----------|---------|---------|
| AHT20 (maso)        | I2C1      | GP3     | GP2     |
| AHT20 (gril)        | I2C0      | GP5     | GP4     |

### Struktura projektu

```
.
├── README.md                                  # tento soubor
├── thermometer.py                             # firmware pro Pico W (MicroPython)
├── app.py                                     # desktop dashboard (Python 3 + Tkinter)
└── docs/
    └── technicka_cast_hw_uspora_iotmasterchef.docx   # technická dokumentace
```

**Závislosti pro Pico W (MicroPython):**

- `umqtt.simple` (modul `simple.py` z umqtt) — MQTT klient
- `ahtx0.py` — driver pro AHT20

**Závislosti pro desktop aplikaci:**

```bash
pip install paho-mqtt
# tkinter je součástí standardní Python distribuce
# pro Linux zvuk: sudo apt install sox  (kvůli příkazu `play`)
```

### Instalace a spuštění

#### 1) MQTT broker

Na notebooku spusťte Mosquitto na portu **11883**:

```bash
# Linux (Arch/Debian/Ubuntu)
mosquitto -p 11883 -v
```

> Pro produkční nasazení nakonfigurujte `mosquitto.conf` s autentizací a TLS.

#### 2) Konfigurace firmwaru

V souboru `thermometer.py` upravte:

```python
WIFI_SSID = "..."          # název Wi-Fi sítě
WIFI_PWD  = "..."          # heslo Wi-Fi
BROKER_IP = "..."          # IP adresa notebooku s brokerem
BROKER_PORT = 11883
GROUP_NUM = "9"            # identifikátor skupiny v MQTT topiku
```

#### 3) Nahrání firmwaru na Pico W

1. Nainstalujte na Pico W MicroPython firmware (`.uf2` z [micropython.org](https://micropython.org/download/RPI_PICO_W/)).
2. Pomocí [Thonny](https://thonny.org) nebo `mpremote` nahrajte:
   - `thermometer.py` jako `main.py`
   - `simple.py` (umqtt klient)
   - `ahtx0.py` (driver senzoru)

```bash
mpremote cp thermometer.py :main.py
mpremote cp simple.py :
mpremote cp ahtx0.py :
mpremote reset
```

#### 4) Spuštění desktop aplikace

```bash
python app.py
```

V aplikaci nastavte slidery na požadovanou teplotu masa a grilu a klikněte na **ODESLAŤ NASTAVENIA**. Aplikace začne přijímat naměřená data a zobrazovat je v reálném čase.

### MQTT topiky a formát zpráv

| Topik                              | Směr            | Payload (JSON)                       |
|------------------------------------|-----------------|--------------------------------------|
| `IoTProject/9/grill/teplota`       | Pico → app      | `{"maso": 62.4, "gril": 187.3}`      |
| `IoTProject/9/grill/Tmaso`         | app → Pico      | `{"masoTarget": 75.0}`               |
| `IoTProject/9/grill/Tgrill`        | app → Pico      | `{"grillTarget": 200.0}`             |

Hodnoty teploty jsou ve °C, zaokrouhleny na jedno desetinné místo.

### Funkce aplikace

- **Dashboard** s aktuální teplotou masa a grilu (velký font, barevná indikace stavu).
- **Slidery** pro nastavení cílové teploty masa (0–100 °C) a grilu (0–200 °C).
- **Tlačítko ODESLAŤ NASTAVENIA** — atomicky odešle obě cílové teploty (zabrání odeslání nedokončeného nastavení během tažení slideru).
- **Zvuková notifikace** při dosažení / opuštění tolerančního pásma (±5 °C kolem cíle):
  - dosažení cíle → krátký vyšší tón,
  - opuštění (např. přetopení) → série pípnutí.
  - Cross-platform: `winsound` na Windows, `sox`/`play` na Linuxu.
- **CSV export** — všechny přijaté hodnoty se průběžně zapisují do `data_gril_export.csv` (`HH:MM:SS, maso, gril`).
- **Indikátor stavu** spojení s brokerem ve spodním řádku.

---

## Známá omezení

- **AHT20 jako teplotní senzor** — pouze pro prototypování. Nevhodný pro reálné měření teploty masa (kontaminace, nesprávný formát) ani teploty grilu (max. ~85 °C). Pro reálné nasazení viz [Senzory: prototyp vs. reálné nasazení](#senzory-prototyp-vs-reálné-nasazení).
- **Sleep režim** — v současné implementaci je použit `time.sleep()` v hlavní smyčce. Pro skutečné dosažení odhadované výdrže by bylo potřeba implementovat `machine.lightsleep()` mezi cykly měření a explicitně deaktivovat WLAN po publikaci. Aktuální kód funguje jako funkční prototyp; energetická optimalizace je rozpracována v technické dokumentaci.
- **MQTT bez autentizace** — broker je pro účely projektu spuštěn bez TLS a bez hesla. Pro reálné nasazení použijte `mosquitto.conf` s `password_file` a TLS certifikáty.
- **Adaptivní interval řízen pouze teplotou masa a grilu** — kód v `thermometer.py` bere `min()` z obou intervalů, takže rychlejší vzorkování jednoho senzoru ovlivňuje i druhý. To je záměrné (chceme rychlou odezvu při blížení k jakékoliv cílové teplotě).
- **Hardcoded GROUP_NUM** v `app.py` — topiky obsahují `9` natvrdo, na rozdíl od firmware, kde je to konstanta. Při změně skupiny upravte na obou místech.

---

## Odkazy

- Detailní technická dokumentace: `docs/technicka_cast_hw_uspora_iotmasterchef.docx`
- [MicroPython na Raspberry Pi Pico W](https://docs.micropython.org/en/latest/rp2/quickref.html)
- [Mosquitto MQTT broker](https://mosquitto.org/)
- [paho-mqtt (Python client)](https://www.eclipse.org/paho/index.php?page=clients/python/index.php)
- [umqtt.simple (MicroPython)](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple)
