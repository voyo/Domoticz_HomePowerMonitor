#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HomePowerMonitor Plugin for Domoticz
Author: voyo@no-ip.pl
Version: 0.0.3
Description: Monitors current (A) and calculates power (W) for 16 channels using Modbus TCP
Requirements: pyModbusTCP (pip3 install pyModbusTCP)
License: Apache License 2.0
"""
"""
<plugin key="HPM" name="HPM - Home Power Monitor" author="voyo@no-ip.pl" version="0.0.3">
    <description>
        <h3>HPM - Home Power Monitor</h3>
        Monitors current (A) and calculates power (W) for 16 channels using Modbus TCP
        with HDXXAXXA16GK-D device from Guangzhou Huidian.
        Creates additional summary devices for phase currents and powers based on voltage_idx groups.
        <br/><br/>
        <b>Requirements:</b> pip3 install pyModbusTCP
    </description>
    <params>
        <param field="Address" label="IP Address" width="150px" required="true" default="10.0.20.27"/>
        <param field="Port" label="Port" width="50px" required="true" default="8887"/>
        <param field="Mode2" label="Modbus ID" width="50px" required="true" default="14"/>
        <param field="Mode3" label="Reading Interval (x10s)" width="50px" required="true" default="1"/>

        <param field="Mode1" label="Channel Configuration (JSON)" width="600px" required="true" default='[
            {"name": "Pralka", "voltage_idx": 1317, "pf_idx": 1317},
            {"name": "Suszarka", "voltage_idx": 1299, "pf_idx": 1318},
            {"name": "Zmywarka", "voltage_idx": 1299, "pf_idx": 1318},
            {"name": "Rekuperacja", "voltage_idx": 1299, "pf_idx": 1318},
            {"name": "Lodówka", "voltage_idx": 1297, "pf_idx": 1316},
            {"name": "Salon TV", "voltage_idx": 1298, "pf_idx": 1317},
            {"name": "Kuchnia 1297", "voltage_idx": 1299, "pf_idx": 1318},
            {"name": "Kuchnia 1298", "voltage_idx": 1298, "pf_idx": 1317},
            {"name": "Kuchnia 1299", "voltage_idx": 1297, "pf_idx": 1316},
            {"name": "Kuchnia blat", "voltage_idx": 1299, "pf_idx": 1318},
            {"name": "Pokój 1", "voltage_idx": 1298, "pf_idx": 1317},
            {"name": "Pokój 2", "voltage_idx": 1297, "pf_idx": 1316},
            {"name": "Pokój 3", "voltage_idx": 1299, "pf_idx": 1318},
            {"name": "Pokój 4", "voltage_idx": 1298, "pf_idx": 1317},
            {"name": "Rezerwowe 1", "voltage_idx": 1297, "pf_idx": 1315},
            {"name": "Rezerwowe 2", "voltage_idx": 1297, "pf_idx": 1315}
        ]'/>

        <param field="Mode6" label="Debug Mode" width="75px">
            <options>
                <option label="Disabled" value="Normal" default="true"/>
                <option label="Enabled" value="Debug"/>
            </options>
        </param>
    </params>
