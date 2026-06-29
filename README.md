# Dynamic Ryzen Power

Dynamic control of AMD Ryzen CPU power limits based on real-time temperature monitoring. Automatically reduces power limits when CPU temperature exceeds thresholds and gradually restores them when cooling down.

This script uses `ryzenadj` to adjust power limits (STAPM, FAST, SLOW, APU_SLOW) on AMD Ryzen APUs (especially laptops) to prevent thermal throttling while maximizing performance.

## Requirements

- Linux system with AMD Ryzen CPU (APU or dGPU)
- `ryzenadj` tool installed (https://github.com/flygoat/ryzenadj)
- Python 3.8+
- Root privileges (required to modify power limits via `ryzenadj`)

### Installing `ryzenadj`

Follow the official installation guide:

```bash
# Clone repository
mkdir -p ~/src && cd ~/src
git clone https://github.com/flygoat/ryzenadj.git
cd ryzenadj

# Build and install
make
sudo make install

# Verify installation
ryzenadj --help
```

> Note: On some distributions (e.g., Arch Linux), `ryzenadj` is available via package manager:
> ```bash
> sudo pacman -S ryzenadj
> ```

## Project Structure

```
dynamic-ryzen-power/
├── dynamic_ryzen_power.py   # Main script
├── config.json              # Configuration file
└── README.md
```

## Configuration

Create `config.json` in the same directory as the script:

```json
{
  "ryzenadj_path": "/usr/local/bin/ryzenadj",
  "default_power_limits": {
    "stapm": 120000,
    "fast": 140000,
    "slow": 120000,
    "apu_slow": 120000
  },
  "temperature_thresholds": {
    "high": 84.0,
    "low": 74.0
  },
  "power_reduction_factor_high": 0.02,
  "power_reduction_factor_mid": 0.005,
  "power_reduction_factor_low": 0.01,
  "restore_step_percent": 0.05,
  "mid_threshold_percent": 0.85,
  "polling_interval": 5,
  "min_reduction": 0.3
}
```

### Configuration Parameters

| Parameter | Description | Default |
|----------|-------------|---------|
| `ryzenadj_path` | Path to `ryzenadj` binary | `/usr/local/bin/ryzenadj` |
| `stapm/fast/slow/apu_slow` | Default power limits in mW | 120000 / 140000 / 120000 / 120000 |
| `high` | Temperature threshold for aggressive power reduction | 84.0°C |
| `low` | Temperature threshold for restoration start | 74.0°C |
| `power_reduction_factor_high` | Reduction rate per °C above high threshold (2% per °C) | 0.02 |
| `power_reduction_factor_mid` | Mild reduction rate in mid-zone | 0.005 |
| `power_reduction_factor_low` | Restoration rate in low-zone | 0.01 |
| `restore_step_percent` | % of default limit restored per cycle | 0.05 (5%) |
| `mid_threshold_percent` | % of default limit where mid-zone ends | 0.85 (85%) |
| `polling_interval` | How often to check temperature (seconds) | 5 |
| `min_reduction` | Minimum power reduction allowed | 0.3 (30%) |

## Usage

### Start the service

```bash
cd /home/nestor/scripts/dynamic-ryzen-power
sudo python3 dynamic_ryzen_power.py
```

> Important: The script must be run as root to modify power limits.

### Run as systemd service (recommended)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/dynamic-ryzen-power.service
```

Paste the following:

```ini
[Unit]
Description=Dynamic Ryzen Power Limiter
After=multi-user.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/nestor/scripts/dynamic-ryzen-power
ExecStart=/usr/bin/python3 /home/nestor/scripts/dynamic-ryzen-power/dynamic_ryzen_power.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dynamic-ryzen-power
sudo systemctl start dynamic-ryzen-power
```

Check status:

```bash
sudo systemctl status dynamic-ryzen-power
journalctl -u dynamic-ryzen-power -f
```

## How It Works

The script monitors temperature from multiple sensors:

- `tctl`: CPU core temperature (`/sys/class/hwmon/hwmon3/temp1_input`)
- `apu_skin`: APU skin temperature (`/sys/class/hwmon/hwmon6/temp1_input`)
- `dgpu_skin`: dGPU skin temperature (`/sys/class/hwmon/hwmon0/temp1_input`)

It uses the **highest** of these readings to determine the current thermal state.

### Power Control Zones

| Zone | Temperature | Action |
|------|-------------|--------|
| **Zone 1 (Aggressive)** | > 84°C | Reduce power by 2% per °C over 84°C (min 30%) |
| **Zone 2 (Moderate)** | 74°C – 84°C | Mild reduction near top, gradual restoration near bottom |
| **Zone 3 (Restoration)** | ≤ 74°C | Restore power limits by 5% of default per cycle until full |

This prevents thermal throttling while maximizing sustained performance.

## Troubleshooting

### `ryzenadj` not found

Verify path in `config.json` and ensure `ryzenadj` is installed:

```bash
which ryzenadj
ls -l /usr/local/bin/ryzenadj
```

### No temperature readings

Check sensor paths:

```bash
ls /sys/class/hwmon/hwmon*/temp1_input
```

Update `SENSORS` dictionary in `dynamic_ryzen_power.py` if sensor paths differ on your system.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Credits

- [ryzenadj](https://github.com/flygoat/ryzenadj) — by flygoat
- Inspired by community power management scripts for Linux