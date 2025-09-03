# HPM - Home Power Monitor

16-channel current monitoring plugin for Domoticz using HDXXAXXA16GK-D Modbus device.

## Features

- **16-channel current monitoring** - Real-time current measurement (0.01A resolution)
- **Power calculation** - Estimates power consumption using voltage and power factor
- **Modbus TCP connectivity** - Requires TCP proxy/gateway (see below)
- **Dynamic or static configuration** - Use live voltage/PF from other devices or fixed values
- **Automatic phase summaries** - Built-in L1/L2/L3 phase totals

## Requirements

### Hardware
- **HDXXAXXA16GK-D** current measurement module
- **16x current transformers** compatible with the device
- **Modbus TCP proxy/gateway** - converts RS485 to TCP

### Modbus TCP Proxy Requirement

The HDXXAXXA16GK-D device uses **Modbus RTU over RS485 serial**. For network access, you need a **TCP proxy/gateway**:

**Hardware options:**
- Moxa NPort series (industrial grade)
- USR-TCP232 series (budget option)
- Any RS485-to-TCP converter

**Software options:**
- pyModbus proxy
- ModbusPal
- Custom Python script

```
Network: [HPM Plugin] ←TCP→ [Proxy] ←RS485→ [HDXXAXXA16GK-D]
```

### Software
- Domoticz with Python plugin support
- Python 3.6+
- `pip3 install pyModbusTCP`

## Installation

1. **Download plugin**
   ```bash
   cd /opt/domoticz/plugins/
   git clone [repository] HPM
   ```

2. **Install dependencies**
   ```bash
   pip3 install pyModbusTCP
   ```

3. **Add hardware**
   - Go to Setup → Hardware
   - Add Type: "HPM - Home Power Monitor"
   - Configure connection and JSON

## Configuration

HPM uses JSON configuration with two approaches:

### Static Values (Simple)
Fixed voltage and power factor for all calculations:
```json
[
  {"name": "Washing Machine", "voltage": 230, "pf": 0.75},
  {"name": "Kitchen Outlets", "voltage": 230, "pf": 0.80}
]
```

### Dynamic Values (Advanced)
Read live voltage/PF from other Domoticz devices (e.g., DDS238 meters):
```json
[
  {"name": "Washing Machine", "voltage_idx": 1317, "pf_idx": 1318},
  {"name": "Kitchen Outlets", "voltage_idx": 1299, "pf_idx": 1320}
]
```

**Benefits of dynamic approach:**
- Real-time voltage compensation
- Actual power factor from smart meters
- Higher accuracy than static values
- Automatic 3-phase detection and summaries

## Device Types Created

**Individual channels (32 devices):**
- Current sensors (ID 1-16): Custom sensor in Amperes
- Power sensors (ID 17-32): Electric usage in Watts

**Phase summaries (7 devices) - only with dynamic config:**
- Current L1/L2/L3 summaries (ID 100-102)
- Power L1/L2/L3 summaries (ID 110-112)  
- Total power summary (ID 120)

## Example Configurations

### Home Setup (Static)
```json
[
  {"name": "Washing Machine", "voltage": 230, "pf": 0.75},
  {"name": "Dryer", "voltage": 230, "pf": 0.80},
  {"name": "Dishwasher", "voltage": 230, "pf": 0.85},
  {"name": "Refrigerator", "voltage": 230, "pf": 0.80},
  {"name": "TV Electronics", "voltage": 230, "pf": 0.70},
  {"name": "LED Lighting", "voltage": 230, "pf": 0.90},
  {"name": "Kitchen Outlets", "voltage": 230, "pf": 0.75},
  {"name": "Living Room", "voltage": 230, "pf": 0.75},
  {"name": "Bedroom 1", "voltage": 230, "pf": 0.75},
  {"name": "Bedroom 2", "voltage": 230, "pf": 0.75},
  {"name": "Bathroom", "voltage": 230, "pf": 0.80},
  {"name": "Office", "voltage": 230, "pf": 0.70},
  {"name": "Basement", "voltage": 230, "pf": 0.75},
  {"name": "Garage", "voltage": 230, "pf": 0.80},
  {"name": "Spare 1", "voltage": 230, "pf": 0.75},
  {"name": "Spare 2", "voltage": 230, "pf": 0.75}
]
```

### Industrial Setup (Dynamic with DDS238 meters)
```json
[
  {"name": "Line 1 Motors", "voltage_idx": 1297, "pf_idx": 1315},
  {"name": "Line 2 Motors", "voltage_idx": 1298, "pf_idx": 1316},
  {"name": "Line 3 Motors", "voltage_idx": 1299, "pf_idx": 1317},
  {"name": "Lighting L1", "voltage_idx": 1297, "pf_idx": 1318},
  {"name": "Lighting L2", "voltage_idx": 1298, "pf_idx": 1318},
  {"name": "Lighting L3", "voltage_idx": 1299, "pf_idx": 1318},
  {"name": "HVAC L1", "voltage_idx": 1297, "pf_idx": 1319},
  {"name": "HVAC L2", "voltage_idx": 1298, "pf_idx": 1319},
  {"name": "HVAC L3", "voltage_idx": 1299, "pf_idx": 1319},
  {"name": "Production L1", "voltage_idx": 1297, "pf_idx": 1320},
  {"name": "Production L2", "voltage_idx": 1298, "pf_idx": 1320},
  {"name": "Production L3", "voltage_idx": 1299, "pf_idx": 1320},
  {"name": "Outlets L1", "voltage_idx": 1297, "pf_idx": 1321},
  {"name": "Outlets L2", "voltage_idx": 1298, "pf_idx": 1321},
  {"name": "Outlets L3", "voltage_idx": 1299, "pf_idx": 1321},
  {"name": "Emergency", "voltage_idx": 1297, "pf_idx": 1315}
]
```

## Power Factor Reference

| Device Type | Typical PF | Static Value |
|------------|-------------|-------------|
| Resistive loads (heaters) | 0.95-1.00 | `0.95` |
| LED lighting | 0.85-0.95 | `0.90` |
| Motors, refrigerators | 0.75-0.85 | `0.80` |
| Electronics, TVs | 0.60-0.90 | `0.75` |
| Mixed circuits | 0.70-0.80 | `0.75` |

## Connection Parameters

- **IP Address**: TCP proxy/gateway IP
- **Port**: Usually 502 (standard) or 8887
- **Modbus ID**: Device address on RS485 bus (default: 14)
- **Reading Interval**: Update frequency in 10-second units

## Troubleshooting

**No data from device:**
- Test TCP connection: `telnet [proxy-ip] [port]`
- Check proxy RS485 wiring and settings
- Verify Modbus ID matches device address

**Incorrect power values:**
- For static config: Check voltage/PF values
- For dynamic config: Verify voltage_idx/pf_idx devices exist and have valid data
- Monitor debug logs for calculation details

**Missing phase summaries:**
- Only available with dynamic configuration (voltage_idx/pf_idx)
- Check that multiple voltage_idx values exist for phase detection

## Device Specifications

**HDXXAXXA16GK-D:**
- 16 AC current inputs, 0.01A resolution
- Accuracy: ±1% @ 50Hz
- Communication: Modbus RTU, 9600 baud, N,8,1
- Power: DC 8-28V
- Registers: 0x0008-0x0017 (current values)

**Network Architecture:**
```
Domoticz HPM Plugin ←→ TCP Proxy ←→ RS485 Bus ←→ HDXXAXXA16GK-D + Other Devices
```

This setup allows multiple applications (Domoticz, Home Assistant, etc.) to access the same Modbus devices without conflicts.
