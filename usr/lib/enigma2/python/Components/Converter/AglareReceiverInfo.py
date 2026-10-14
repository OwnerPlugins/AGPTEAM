# -*- coding: utf-8 -*-

from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.Converter.Poll import Poll
from os import popen, statvfs, listdir, path

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']


class AglareReceiverInfo(Poll, Converter):
    HDDTEMP = 0
    LOADAVG = 1
    MEMTOTAL = 2
    MEMFREE = 3
    SWAPTOTAL = 4
    SWAPFREE = 5
    USBINFO = 6
    HDDINFO = 7
    FLASHINFO = 8
    MMCINFO = 9

    def __init__(self, type):
        Converter.__init__(self, type)
        Poll.__init__(self)
        type = type.split(',')
        self.shortFormat = 'Short' in type
        self.fullFormat = 'Full' in type
        self.type = self.get_type_from_string(type)
        self.poll_interval = 5000 if self.type in (
            self.FLASHINFO, self.HDDINFO, self.MMCINFO, self.USBINFO) else 1000
        self.poll_enabled = True

    def get_type_from_string(self, type_list):
        type_mapping = {
            'HddTemp': self.HDDTEMP,
            'LoadAvg': self.LOADAVG,
            'MemTotal': self.MEMTOTAL,
            'MemFree': self.MEMFREE,
            'SwapTotal': self.SWAPTOTAL,
            'SwapFree': self.SWAPFREE,
            'UsbInfo': self.USBINFO,
            'HddInfo': self.HDDINFO,
            'MmcInfo': self.MMCINFO,
        }
        for key, value in type_mapping.items():
            if key in type_list:
                return value
        return self.FLASHINFO

    @cached
    def getText(self):
        if self.type == self.HDDTEMP:
            return self.getHddTemp()
        elif self.type == self.LOADAVG:
            return self.getLoadAvg()
        else:
            entry = self.get_info_entry()
            info = self.get_disk_or_mem_info(entry[0])
            return self.format_text(entry[1], info)

    def get_info_entry(self):
        return {
            self.MEMTOTAL: ('Mem', 'Ram'),
            self.MEMFREE: ('Mem', 'Ram'),
            self.SWAPTOTAL: ('Swap', 'Swap'),
            self.SWAPFREE: ('Swap', 'Swap'),
            self.USBINFO: ('/media/usb', 'USB'),
            self.MMCINFO: ('/media/mmc', 'MMC'),
            self.HDDINFO: ('/media/hdd', 'HDD'),
            self.FLASHINFO: ('/', 'Flash')
        }.get(self.type, ('/', 'Unknown'))

    def get_disk_or_mem_info(self, path_or_value):
        if self.type in (
                self.USBINFO,
                self.MMCINFO,
                self.HDDINFO,
                self.FLASHINFO):
            return self.getDiskInfo(path_or_value)
        return self.getMemInfo(path_or_value)

    def format_text(self, label, info):
        if info[0] == 0:
            return '{}: Not Available'.format(label)
        elif self.shortFormat:
            return '{}: {}, in use: {}%'.format(
                label, self.getSizeStr(info[0]), info[3])
        elif self.fullFormat:
            return '{}: {} Free:{} used:{} ({}%)'.format(
                label,
                self.getSizeStr(info[0]),
                self.getSizeStr(info[2]),
                self.getSizeStr(info[1]),
                info[3])
        else:
            return '{}: {} used:{} Free:{}'.format(
                label,
                self.getSizeStr(info[0]),
                self.getSizeStr(info[1]),
                self.getSizeStr(info[2]))

    @cached
    def getValue(self):
        result = 0
        if self.type in (
                self.MEMTOTAL,
                self.MEMFREE,
                self.SWAPTOTAL,
                self.SWAPFREE):
            entry = {
                self.MEMTOTAL: 'Mem', self.MEMFREE: 'Mem',
                self.SWAPTOTAL: 'Swap', self.SWAPFREE: 'Swap'
            }[self.type]
            result = self.getMemInfo(entry)[3]

        elif self.type in (self.USBINFO, self.MMCINFO, self.HDDINFO, self.FLASHINFO):
            path = {
                self.USBINFO: '/media/usb', self.HDDINFO: '/media/hdd',
                self.MMCINFO: '/media/mmc', self.FLASHINFO: '/'
            }[self.type]
            result = self.getDiskInfo(path)[3]
        return result

    text = property(getText)
    value = property(getValue)
    range = 100  # Added range attribute to fix the skin error

    def is_mmc_device(self, mount_point):
        try:
            mp_lower = mount_point.lower()
            if any(kw in mp_lower for kw in ['mmc', 'sd', 'card', 'emmc']):
                return True

            for device in listdir('/sys/block'):
                if device.startswith('mmcblk') and path.ismount(mount_point):
                    device_path = path.join('/dev', device)
                    with open('/proc/mounts') as f:
                        if any(
                                device_path in line and mount_point in line for line in f):
                            return True
        except BaseException:
            pass
        return False

    def getHddTemp(self):
        try:
            temp = popen('hddtemp -n -q /dev/sda').readline().strip()
            return "{}°C".format(temp) if temp else "No info"
        except BaseException:
            return "No info"

    def getLoadAvg(self):
        try:
            return popen('cat /proc/loadavg').readline()[:15].strip()
        except BaseException:
            return "No info"

    def getMemInfo(self, value):
        result = [0, 0, 0, 0]
        try:
            check = 0
            with open('/proc/meminfo', 'r') as fd:
                for line in fd:
                    if '{}Total'.format(value) in line:
                        check += 1
                        result[0] = int(line.split()[1]) * 1024
                    elif '{}Free'.format(value) in line:
                        check += 1
                        result[2] = int(line.split()[1]) * 1024
                    if check > 1:
                        if result[0] > 0:
                            result[1] = result[0] - result[2]
                            result[3] = (result[1] * 100) / result[0]
                        break
        except BaseException:
            pass
        return result

    def getDiskInfo(self, path):
        result = [0, 0, 0, 0]
        if self.is_mount_point(path):
            try:
                st = statvfs(path)
                if st and 0 not in (st.f_bsize, st.f_blocks):
                    result[0] = st.f_bsize * st.f_blocks
                    result[2] = st.f_bsize * st.f_bavail
                    result[1] = result[0] - result[2]
                    result[3] = (result[1] * 100) / result[0]
            except BaseException:
                pass
        return result

    def is_mount_point(self, path):
        try:
            with open('/proc/mounts', 'r') as fd:
                for line in fd:
                    parts = line.split()
                    if len(parts) > 1 and parts[1] == path:
                        return True
        except BaseException:
            pass
        return False

    def getSizeStr(self, value, u=0):
        fractal = 0
        if value >= 1024:

            while value >= 1024 and u < len(SIZE_UNITS):
                value, mod = divmod(value, 1024)
                fractal = mod * 10 // 1024
                u += 1

        return '{}{} {}'.format(
            value, "." + str(fractal) if fractal else "", SIZE_UNITS[u])

    def doSuspend(self, suspended):
        self.poll_enabled = not suspended
        if not suspended:
            self.downstream_elements.changed((self.CHANGED_POLL,))


