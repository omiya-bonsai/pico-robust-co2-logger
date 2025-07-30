#
# CO2 Monitoring System for Long-Term Operation on Raspberry Pi Pico W
#
# This script is designed for robustness and long-term stability,
# removing print statements and focusing on error handling and memory management.
# It reads sensor data, displays it, and sends it to an MQTT broker.
#

import time
import gc
import machine
from machine import Pin, I2C, WDT
import network
import ujson
import os

# ==============================================================================
# ===== User Configuration =====
# Please create a 'config.py' file with your network and MQTT settings.
#
# Example 'config.py':
#
# WIFI_SSID = 'YOUR_WIFI_SSID'
# WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'
# MQTT_SERVER = 'YOUR_MQTT_BROKER_IP'
# MQTT_PORT = 1883
# MQTT_CLIENT_ID = 'pico_w_co2_monitor'
#
# ==============================================================================

try:
    from config import WIFI_SSID, WIFI_PASSWORD, MQTT_SERVER, MQTT_PORT, MQTT_CLIENT_ID
except ImportError:
    # Fallback to default placeholder values if config.py is not found
    WIFI_SSID = 'YOUR_WIFI_SSID'
    WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'
    MQTT_SERVER = '192.168.1.100'
    MQTT_PORT = 1883
    MQTT_CLIENT_ID = 'pico_w_co2_monitor'


# ===== MQTT Topics =====
MQTT_TOPIC_CO2 = b'co2_data'
MQTT_TOPIC_SENSOR = b'sensor_data'
MQTT_TOPIC_STATUS = b'system_status'
MQTT_KEEPALIVE = 120  # Extended for long-term operation (2 minutes)

# ===== Hardware Configuration =====
I2C_SCL_PIN = 1
I2C_SDA_PIN = 0
DISPLAY_CLK_PIN = 2
DISPLAY_DIO_PIN = 3

# ===== Timing for Long-Term Operation =====
SENSOR_READ_INTERVAL = 30       # 30s interval to extend sensor life
PUBLISH_INTERVAL = 30         # 30s interval to reduce network load
DISPLAY_SWITCH_INTERVAL = 3   # 3s interval for display toggle
GC_INTERVAL = 60              # 60s interval for garbage collection
WATCHDOG_TIMEOUT = 30000      # 30s for stability
SYSTEM_RESET_INTERVAL = 86400 # Preventive reset every 24 hours
CONNECTION_RETRY_INTERVAL = 300 # 5-minute interval for connection retries

# ===== Memory Management Thresholds =====
MEMORY_WARNING_THRESHOLD = 20000
MEMORY_CRITICAL_THRESHOLD = 12000
MEMORY_EMERGENCY_THRESHOLD = 8000

# ===== Error Management =====
MAX_CONSECUTIVE_ERRORS = 20
MAX_MQTT_FAILURES = 10
MAX_SENSOR_FAILURES = 15

# ===== Library Availability Check =====
LIBRARIES_STATUS = {}

def check_library_availability():
    """Checks for required libraries at startup."""
    global LIBRARIES_STATUS
    libs = {
        'ntptime': 'ntptime',
        'scd4x': 'scd4x',
        'tm1637': 'tm1637',
        'umqtt': 'umqtt.simple'
    }
    for key, lib_name in libs.items():
        try:
            __import__(lib_name)
            LIBRARIES_STATUS[key] = True
        except ImportError:
            LIBRARIES_STATUS[key] = False

check_library_availability()


