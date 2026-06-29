#!/usr/bin/env python3

import os
import time
import subprocess
import logging
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load configuration
script_path = Path(__file__)
resolved_dir = script_path.resolve().parent
default_dir = script_path.parent
config_path = resolved_dir / "config.json"
if not config_path.exists() and default_dir != resolved_dir:
    fallback_config = default_dir / "config.json"
    if fallback_config.exists():
        config_path = fallback_config

logging.info(f"Using configuration file: {config_path}")

try:
    with open(config_path, "r") as f:
        config = json.load(f)

    RYZENADJ = config.get("ryzenadj_path", "/usr/local/bin/ryzenadj")

    # Power limits in mW (default values)
    DEFAULT_STAPM = config.get("default_power_limits", {}).get("stapm", 120000)
    DEFAULT_FAST = config.get("default_power_limits", {}).get("fast", 140000)
    DEFAULT_SLOW = config.get("default_power_limits", {}).get("slow", 120000)
    DEFAULT_APU_SLOW = config.get("default_power_limits", {}).get("apu_slow", 120000)

    # Temperature thresholds in °C
    THRESHOLD_HIGH = config.get("temperature_thresholds", {}).get("high", 84.0)
    THRESHOLD_LOW = config.get("temperature_thresholds", {}).get("low", 74.0)

    # Power reduction factor: reduce by 2% per 1°C over 84°C
    POWER_REDUCTION_FACTOR = config.get("power_reduction_factor", 0.02)

    # Polling interval (seconds)
    INTERVAL = config.get("polling_interval", 5)

    # Minimum reduction percentage
    MIN_REDUCTION = config.get("min_reduction", 0.3)

except Exception as e:
    logging.error(f"Failed to load configuration: {e}")
    # Fallback to hardcoded values
    RYZENADJ = "/usr/local/bin/ryzenadj"
    DEFAULT_STAPM = 120000
    DEFAULT_FAST = 140000
    DEFAULT_SLOW = 120000
    DEFAULT_APU_SLOW = 120000
    THRESHOLD_HIGH = 84.0
    THRESHOLD_LOW = 74.0
    POWER_REDUCTION_FACTOR = 0.02
    INTERVAL = 5
    MIN_REDUCTION = 0.3

# Sensor paths (confirmed via sysfs)
SENSORS = {
    "tctl": "/sys/class/hwmon/hwmon3/temp1_input",   # CPU Core
    "apu_skin": "/sys/class/hwmon/hwmon6/temp1_input", # APU Skin
    "dgpu_skin": "/sys/class/hwmon/hwmon0/temp1_input" # dGPU Skin
}

def read_sensor(path):
    try:
        with open(path, "r") as f:
            val = int(f.readline().strip())
            return val / 1000.0  # Convert millidegrees to degrees
    except Exception as e:
        logging.error(f"Failed to read {path}: {e}")
        return None

def get_max_temp():
    temps = {name: read_sensor(path) for name, path in SENSORS.items()}
    valid_temps = [t for t in temps.values() if t is not None]
    return max(valid_temps) if valid_temps else None

def set_power_limits(stapm, fast, slow, apu_slow):
    cmd = [
        RYZENADJ,
        f"--stapm-limit={int(stapm)}",
        f"--fast-limit={int(fast)}",
        f"--slow-limit={int(slow)}",
        f"--apu-slow-limit={int(apu_slow)}"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info(f"Set limits: STAPM={stapm}, FAST={fast}, SLOW={slow}, APU_SLOW={apu_slow}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"ryzenadj failed: {e.stderr}")
        return False

def restore_defaults():
    logging.info("Restoring default power limits...")
    set_power_limits(DEFAULT_STAPM, DEFAULT_FAST, DEFAULT_SLOW, DEFAULT_APU_SLOW)

def main():
    # Restore defaults on startup
    logging.info("Dynamic Ryzen Power service started.")
    restore_defaults()
    at_default_limits = True

    try:
        while True:
            max_temp = get_max_temp()

            if max_temp is None:
                logging.warning(f"No valid temperature readings. Skipping cycle.")
                time.sleep(INTERVAL)
                continue

            if max_temp >= THRESHOLD_HIGH:
                # Calculate reduction: 2% per °C over 84°C
                overage = max_temp - THRESHOLD_HIGH
                reduction = 1.0 - (overage * POWER_REDUCTION_FACTOR)
                reduction = max(MIN_REDUCTION, reduction)  # Never reduce below MIN_REDUCTION of default

                new_stapm = int(DEFAULT_STAPM * reduction)
                new_fast = int(DEFAULT_FAST * reduction)
                new_slow = int(DEFAULT_SLOW * reduction)
                new_apu_slow = int(DEFAULT_APU_SLOW * reduction)

                logging.info(f"Temp {max_temp:.2f}°C > {THRESHOLD_HIGH}°C. Reducing power limits to {reduction:.1%}.")
                set_power_limits(new_stapm, new_fast, new_slow, new_apu_slow)
                at_default_limits = False

            elif max_temp <= THRESHOLD_LOW:
                # Restore to 100% if all temps below 74°C
                if not at_default_limits:
                    logging.info(f"Temp {max_temp:.2f}°C <= {THRESHOLD_LOW}°C. Restoring 100% limits.")
                    set_power_limits(DEFAULT_STAPM, DEFAULT_FAST, DEFAULT_SLOW, DEFAULT_APU_SLOW)
                    at_default_limits = True

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logging.info("Shutting down...")
        restore_defaults()
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        restore_defaults()

if __name__ == "__main__":
    main()