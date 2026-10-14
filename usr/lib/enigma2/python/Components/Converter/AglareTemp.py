# -*- coding: utf-8 -*-

from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.Converter.Poll import Poll
from enigma import eConsoleAppContainer
import os
import socket
import subprocess
import re
import logging
# 01.04.2025 @ lululla


class AglareTemp(Poll, Converter):
    TEMPERATURE = 0
    HDDTEMP = 1
    CPULOAD = 2
    CPUSPEED = 3
    FANINFO = 4
    UPTIME = 5
    IPLOCAL = 6

    def __init__(self, type):
        Converter.__init__(self, type)
        Poll.__init__(self)
        self.logger = logging.getLogger("AglareTemp")
        self.container = eConsoleAppContainer()

        # Parse type parameters
        type = type.split(',')
        self.short_format = 'Short' in type
        self.type = self._determine_type(type)

        # Initialize HDD temp monitoring if needed
        if self.type == self.HDDTEMP:
            self._init_hddtemp_monitoring()

        # Set appropriate polling interval
        self.poll_interval = 500 if self.type == self.HDDTEMP else 7000
        self.poll_enabled = True

    def _determine_type(self, type_params):
        """Determine the converter type based on input parameters"""
        type_mapping = {
            'CPULoad': self.CPULOAD,
            'CPUSpeed': self.CPUSPEED,
            'Temperature': self.TEMPERATURE,
            'Uptime': self.UPTIME,
            'Iplocal': self.IPLOCAL,
            'HDDTemp': self.HDDTEMP,
            'FanInfo': self.FANINFO
        }

        for param, type_val in type_mapping.items():
            if param in type_params:
                return type_val
        return self.TEMPERATURE  # Default type

    def _init_hddtemp_monitoring(self):
        """Initialize HDD temperature monitoring"""
        self.hddtemp_output = ''
        self.hddtemp = 'Waiting for HDD Temp Data...'
        self.container.appClosed.append(self._hddtemp_finished)
        self.container.dataAvail.append(self._hddtemp_data_available)

        # Check for HDD device
        hdd_device = '/dev/sda'
        if not os.path.exists(hdd_device):
            hdd_device = '/dev/sdb'  # Fallback device

        if os.path.exists(hdd_device):
            self.container.execute('hddtemp -n -q {}'.format(hdd_device))
        else:
            self.hddtemp = 'HDD not detected'

    def _hddtemp_data_available(self, strData):
        """Collect HDD temperature data"""
        try:
            self.hddtemp_output += strData.decode('utf-8', 'ignore')
        except Exception as e:
            self.logger.warning("Error processing HDD temp data: {}".format(str(e)))

    def _hddtemp_finished(self, retval):
        """Process completed HDD temperature check"""
        try:
            if 'No such file or directory' in self.hddtemp_output or 'not found' in self.hddtemp_output:
                self.hddtemp = 'HDD Temp: N/A'
            else:
                temp = int(self.hddtemp_output.strip())
                self.hddtemp = 'HDD Temp: {}°C'.format(temp) if temp > 0 else 'HDD idle or N/A'
        except ValueError:
            self.hddtemp = 'HDD Temp: Invalid data'
        except Exception as e:
            self.logger.warning("Error processing HDD temp: {}".format(str(e)))
            self.hddtemp = 'HDD Temp: Error'

    @cached
    def getText(self):
        """Main method to get requested information"""
        try:
            if self.type == self.CPULOAD:
                return self._get_cpu_load()
            elif self.type == self.TEMPERATURE:
                return self._get_temperature()
            elif self.type == self.HDDTEMP:
                return self.hddtemp
            elif self.type == self.IPLOCAL:
                return self._get_local_ip()
            elif self.type == self.CPUSPEED:
                return self._get_cpu_speed()
            elif self.type == self.FANINFO:
                return self._get_fan_info()
            elif self.type == self.UPTIME:
                return self._get_uptime()
        except Exception as e:
            self.logger.error("Error in getText: {}".format(str(e)))
            return "N/A"

    def _get_cpu_load(self):
        """Get current CPU load average"""
        try:
            if os.path.exists('/proc/loadavg'):
                with open('/proc/loadavg', 'r') as f:
                    load = f.readline(4).strip()
                return 'CPU Load: {}'.format(load)
            return 'CPU Load: N/A'
        except Exception as e:
            self.logger.warning("Error getting CPU load: {}".format(str(e)))
            return 'CPU Load: Error'

    def _get_temperature(self):
        """Get system temperature from various sources"""
        temp_sources = [
            ('/proc/stb/sensors/temp0/value', None),
            ('/proc/stb/fp/temp_sensor', None),
            ('/proc/stb/fp/temp_sensor_avs', None),
            ('/sys/devices/virtual/thermal/thermal_zone0/temp', lambda x: x[:2]),
            ('/proc/hisi/msp/pm_cpu', self._parse_hisi_temp)
        ]

        for source, processor in temp_sources:
            if os.path.exists(source):
                try:
                    with open(source, 'r') as f:
                        temp = f.read().strip()
                        if processor:
                            temp = processor(temp)
                        return '{}°C'.format(temp)
                except Exception as e:
                    self.logger.debug("Error reading {}: {}".format(source, str(e)))
                    continue
        return 'N/A'

    def _parse_hisi_temp(self, content):
        """Parse temperature from hisi format"""
        match = re.search(r'temperature\s*=\s*(\d+)\s*degree', content)
        return match.group(1) if match else 'N/A'

    def _get_local_ip(self):
        """Get local IP address"""
        try:
            # Try multiple methods to get IP
            methods = [
                self._get_ip_from_socket,
                self._get_ip_from_ip_command,
                self._get_ip_from_hostname
            ]

            for method in methods:
                ip = method()
                if ip:
                    return ip

            return 'IP: Not available'
        except Exception as e:
            self.logger.warning("Error getting local IP: {}".format(str(e)))
            return 'IP: Error'

    def _get_ip_from_socket(self):
        """Get IP using socket connection"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))  # Google DNS
                return s.getsockname()[0]
        except BaseException:
            return None

    def _get_ip_from_ip_command(self):
        """Get IP using ip command"""
        try:
            result = subprocess.run(
                ["ip", "-4", "route", "get", "8.8.8.8"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                match = re.search(r'src (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
        except BaseException:
            return None

    def _get_ip_from_hostname(self):
        """Get IP using hostname"""
        try:
            return socket.gethostbyname(socket.gethostname())
        except BaseException:
            return None

    def _get_cpu_speed(self):
        """Get current CPU speed in MHz"""
        speed_sources = [
            ('/proc/cpuinfo',
             self._parse_cpuinfo_speed),
            ('/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq',
             lambda x: str(
                 int(x) / 1000)),
            ('/sys/firmware/devicetree/base/cpus/cpu@0/clock-frequency',
             self._parse_dt_clock)]

        for source, processor in speed_sources:
            if os.path.exists(source):
                try:
                    with open(source, 'r') as f:
                        speed = processor(f.read())
                        if speed:
                            return 'CPU Speed: {} MHz'.format(speed)
                except Exception as e:
                    self.logger.debug("Error reading {}: {}".format(source, str(e)))
                    continue
        return 'CPU Speed: N/A'

    def _parse_cpuinfo_speed(self, content):
        """Parse CPU speed from cpuinfo"""
        for line in content.split('\n'):
            if 'cpu MHz' in line:
                return '%1.0f' % float(line.split(':')[1].strip())
        return None

    def _parse_dt_clock(self, content):
        """Parse CPU speed from device tree"""
        try:
            import binascii
            return str(int(binascii.hexlify(content.encode()), 16) / 1000000)
        except BaseException:
            return None

    def _get_fan_info(self):
        """Get fan information"""
        fan_data = {
            'speed': self._read_fan_file('/proc/stb/fp/fan_speed'),
            'voltage': self._read_fan_file('/proc/stb/fp/fan_vlt', hex=True),
            'pwm': self._read_fan_file('/proc/stb/fp/fan_pwm', hex=True)
        }

        if not any(fan_data.values()):
            return 'Fan Info: N/A'

        if self.short_format:
            return "{} - {}V - P:{}".format(
                fan_data['speed'], fan_data['voltage'], fan_data['pwm'])
        return "Speed: {} V: {} PWM: {}".format(
            fan_data['speed'], fan_data['voltage'], fan_data['pwm'])

    def _read_fan_file(self, path, hex=False):
        """Read fan information file"""
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    content = f.readline().strip()
                    return str(int(content, 16)) if hex else content
            except BaseException:
                pass
        return 'N/A'

    def _get_uptime(self):
        """Get system uptime"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return self._format_uptime(uptime_seconds)
        except Exception as e:
            self.logger.warning("Error getting uptime: {}".format(str(e)))
            return 'Uptime: N/A'

    def _format_uptime(self, seconds):
        """Format uptime seconds into human-readable string"""
        intervals = (
            ('days', 86400),
            ('hrs', 3600),
            ('mins', 60),
            ('secs', 1)
        )

        result = []
        for name, count in intervals:
            value = int(seconds // count)
            if value:
                seconds -= value * count
                result.append("{} {}".format(value, name))

        if not result:
            return "Uptime: 0 secs"

        if self.short_format:
            return 'Uptime: ' + ' '.join(result[:3])
        return 'Uptime: ' + ', '.join(result)

    text = property(getText)

    def changed(self, what):
        if what[0] == self.CHANGED_POLL:
            self.downstream_elements.changed(what)

    def destroy(self):
        """Clean up resources"""
        if self.type == self.HDDTEMP:
            self.container.appClosed.remove(self._hddtemp_finished)
            self.container.dataAvail.remove(self._hddtemp_data_available)
        super().destroy()


# Usage Examples:
# Basic Temperature Display:
"""
<widget source="session.CurrentService" render="Label" position="100,100" size="200,25" font="Regular;18">
    <convert type="AglareTemp">Temperature</convert>
</widget>
"""

# Compact System Info Panel:

"""
<panel position="100,100" size="300,150" backgroundColor="#40000000">
    <widget source="session.CurrentService" render="Label" position="10,10" size="280,20" font="Regular;16">
        <convert type="AglareTemp">Temperature,Short</convert>
    </widget>
    <widget source="session.CurrentService" render="Label" position="10,35" size="280,20" font="Regular;16">
        <convert type="AglareTemp">CPULoad,Short</convert>
    </widget>
    <widget source="session.CurrentService" render="Label" position="10,60" size="280,20" font="Regular;16">
        <convert type="AglareTemp">Uptime,Short</convert>
    </widget>
    <widget source="session.CurrentService" render="Label" position="10,85" size="280,20" font="Regular;16">
        <convert type="AglareTemp">Iplocal</convert>
    </widget>
</panel>
"""

# Fan Control Display:

"""
<widget source="session.CurrentService" render="Label" position="100,130" size="300,25" font="Regular;18">
    <convert type="AglareTemp">FanInfo</convert>
</widget>
"""