"""
<screen name="ReceiverInfoScreen" position="center,center" size="1280,720" title="Receiver Information">
    <!-- Widget per mostrare la temperatura del disco HDD -->
    <widget name="hddTemp" source="ServiceEvent" render="Label" position="50,100" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="green" valign="center">
        <convert type="AglareReceiverInfo">HddTemp</convert>
    </widget>

    <!-- Widget per mostrare il carico medio (LoadAvg) -->
    <widget name="loadAvg" source="ServiceEvent" render="Label" position="50,160" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="yellow" valign="center">
        <convert type="AglareReceiverInfo">LoadAvg</convert>
    </widget>

    <!-- Widget per mostrare la memoria totale -->
    <widget name="memTotal" source="ServiceEvent" render="Label" position="50,220" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="blue" valign="center">
        <convert type="AglareReceiverInfo">MemTotal</convert>
    </widget>

    <!-- Widget per mostrare la memoria libera -->
    <widget name="memFree" source="ServiceEvent" render="Label" position="50,280" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="red" valign="center">
        <convert type="AglareReceiverInfo">MemFree</convert>
    </widget>

    <!-- Widget per mostrare lo spazio swap totale -->
    <widget name="swapTotal" source="ServiceEvent" render="Label" position="50,340" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="purple" valign="center">
        <convert type="AglareReceiverInfo">SwapTotal</convert>
    </widget>

    <!-- Widget per mostrare lo spazio swap libero -->
    <widget name="swapFree" source="ServiceEvent" render="Label" position="50,400" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="orange" valign="center">
        <convert type="AglareReceiverInfo">SwapFree</convert>
    </widget>

    <!-- Widget per mostrare informazioni sul dispositivo USB -->
    <widget name="usbInfo" source="ServiceEvent" render="Label" position="50,460" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="cyan" valign="center">
        <convert type="AglareReceiverInfo">UsbInfo</convert>
    </widget>

    <!-- Widget per mostrare informazioni sul disco HDD -->
    <widget name="hddInfo" source="ServiceEvent" render="Label" position="50,520" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="pink" valign="center">
        <convert type="AglareReceiverInfo">HddInfo</convert>
    </widget>

    <!-- Widget per mostrare informazioni sulla memoria Flash -->
    <widget name="flashInfo" source="ServiceEvent" render="Label" position="50,580" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="lime" valign="center">
        <convert type="AglareReceiverInfo">FlashInfo</convert>
    </widget>

    <!-- Widget per mostrare informazioni sulla memoria MMC -->
    <widget name="mmcInfo" source="ServiceEvent" render="Label" position="50,640" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="magenta" valign="center">
        <convert type="AglareReceiverInfo">MmcInfo</convert>
    </widget>
</screen>
"""