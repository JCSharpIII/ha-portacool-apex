![PortaCool Apex](icon.png)

# Portacool APEX

A Home Assistant custom integration for controlling **Portacool APEX evaporative coolers** using the official Portacool cloud backend (Firebase / REST).

This integration is **UI-configured only** (no YAML) and exposes power, fan, pump, timer, temperature, water status, and device health in a clean, Home Assistant–native way.

> This is an **unofficial** integration and is not affiliated with or endorsed by Portacool.

---

## Features

- Cloud authentication using Portacool account credentials
- Automatic device discovery
- Real-time state updates via Firebase WebSockets
- Main power control
- Fan mode control (Off → 100%)
- Pump mode control (Off / Eco / Manual speeds / Max)
- Sleep timer with remaining time sensor
- Exit temperature sensor
- Ambient temperature sensor
- Water tank status monitoring
- Input voltage monitoring
- Clean entity model (no duplicate or conflicting controls)
- Fully UI-configured via Config Flow (no YAML)

---

## Entities Created

Each Portacool APEX device creates the following entities.

---

### Switch Entities

#### **Power**
- Turns the entire unit **On / Off**
- When powered off:
  - Fan and pump controls remain visible but do not send commands
  - Sensor updates continue (cloud-reported state)

---

### Select Entities

#### **Fan Mode**
Controls fan output as discrete, user-friendly steps:

- Off  
- 20%  
- 40%  
- 60%  
- 80%  
- 100%

Mapped internally to the device’s native fan control datapoints.

---

#### **Pump Mode**
Unified pump control combining **Off**, **presets**, and **manual speeds**:

- Off
- Eco
- 1
- 2
- 3
- 4
- 5
- Max

This avoids conflicting states between Eco / Max and manual pump speeds.

---

#### **Sleep Timer**
Sets the device sleep timer:

- Off
- 30 minutes
- 1 hour
- 2 hours
- 4 hours
- 8 hours

---

### Sensor Entities

#### **Timer Remaining**
- Remaining sleep-timer duration
- Updates periodically
- Clears automatically when the timer expires or is turned off
- Displayed in minutes for readability

---

#### **Exit Temperature**
- Temperature of air exiting the unit
- °F (reported directly from device)

---

#### **Ambient Temperature**
- Ambient intake temperature
- °F

---

#### **Water Status**
Summarized water tank state derived from device alerts:

- Normal
- Low
- Empty
- Overflow

Only the **highest-priority active condition** is shown.

---

#### **Input Voltage**
- Line input voltage reported by the unit
- Used by the device internally for load and fault detection

---

## Installation (HACS)

### Recommended (HACS)

1. Open **HACS**
2. Go to **Integrations**
3. Click **Custom repositories**
4. Add this repository:
      https://github.com/JCSharpIII/ha-portacool-apex
5. Category: **Integration**
6. Install **Portacool APEX**
7. Restart Home Assistant

---

## Setup

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **Portacool APEX**
4. Log in with your Portacool account credentials
5. Your device will be discovered automatically

The integration title and device name are pulled directly from the Portacool API (model and device name).

---

## How It Works

- Authentication uses Portacool’s official cloud endpoints
- State updates are received via **Firebase WebSockets**
- Commands are sent using Portacool’s device action API
- Polling fallback is used conservatively to avoid rate limits
- Sensor updates continue even when the unit is powered off

---

## Configuration Notes

- YAML configuration is **not supported**
- All entities are created automatically
- Polling interval defaults to **60 seconds**
- WebSocket updates are preferred whenever available

---

## Known Limitations

- Cloud-only (no local control)
- Fan RPM is not currently exposed by the API
- Some internal datapoints are undocumented and inferred
- Device availability depends on Portacool cloud uptime

---

## Debugging & Support

To enable debug logging:

```yaml
logger:
default: info
logs:
 custom_components.portacool_apex: debug

When opening a GitHub issue, include:
	•	Device model
	•	Relevant logs
	•	Description of the behavior

Roadmap / Ideas
	•	Climate entity abstraction
	•	Fan RPM detection (if exposed by API)
	•	Better water level percentage mapping
	•	Dashboard card templates
	•	Multi-device support improvements

License

MIT License