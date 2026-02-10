# GPS Simulator Module

## Overview
The `gps-sim` module is a Linux kernel module that simulates a GPS receiver by generating NMEA 0183 sentences over a virtual TTY device (`/dev/ttyGPS0`).

## usage
Loading the module:
```bash
insmod /lib/modules/$(uname -r)/extra/gps-sim.ko
```
Or if installed in the module path:
```bash
modprobe gps-sim
```

## Features
- **Virtual TTY**: Creates `/dev/ttyGPS0` which outputs NMEA data.
- **NMEA Sentences**: Generates `GNGGA`, `GNRMC`, `GNGSA`, `GNGSV`.
- **Simulation**:
    - Simulates satellite movement and signal quality.
    - Simulates location jitter.
    - Uses system time for timestamps (taking current UTC time).

## Module Parameters

The module accepts the following parameters at load time:

| Parameter | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `start_lat` | int | Starting Latitude in micro-degrees (e.g., -35315075 for -35.315075) | -35315075 |
| `start_lon` | int | Starting Longitude in micro-degrees (e.g., 149129404 for 149.129404) | 149129404 |
| `error_rate` | int | Error rate (0-100%) for checksum corruption | 0 |
| `signal_loss` | int | Simulate signal loss (0=Good, 1=Lost) | 0 |

### Example
Load the module starting at a specific location (NYC) with 10% error rate:
```bash
insmod gps-sim.ko start_lat=40712800 start_lon=-74006000 error_rate=10
```

## Runtime Configuration

Parameters can be modified at runtime via `sysfs`. This allows for dynamic control of the simulation without reloading the module.

**Change location to Sydney:**
```bash
echo -33868800 > /sys/module/gps_sim/parameters/start_lat
echo 151209300 > /sys/module/gps_sim/parameters/start_lon
```

**Induce signal loss:**
```bash
echo 1 > /sys/module/gps_sim/parameters/signal_loss
```

**Increase error rate:**
```bash
echo 50 > /sys/module/gps_sim/parameters/error_rate
```

## Time Handling
The simulator uses the kernel's real-time clock to generate accurate UTC timestamps in the NMEA sentences, reflecting the current system time.
