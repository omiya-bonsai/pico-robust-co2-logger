🌐 **Language**: [English](#) | [日本語](README-ja.md)

# Pico W CO2 Monitor for Long-Term Operation

![IMG_6133](https://github.com/user-attachments/assets/501ac347-8d22-4c50-b5d5-3e9043985742)
![IMG_6136](https://github.com/user-attachments/assets/66ac1ded-a521-45ee-99ad-bb02a97fbbde)

This MicroPython project turns a Raspberry Pi Pico W into a robust, long-term CO2, temperature, and humidity monitor. It is designed for stability over months or even years, incorporating features like watchdog timers, automated recovery mechanisms, and proactive daily reboots to prevent long-term issues.

Sensor data (CO2, Temperature, Humidity, THI) is displayed on a 4-digit 7-segment display and published to an MQTT broker for data logging and analysis.

## Features

- **Long-Term Stability**: Designed for "set it and forget it" operation.
- **Robust Error Handling**: Automatically recovers from Wi-Fi, MQTT, and sensor errors.
- **Watchdog Timer**: Resets the device if the main loop freezes.
- **Memory Management**: Aggressive garbage collection to prevent heap fragmentation.
- **Preventive Resets**: Daily reboots to ensure a fresh state.
- **Local Display**: Shows CO2 concentration and Temperature-Humidity Index (THI) on a TM1637 display.
- **MQTT Integration**: Publishes sensor data and system status to an MQTT broker.
- **File Logging**: Records important events and errors in a local `system.log` file, which is automatically rotated.
- **Configuration-Friendly**: Network and MQTT settings are stored in a separate `config.py` file.

## Required Hardware

- Raspberry Pi Pico W
- **SCD4x CO2 Sensor**: (e.g., Sensirion SCD40 or SCD41)
- **TM1637 4-Digit 7-Segment Display**
- Breadboard and jumper wires

### Wiring

| Pico W Pin | Component Pin | Description       |
| :--------- | :------------ | :---------------- |
| **3V3(OUT)** | SCD4x VDD, TM1637 VCC | Power             |
| **GND** | SCD4x GND, TM1637 GND | Ground            |
| **GP0 (I2C0 SDA)** | SCD4x SDA       | I2C Data          |
| **GP1 (I2C0 SCL)** | SCD4x SCL       | I2C Clock         |
| **GP2** | TM1637 CLK      | Display Clock     |
| **GP3** | TM1637 DIO      | Display Data I/O  |

## Required Software & Libraries

- [MicroPython for Raspberry Pi Pico W](https://micropython.org/download/RPI_PICO_W/)
- The following MicroPython libraries:
  - `scd4x.py`: Driver for the Sensirion SCD4x sensor. You can find a version here: [Github rst-sensors/scd4x](https://github.com/rst-sensors/scd4x/blob/main/scd4x.py)
  - `tm1637.py`: Driver for the TM1637 display. Available from [micropython-tm1637](https://github.com/mcauser/micropython-tm1637).
  - `umqtt.simple.py`: A simple MQTT client. Installable via `upip` or from [micropython-lib](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple).

## Setup Instructions

1.  **Flash MicroPython**: If you haven't already, flash the latest MicroPython firmware to your Raspberry Pi Pico W.

2.  **Upload Libraries**: Copy the required library files (`scd4x.py`, `tm1637.py`, `umqtt/simple.py`, `umqtt/robust.py`) to the `lib` directory on your Pico W.

3.  **Create Configuration File**: Create a file named `config.py` in the root directory of your Pico W. Add your network and MQTT broker details to this file:

    ```python
    # config.py
    
    WIFI_SSID = 'YOUR_WIFI_SSID'
    WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'
    
    MQTT_SERVER = '192.168.1.100' # IP address of your MQTT broker
    MQTT_PORT = 1883
    MQTT_CLIENT_ID = 'pico_w_co2_monitor_living_room' # A unique ID for this device
    ```

4.  **Upload Main Script**: Copy the `main.py` script from this repository to the root directory of your Pico W. The device will automatically run this script on boot.

5.  **Power On**: Connect the Pico W to a power source. It will automatically connect to Wi-Fi, initialize the sensors, and start monitoring.

## How It Works

### Display

The 4-digit display alternates between showing two values:
1.  **CO2 Concentration**: Displayed as a number (e.g., `850`).
2.  **Temperature-Humidity Index (THI)**: Displayed as `HiXX` (e.g., `Hi72`). THI is a measure of discomfort due to heat and humidity.

The display shows `init` on startup until the first sensor reading is available.

### MQTT Topics

The device publishes data to the following MQTT topics:

-   `co2_data`: A simple JSON payload with the latest CO2 reading.
    ```json
    {"co2": 850}
    ```
-   `sensor_data`: A JSON payload with all available sensor data.
    ```json
    {
      "timestamp": 1672531200,
      "device_id": "pico_w_co2_monitor_living_room",
      "co2": 850,
      "temperature": 24.5,
      "humidity": 55.2,
      "thi": 72.1
    }
    ```
-   `system_status`: A JSON payload published hourly with system health metrics.
    ```json
    {
      "uptime": 3600,
      "memory_free": 125400,
      "successful_readings": 120,
      "successful_transmissions": 120,
      "sensor_errors": 0,
      "mqtt_errors": 0,
      "wifi_errors": 0,
      "timestamp": 1672534800,
      "device_id": "pico_w_co2_monitor_living_room"
    }
    ```

### Logging

The device maintains a log file named `system.log` on its flash storage. This log is useful for debugging issues without needing a constant serial connection. The log file is automatically cleared when it grows too large to prevent storage issues.

## Customization

You can adjust the operational parameters at the top of the `main.py` script:
- `SENSOR_READ_INTERVAL`: How often to read from the sensor.
- `PUBLISH_INTERVAL`: How often to publish data to MQTT.
- `WATCHDOG_TIMEOUT`: The timeout for the system watchdog.
- `SYSTEM_RESET_INTERVAL`: The interval for preventive reboots.

## Acknowledgements
This script and its documentation were refined and structured with the assistance of Google's Gemini.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.