</plugin>
"""

import time
import json
import urllib.request
import urllib.error

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz

try:
    from pyModbusTCP.client import ModbusClient
except ImportError:
    ModbusClient = None

# Constants
CHANNEL_COUNT = 16
CURRENT_REGISTER_START = 8
CURRENT_MULTIPLIER = 0.01
MAX_CURRENT = 40
MAX_POWER = 10000
MAX_CONSECUTIVE_FAILURES = 5
CONNECTION_RESET_COOLDOWN = 30

# Device type definitions
DEVICE_TYPES = {
    'current': {
        'type_name': 'Custom',
        'type_id': 0,
        'sub_type': 0,
        'options': {'Custom': '1;A'}
    },
    'power': {
        'type_name': 'Usage',
        'type_id': 248,
        'sub_type': 1,
        'options': {'EnergyMeterMode': '1'}
    }
}

class Logger:
    def __init__(self):
        self.debug_mode = False

    def set_debug_mode(self, enabled):
        self.debug_mode = enabled

    def info(self, message):
        Domoticz.Log(f"HPM: {message}")

    def error(self, message):
        Domoticz.Error(f"HPM: {message}")

    def debug(self, message):
        if self.debug_mode:
            Domoticz.Debug(f"HPM: {message}")

    def warning(self, message):
        Domoticz.Log(f"HPM: WARNING: {message}")

logger = Logger()

class ValidationError(Exception):
    pass

class ConfigValidator:
    @staticmethod
    def validate_config(params):
        connection_params = ConfigValidator._validate_connection_params(params)
        channels = ConfigValidator._parse_channel_config(params.get("Mode1", ""))
        return connection_params, channels

    @staticmethod
    def _validate_connection_params(params):
        try:
            validated = {
                'host': params['Address'].strip(),
                'port': int(params['Port']),
                'unit_id': int(params['Mode2']),
                'interval': max(1, int(params['Mode3']))
            }

            if not 1 <= validated['port'] <= 65535:
                raise ValidationError("Port must be between 1 and 65535")

            if not 1 <= validated['unit_id'] <= 247:
                raise ValidationError("Modbus ID must be between 1 and 247")

            return validated

        except ValueError as e:
            raise ValidationError(f"Invalid numeric parameter: {e}")

    @staticmethod
    def _parse_channel_config(config_json):
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {e}")

        if not isinstance(config, list):
            raise ValidationError("Configuration must be a list")

        if len(config) != CHANNEL_COUNT:
            raise ValidationError(f"Configuration must contain exactly {CHANNEL_COUNT} channels")

        channels = []
        for i, channel in enumerate(config):
            if not isinstance(channel, dict):
                raise ValidationError(f"Channel {i+1} must be a dictionary")

            name = channel.get('name', f"Channel {i+1}").strip()
            voltage = channel.get('voltage', 230)
            voltage_idx = channel.get('voltage_idx')
            pf = channel.get('pf', 0.75)
            pf_idx = channel.get('pf_idx')

            if voltage_idx is None and (not isinstance(voltage, (int, float)) or voltage <= 0):
                raise ValidationError(f"Channel {i+1} voltage must be positive")

            if pf_idx is None and (not isinstance(pf, (int, float)) or not (0 < pf <= 1)):
                raise ValidationError(f"Channel {i+1} power factor must be between 0 and 1")

            channels.append({
                'name': name,
                'voltage': voltage,
                'voltage_idx': voltage_idx,
                'pf': pf,
                'pf_idx': pf_idx
            })

        return channels

class ConnectionHealthMonitor:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_reset_time = 0

    def record_success(self):
        self.consecutive_failures = 0

    def record_failure(self):
        self.consecutive_failures += 1

    def should_reset_connection(self):
        return (self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES and
                time.time() - self.last_reset_time >= CONNECTION_RESET_COOLDOWN)

    def reset_connection_attempted(self):
        self.last_reset_time = time.time()
        self.consecutive_failures = 0

class ValueFetcher:
    @staticmethod
    def get_value_from_idx(idx, value_name="value"):
        if idx is None:
            return None

        try:
            target_idx = int(idx)
            url = f"http://127.0.0.1:8080/json.htm?type=command&param=getdevices&rid={target_idx}"
            logger.debug(f"Fetching from URL: {url}")

            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    if response.getcode() == 200:
                        data = json.loads(response.read().decode('utf-8'))

                        if data.get('status') == 'OK' and data.get('result') and len(data['result']) > 0:
                            device_data = data['result'][0]

                            if 'Voltage' in device_data:
                                try:
                                    value = float(device_data['Voltage'])
                                    logger.debug(f"Device IDX {idx}: {value_name} = {value} (Voltage)")
                                    return value
                                except ValueError:
                                    pass

                            if 'Data' in device_data:
                                try:
                                    value = float(device_data['Data'].split(' ')[0])
                                    logger.debug(f"Device IDX {idx}: {value_name} = {value} (Data)")
                                    return value
                                except ValueError:
                                    pass

                            logger.debug(f"Device IDX {idx}: No readable value found")

            except Exception as e:
                logger.debug(f"Device IDX {idx}: Error - {e}")

        except ValueError:
            logger.debug(f"Device IDX {idx}: Invalid IDX format")

        return None

    @staticmethod
    def get_phase_values(channels, phase_groups):
        phase_values = {}
        for vidx in phase_groups:
            # Find a representative channel for this phase to fetch voltage and PF
            for channel_idx in phase_groups[vidx]:
                channel = channels[channel_idx]
                voltage = channel['voltage']
                pf = channel['pf']

                if channel.get('voltage_idx'):
                    dynamic_voltage = ValueFetcher.get_value_from_idx(channel['voltage_idx'], "voltage")
                    if dynamic_voltage is not None and dynamic_voltage > 0:
                        voltage = dynamic_voltage
                        logger.debug(f"Phase IDX {vidx}: Using dynamic voltage {voltage}V")

                if channel.get('pf_idx'):
                    dynamic_pf = ValueFetcher.get_value_from_idx(channel['pf_idx'], "power factor")
                    if dynamic_pf is not None and 0 < dynamic_pf <= 1:
                        pf = dynamic_pf
                        logger.debug(f"Phase IDX {vidx}: Using dynamic PF {pf}")

                phase_values[vidx] = {'voltage': voltage, 'pf': pf}
                break  # Use the first valid channel for this phase
        return phase_values

class DeviceManager:
    def __init__(self, channels):
        self.channels = channels
        self.devices = {}
        self.summary_devices = {}
        self.phase_groups = {}
        self.phase_labels = {}
        self.sorted_phases = []
        self._group_phases()
        self._create_devices()

    def _group_phases(self):
        for i, channel in enumerate(self.channels):
            vidx = channel.get('voltage_idx')
            if vidx is not None:
                if vidx not in self.phase_groups:
                    self.phase_groups[vidx] = []
                self.phase_groups[vidx].append(i)
        self.sorted_phases = sorted(self.phase_groups.keys())
        self.phase_labels = {idx: f"L{i+1}" for i, idx in enumerate(self.sorted_phases)}

    def _create_devices(self):
        # Individual devices
        for i, channel in enumerate(self.channels):
            current_unit = i + 1
            current_name = f"{channel['name']} Current"
            self._create_device(current_unit, current_name, 'current')
            self.devices[current_unit] = {'name': current_name, 'type': 'current', 'channel_idx': i}

            power_unit = i + 17
            power_name = f"{channel['name']} Power"
            self._create_device(power_unit, power_name, 'power')
            self.devices[power_unit] = {'name': power_name, 'type': 'power', 'channel_idx': i}

        # Summary devices
        next_unit = CHANNEL_COUNT * 2 + 1
        for phase_idx in self.sorted_phases:
            label = self.phase_labels[phase_idx]
            current_sum_unit = next_unit
            current_sum_name = f"Current Sum {label}"
            self._create_device(current_sum_unit, current_sum_name, 'current')
            self.summary_devices[current_sum_unit] = {'type': 'current_sum', 'phase': phase_idx}
            next_unit += 1

            power_sum_unit = next_unit
            power_sum_name = f"Power Sum {label}"
            self._create_device(power_sum_unit, power_sum_name, 'power')
            self.summary_devices[power_sum_unit] = {'type': 'power_sum', 'phase': phase_idx}
            next_unit += 1

        total_power_unit = next_unit
        total_power_name = "Total Power Sum"
        self._create_device(total_power_unit, total_power_name, 'power')
        self.summary_devices[total_power_unit] = {'type': 'power_total'}

    def _create_device(self, unit_id, name, device_type):
        if unit_id not in Devices:
            config = DEVICE_TYPES[device_type]
            Domoticz.Device(
                Name=name,
                Unit=unit_id,
                TypeName=config['type_name'],
                Type=config['type_id'],
                Subtype=config['sub_type'],
                Options=config['options'],
                Used=1
            ).Create()

    def update_devices(self, current_values):
        phase_values = ValueFetcher.get_phase_values(self.channels, self.phase_groups)
        phase_current_sums = {vidx: 0.0 for vidx in self.phase_groups}
        phase_power_sums = {vidx: 0.0 for vidx in self.phase_groups}
        total_power = 0.0
        updated_count = 0

        # Calculate and update individual devices
        for channel_idx in range(CHANNEL_COUNT):
            if channel_idx >= len(current_values):
                continue

            raw_current = current_values[channel_idx]
            current_amperes = raw_current * CURRENT_MULTIPLIER
            current_valid = 0 <= current_amperes <= MAX_CURRENT

            current_unit = channel_idx + 1
            if current_valid and current_unit in Devices:
                Devices[current_unit].Update(nValue=0, sValue=f"{current_amperes:.2f}")
                updated_count += 1
                if logger.debug_mode:
                    logger.debug(f"Device '{self.channels[channel_idx]['name']} Current': Updated to {current_amperes:.2f}A")

            channel_config = self.channels[channel_idx]
            vidx = channel_config.get('voltage_idx')
            power_watts = 0.0
            power_valid = False

            if vidx in phase_values:
                voltage = phase_values[vidx]['voltage']
                pf = phase_values[vidx]['pf']
                power_watts = voltage * current_amperes * pf
                power_valid = 0 <= power_watts <= MAX_POWER

                if logger.debug_mode:
                    logger.debug(f"Channel '{channel_config['name']}': {voltage}V × {current_amperes:.3f}A × {pf} = {power_watts:.1f}W")

                power_unit = channel_idx + 17
                if power_valid and power_unit in Devices:
                    Devices[power_unit].Update(nValue=0, sValue=f"{power_watts:.2f}")
                    updated_count += 1
                    if logger.debug_mode:
                        logger.debug(f"Device '{self.channels[channel_idx]['name']} Power': Updated to {power_watts:.1f}W")

                if current_valid:
                    phase_current_sums[vidx] += current_amperes
                if power_valid:
                    phase_power_sums[vidx] += power_watts
                    total_power += power_watts
            else:
                logger.warning(f"Channel '{channel_config['name']}' has no valid phase (voltage_idx: {vidx})")

        # Update summary devices
        for unit, info in self.summary_devices.items():
            if info['type'] == 'current_sum':
                val = phase_current_sums.get(info['phase'], 0.0)
                svalue = f"{val:.2f}"
                log_msg = f"Current Sum {self.phase_labels[info['phase']]} to {val:.2f}A"
            elif info['type'] == 'power_sum':
                val = phase_power_sums.get(info['phase'], 0.0)
                svalue = f"{val:.2f}"
                log_msg = f"Power Sum {self.phase_labels[info['phase']]} to {val:.2f}W"
            elif info['type'] == 'power_total':
                val = total_power
                svalue = f"{val:.2f}"
                log_msg = f"Total Power Sum to {val:.2f}W"
            else:
                continue

            if unit in Devices:
                Devices[unit].Update(nValue=0, sValue=svalue)
                if logger.debug_mode:
                    logger.debug(f"Updated {log_msg}")

        # Verify consistency
        sum_phases = sum(phase_power_sums.values())
        if abs(sum_phases - total_power) > 0.01:
            logger.warning(f"Power sum mismatch: L1+L2+L3={sum_phases:.2f}W, Total={total_power:.2f}W")
            for vidx in phase_power_sums:
                logger.debug(f"Phase {self.phase_labels[vidx]} power: {phase_power_sums[vidx]:.2f}W")

        logger.debug(f"Updated {updated_count}/{len(self.devices)} individual devices")

class ModbusManager:
    def __init__(self, connection_params):
        self.connection_params = connection_params
        self.client = None
        self.health = ConnectionHealthMonitor()

    def connect(self):
        if ModbusClient is None:
            logger.error("pyModbusTCP library not available")
            return False

        try:
            self.client = ModbusClient(
                host=self.connection_params['host'],
                port=self.connection_params['port'],
                unit_id=self.connection_params['unit_id'],
                auto_open=True,
                auto_close=True,
                timeout=2
            )
            logger.info(f"Connected to {self.connection_params['host']}:{self.connection_params['port']}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def read_channels(self):
        if not self.client:
            return None

        try:
            registers = self.client.read_holding_registers(CURRENT_REGISTER_START, CHANNEL_COUNT)

            if registers and len(registers) == CHANNEL_COUNT:
                self.health.record_success()
                logger.debug(f"Read {len(registers)} registers: {registers}")
                return registers
            else:
                self.health.record_failure()
                logger.error("Failed to read registers")
                return None

        except Exception as e:
            self.health.record_failure()
            logger.error(f"Read error: {e}")
            return None

    def check_connection(self):
        if self.health.should_reset_connection():
            logger.warning("Resetting connection due to failures")
            self.disconnect()
            self.health.reset_connection_attempted()
            return self.connect()
        return True

    def disconnect(self):
        if self.client:
            try:
                self.client.close()
            except:
                pass

class HPMPlugin:
    def __init__(self):
        self.connection_params = {}
        self.channels = []
        self.device_manager = None
        self.modbus_manager = None
        self.run_interval = 1

    def on_start(self):
        try:
            debug_enabled = Parameters["Mode6"] == "Debug"
            logger.set_debug_mode(debug_enabled)
            Domoticz.Debugging(1 if debug_enabled else 0)

            self.connection_params, self.channels = ConfigValidator.validate_config(Parameters)
            logger.info(f"Loaded configuration for {len(self.channels)} channels")

            if logger.debug_mode:
                for i, channel in enumerate(self.channels):
                    config_info = f"Channel {i+1}: '{channel['name']}'"
                    if channel.get('voltage_idx'):
                        config_info += f", Voltage from IDX {channel['voltage_idx']}"
                    else:
                        config_info += f", Voltage {channel['voltage']}V"
                    if channel.get('pf_idx'):
                        config_info += f", PF from IDX {channel['pf_idx']}"
                    else:
                        config_info += f", PF {channel['pf']}"
                    logger.debug(config_info)

            self.device_manager = DeviceManager(self.channels)
            if self.device_manager.sorted_phases:
                phase_info = ', '.join([f"{self.device_manager.phase_labels[idx]} (IDX {idx})" for idx in self.device_manager.sorted_phases])
                logger.info(f"Detected {len(self.device_manager.sorted_phases)} phases: {phase_info}")

            self.modbus_manager = ModbusManager(self.connection_params)

            if not self.modbus_manager.connect():
                raise Exception("Modbus connection failed")

            logger.info("HPM plugin started successfully")

        except ValidationError as e:
            logger.error(f"Configuration error: {e}")
        except Exception as e:
            logger.error(f"Startup failed: {e}")

    def on_heartbeat(self):
        self.run_interval -= 1
        if self.run_interval > 0:
            return

        self.run_interval = self.connection_params['interval']

        try:
            if not self.modbus_manager.check_connection():
                return

            current_values = self.modbus_manager.read_channels()
            if current_values is None:
                return

            self.device_manager.update_devices(current_values)

        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

    def on_stop(self):
        logger.info("Stopping HPM plugin")
        if self.modbus_manager:
            self.modbus_manager.disconnect()
        logger.info("HPM plugin stopped")

# Global plugin instance
_plugin = HPMPlugin()

def onStart():
    _plugin.on_start()

def onStop():
    _plugin.on_stop()

def onHeartbeat():
    _plugin.on_heartbeat()

# Required unused callbacks
def onConnect(Connection, Status, Description): pass
def onMessage(Connection, Data): pass
def onCommand(Unit, Command, Level, Hue): pass
def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile): pass
def onDisconnect(Connection): pass
def onDeviceAdded(Unit): pass
def onDeviceModified(Unit): pass
def onDeviceRemoved(Unit): pass
def onSecurityEvent(Unit, Level, Description): pass