class ProductionCO2Monitor:
    """A robust CO2 monitoring system for long-term, multi-year operation."""

    def __init__(self):
        # Minimized instance variables for memory efficiency
        self.watchdog = None
        self.wlan = None
        self.mqtt_client = None
        self.scd40 = None
        self.display = None
        self.led = Pin("LED", Pin.OUT)

        # State management
        self.mqtt_connected = False
        self.system_running = True
        self.startup_time = time.time()

        # Timers
        self.last_sensor_read = 0
        self.last_publish = 0
        self.last_display_switch = 0
        self.last_gc = 0
        self.last_connection_check = 0
        self.last_status_report = 0
        self.last_preventive_reset = time.time()

        # Sensor data
        self.co2_ppm = None
        self.temperature_c = None
        self.humidity_percent = None
        self.thi_value = None

        # Display state
        self.show_co2_mode = True

        # Error counters
        self.sensor_error_count = 0
        self.mqtt_error_count = 0
        self.wifi_error_count = 0
        self.system_error_count = 0

        # Statistics
        self.successful_readings = 0
        self.successful_transmissions = 0

        # Logging
        self.log_file = "system.log"
        self.max_log_size = 50000  # 50KB limit

    def write_log(self, message, level="INFO"):
        """
        Writes a log entry to a file, replacing print().
        Rotates log file if it exceeds max size.
        """
        try:
            timestamp = time.time()
            log_entry = f"{timestamp}|{level}|{message}\n"

            # Check log file size
            try:
                if os.stat(self.log_file)[6] > self.max_log_size:
                    os.remove(self.log_file) # Rotate by deleting the old log
            except OSError:
                pass # File doesn't exist yet

            # Write to file
            with open(self.log_file, "a") as f:
                f.write(log_entry)
        except Exception:
            # Prevent logging errors from crashing the system
            pass

    def memory_management_aggressive(self):
        """Performs aggressive memory management to prevent heap fragmentation."""
        for _ in range(3):
            gc.collect()

        free_mem = gc.mem_free()

        if free_mem < MEMORY_EMERGENCY_THRESHOLD:
            # Emergency: Disable non-essential features and reset
            if self.display:
                try:
                    self.display.show("    ")
                except Exception:
                    pass
                self.display = None
            self.write_log(f"EMERGENCY_RESET: Memory={free_mem}", "CRITICAL")
            time.sleep(1)
            machine.reset()

        elif free_mem < MEMORY_CRITICAL_THRESHOLD:
            # Critical: Reset network connections
            if self.mqtt_client:
                try:
                    self.mqtt_client.disconnect()
                except Exception:
                    pass
                self.mqtt_client = None
                self.mqtt_connected = False
            self.write_log(f"MEMORY_CRITICAL: {free_mem}", "WARNING")

        elif free_mem < MEMORY_WARNING_THRESHOLD:
            self.write_log(f"MEMORY_WARNING: {free_mem}", "WARNING")

        return free_mem

    def feed_watchdog_safe(self):
        """Safely feeds the watchdog timer."""
        if self.watchdog:
            try:
                self.watchdog.feed()
            except Exception:
                pass

    def init_watchdog(self):
        """Initializes the Watchdog Timer."""
        try:
            self.watchdog = WDT(timeout=WATCHDOG_TIMEOUT)
            self.write_log("Watchdog initialized", "INFO")
            return True
        except Exception as e:
            self.write_log(f"Watchdog init failed: {e}", "ERROR")
            return False

    def calculate_thi_efficient(self, temp, humid):
        """Efficiently calculates the Temperature-Humidity Index (THI)."""
        if temp is None or humid is None:
            return None
        try:
            return round(0.81 * temp + 0.01 * humid * (0.99 * temp - 14.3) + 46.3, 1)
        except Exception:
            return None

    def connect_wifi_robust(self):
        """Robust Wi-Fi connection with retries and interface reset."""
        try:
            if not self.wlan:
                self.wlan = network.WLAN(network.STA_IF)
                self.wlan.active(True)

            if self.wlan.isconnected():
                return True

            # Reset interface before attempting to connect
            self.wlan.active(False)
            time.sleep(1)
            self.wlan.active(True)
            time.sleep(1)

            self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)

            # Wait for connection
            for _ in range(30):  # Max 30 seconds
                if self.wlan.isconnected():
                    self.write_log(f"WiFi connected: {self.wlan.ifconfig()[0]}", "INFO")
                    self.wifi_error_count = 0
                    return True
                time.sleep(1)
                self.feed_watchdog_safe()

            self.wifi_error_count += 1
            self.write_log(f"WiFi timeout (attempt {self.wifi_error_count})", "ERROR")
            return False

        except Exception as e:
            self.wifi_error_count += 1
            self.write_log(f"WiFi error: {e}", "ERROR")
            return False

    def sync_time_safe(self):
        """Safely syncs time using NTP."""
        if not LIBRARIES_STATUS.get('ntptime', False):
            return False
        try:
            import ntptime
            ntptime.settime()
            self.write_log("NTP synced", "INFO")
            return True
        except Exception as e:
            self.write_log(f"NTP failed: {e}", "WARNING")
            return False

    def connect_mqtt_robust(self):
        """Robust MQTT connection with cleanup."""
        if not LIBRARIES_STATUS.get('umqtt', False):
            return False
        try:
            # Clean up existing connection
            if self.mqtt_client:
                try:
                    self.mqtt_client.disconnect()
                except Exception:
                    pass
                self.mqtt_client = None

            # Create a new connection
            from umqtt.simple import MQTTClient
            self.mqtt_client = MQTTClient(
                MQTT_CLIENT_ID,
                MQTT_SERVER,
                port=MQTT_PORT,
                keepalive=MQTT_KEEPALIVE
            )
            self.mqtt_client.connect()
            self.mqtt_connected = True
            self.mqtt_error_count = 0
            self.write_log("MQTT connected", "INFO")
            return True

        except Exception as e:
            self.mqtt_error_count += 1
            self.mqtt_connected = False
            self.write_log(f"MQTT error (count {self.mqtt_error_count}): {e}", "ERROR")
            return False

    def init_sensor_robust(self):
        """Robust sensor initialization."""
        if not LIBRARIES_STATUS.get('scd4x', False):
            self.write_log("SCD4X library unavailable", "WARNING")
            return False
        try:
            from scd4x import SCD4X
            i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
            self.scd40 = SCD4X(i2c)

            # Sensor reset procedure
            self.scd40.stop_periodic_measurement()
            time.sleep(2)  # Allow ample time
            self.scd40.start_periodic_measurement()

            self.write_log("Sensor initialized", "INFO")
            return True
        except Exception as e:
            self.write_log(f"Sensor init error: {e}", "ERROR")
            return False

    def init_display_robust(self):
        """Robust display initialization."""
        if not LIBRARIES_STATUS.get('tm1637', False):
            self.write_log("TM1637 library unavailable", "WARNING")
            return False
        try:
            import tm1637
            clk = Pin(DISPLAY_CLK_PIN)
            dio = Pin(DISPLAY_DIO_PIN)
            self.display = tm1637.TM1637(clk, dio)
            self.display.brightness(7)
            self.write_log("Display initialized", "INFO")
            return True
        except Exception as e:
            self.write_log(f"Display init error: {e}", "ERROR")
            return False

    def read_sensor_robust(self):
        """Robust sensor reading with data validation."""
        if not self.scd40:
            return False
        try:
            if not self.scd40.data_ready:
                return False

            # Get data
            self.co2_ppm = self.scd40.CO2
            
            # Get temperature and humidity (handle different attribute names)
            try:
                self.temperature_c = getattr(self.scd40, 'temperature', None)
                self.humidity_percent = getattr(self.scd40, 'humidity', None) or \
                                        getattr(self.scd40, 'relative_humidity', None)
            except Exception:
                self.temperature_c = None
                self.humidity_percent = None
            
            # Calculate THI
            self.thi_value = self.calculate_thi_efficient(self.temperature_c, self.humidity_percent)

            # Validate data
            if self.co2_ppm is not None and (self.co2_ppm < 0 or self.co2_ppm > 50000):
                self.write_log(f"Invalid CO2: {self.co2_ppm}", "WARNING")
                return False

            self.successful_readings += 1
            self.sensor_error_count = 0
            return True

        except Exception as e:
            self.sensor_error_count += 1
            self.write_log(f"Sensor read error (count {self.sensor_error_count}): {e}", "ERROR")

            # Re-initialize sensor if errors persist
            if self.sensor_error_count >= MAX_SENSOR_FAILURES:
                self.write_log("Sensor failure limit reached, reinitializing", "WARNING")
                self.init_sensor_robust()
                self.sensor_error_count = 0
            return False

    def update_display_safe(self):
        """Safely updates the display, showing 'init' until first reading."""
        if not self.display:
            return

        if self.co2_ppm is None:
            try:
                self.display.show("init")
            except Exception:
                pass # Ignore display errors
            return

        current_time = time.time()

        # Toggle display mode
        if current_time - self.last_display_switch >= DISPLAY_SWITCH_INTERVAL:
            self.show_co2_mode = not self.show_co2_mode
            self.last_display_switch = current_time

        try:
            if self.show_co2_mode:
                self.display.number(int(self.co2_ppm))
            else:
                if self.thi_value is not None:
                    thi_display = f"Hi{int(self.thi_value):02d}"
                    self.display.show(thi_display)
                else:
                    self.display.show("Hi--")
        except Exception:
            # Ignore display errors
            pass

    def publish_data_robust(self):
        """Robustly publishes data, excluding None values from JSON."""
        if not self.mqtt_connected or not self.mqtt_client:
            return False
        try:
            timestamp = time.time()

            # Create integrated sensor payload, adding only non-None values
            sensor_payload = {
                "timestamp": timestamp,
                "device_id": MQTT_CLIENT_ID
            }
            if self.co2_ppm is not None:
                sensor_payload["co2"] = self.co2_ppm
            if self.temperature_c is not None:
                sensor_payload["temperature"] = round(self.temperature_c, 2)
            if self.humidity_percent is not None:
                sensor_payload["humidity"] = round(self.humidity_percent, 2)
            if self.thi_value is not None:
                sensor_payload["thi"] = round(self.thi_value, 2)
            
            # Publish dedicated CO2 topic if CO2 is available
            if "co2" in sensor_payload:
                 self.mqtt_client.publish(MQTT_TOPIC_CO2, ujson.dumps({"co2": sensor_payload["co2"]}))

            # Publish combined sensor data if there's more than just timestamp/id
            if len(sensor_payload) > 2:
                self.mqtt_client.publish(MQTT_TOPIC_SENSOR, ujson.dumps(sensor_payload))

            self.successful_transmissions += 1
            self.mqtt_error_count = 0
            return True

        except Exception as e:
            self.mqtt_error_count += 1
            self.mqtt_connected = False
            self.write_log(f"MQTT publish error (count {self.mqtt_error_count}): {e}", "ERROR")
            return False

    def send_system_status(self):
        """Sends a system status report via MQTT."""
        if not self.mqtt_connected:
            return
        try:
            uptime = time.time() - self.startup_time
            status_data = {
                "uptime": uptime,
                "memory_free": gc.mem_free(),
                "successful_readings": self.successful_readings,
                "successful_transmissions": self.successful_transmissions,
                "sensor_errors": self.sensor_error_count,
                "mqtt_errors": self.mqtt_error_count,
                "wifi_errors": self.wifi_error_count,
                "timestamp": time.time(),
                "device_id": MQTT_CLIENT_ID
            }
            self.mqtt_client.publish(MQTT_TOPIC_STATUS, ujson.dumps(status_data))
        except Exception as e:
            self.write_log(f"Status report error: {e}", "ERROR")

    def check_connections_robust(self):
        """Robustly checks and re-establishes connections."""
        if not self.wlan or not self.wlan.isconnected():
            self.connect_wifi_robust()
        
        if not self.mqtt_connected and LIBRARIES_STATUS.get('umqtt', False):
            self.connect_mqtt_robust()

    def preventive_system_reset(self):
        """Performs a preventive system reset to maintain long-term health."""
        current_time = time.time()
        if current_time - self.last_preventive_reset >= SYSTEM_RESET_INTERVAL:
            self.write_log("Preventive system reset", "INFO")
            uptime = current_time - self.startup_time
            self.write_log(f"Uptime: {uptime}s, Readings: {self.successful_readings}, Transmissions: {self.successful_transmissions}", "INFO")
            time.sleep(2)
            machine.reset()

    def run_system_maintenance(self):
        """Runs periodic system maintenance tasks."""
        current_time = time.time()

        if current_time - self.last_gc >= GC_INTERVAL:
            self.memory_management_aggressive()
            self.last_gc = current_time

        if current_time - self.last_connection_check >= CONNECTION_RETRY_INTERVAL:
            self.check_connections_robust()
            self.last_connection_check = current_time

        if current_time - self.last_status_report >= 3600: # Every hour
            self.send_system_status()
            self.last_status_report = current_time

        self.preventive_system_reset()

    def run_monitoring_cycle(self):
        """Runs the main monitoring cycle: read, publish."""
        current_time = time.time()

        if current_time - self.last_sensor_read >= SENSOR_READ_INTERVAL:
            self.read_sensor_robust()
            self.last_sensor_read = current_time

        if (current_time - self.last_publish >= PUBLISH_INTERVAL and self.co2_ppm is not None):
            if self.publish_data_robust():
                self.last_publish = current_time

    def production_main_loop(self):
        """The main loop for production deployment."""
        self.write_log("Production CO2 Monitor starting", "INFO")
        self.write_log(f"Libraries: {LIBRARIES_STATUS}", "INFO")

        # Initialization sequence
        self.memory_management_aggressive()
        self.init_watchdog()
        self.feed_watchdog_safe()

        if not self.connect_wifi_robust():
            self.write_log("WiFi init failed - proceeding in offline mode", "WARNING")
        
        self.feed_watchdog_safe()
        self.sync_time_safe()
        
        self.feed_watchdog_safe()
        self.connect_mqtt_robust()
        
        self.feed_watchdog_safe()
        if not self.init_sensor_robust():
            self.write_log("Sensor init failed - display/network only mode", "WARNING")
        
        self.feed_watchdog_safe()
        self.init_display_robust()

        # Initialize timers to trigger actions on the first loop
        current_time = time.time()
        self.last_sensor_read = current_time - SENSOR_READ_INTERVAL
        self.last_publish = current_time
        self.last_gc = current_time
        self.last_connection_check = current_time
        self.last_status_report = current_time

        self.write_log("Production monitoring started", "INFO")

        try:
            while self.system_running:
                self.feed_watchdog_safe()
                
                self.update_display_safe()
                self.run_monitoring_cycle()
                self.run_system_maintenance()

                # Blink LED for visual feedback that the loop is running
                self.led.on()
                time.sleep(0.05)
                self.led.off()
                time.sleep(0.95)

        except Exception as e:
            self.write_log(f"FATAL SYSTEM ERROR: {e}", "CRITICAL")
            time.sleep(5)
            machine.reset()
        finally:
            self.write_log("System shutdown", "INFO")
            self.led.off()
            if self.mqtt_client:
                try:
                    self.mqtt_client.disconnect()
                except Exception:
                    pass

# Start the monitoring system
if __name__ == "__main__":
    monitor = ProductionCO2Monitor()
    monitor.production_main_loop()
