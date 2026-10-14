# AglareBitrate.py
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from enigma import (
    eConsoleAppContainer,
    eTimer,
    iServiceInformation,
)
from Components.Console import Console
from Components.Converter.Converter import Converter
from Components.Element import cached
import six
from datetime import datetime
from os import path

DBG = False
DEBUG_FILE = '/tmp/AglareComponents.log'
BITRATE_PATH = '/usr/bin/bitrate'

_image_type = None
_append_to_file = False


def AGDEBUG(my_text=None, append=True, debug_file=DEBUG_FILE):
    global _append_to_file
    if not debug_file or not my_text:
        return

    try:
        mode = 'a' if _append_to_file and append else 'w'
        _append_to_file = True

        with open(debug_file, mode) as f:
            f.write(f'{datetime.now()}\t{my_text}\n')

        if path.getsize(debug_file) > 100000:
            with open(debug_file, 'r+') as f:
                lines = f.readlines()
                f.seek(0)
                f.writelines(lines[10:])
                f.truncate()
    except Exception as e:
        try:
            with open(debug_file, 'a') as f:
                f.write(f'Exception: {e}\n')
        except BaseException:
            pass


def isImageType(img_name=''):
    global _image_type

    if _image_type is None:
        feed_conf = '/etc/opkg/all-feed.conf'
        if path.exists(feed_conf):
            try:
                with open(feed_conf, 'r') as f:
                    content = f.read().lower()
                    if 'vti' in content:
                        _image_type = 'vti'
                    elif 'code.vuplus.com' in content:
                        _image_type = 'vuplus'
                    elif 'openpli-7' in content:
                        _image_type = 'openpli7'
                    elif 'openatv' in content:
                        _image_type = 'openatv'
                        if '/5.3/' in content:
                            _image_type += '5.3'
            except BaseException:
                pass

        if _image_type is None:
            if path.exists(
                    '/usr/lib/enigma2/python/Plugins/SystemPlugins/VTIPanel/'):
                _image_type = 'vti'
            elif path.exists('/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/'):
                _image_type = 'openatv'
            elif path.exists('/usr/lib/enigma2/python/Blackhole'):
                _image_type = 'blackhole'
            elif path.exists('/etc/init.d/start_pkt.sh'):
                _image_type = 'pkt'
            else:
                _image_type = 'unknown'

    return img_name.lower() == _image_type.lower()


class AglareBitrate(Converter, object):
    def __init__(self, type):
        Converter.__init__(self, type)
        self.mode = (type or "").strip().lower()
        self.clear_values()
        self.is_running = False
        self.is_suspended = False
        self.my_console = Console()
        self.container = eConsoleAppContainer()
        self.container.appClosed.append(self.app_closed)
        self.container.dataAvail.append(self.data_avail)

        self.start_timer = eTimer()
        self.start_timer.callback.append(self.start)
        self.start_timer.start(100, True)

        self.run_timer = eTimer()
        self.run_timer.callback.append(self.run_bitrate)

        if path.exists(BITRATE_PATH):
            self.my_console.ePopen(f'chmod 755 {BITRATE_PATH}')

    @cached
    def getText(self):
        vcur = self.vcur if 0 < self.vcur < 100000 else 0
        acur = self.acur if 0 < self.acur < 100000 else 0
        if self.mode in ("video", "v"):
            return f"V: {vcur} Kb/s" if vcur > 0 else ""

        if self.mode in ("audio", "a"):
            return f"A: {acur} Kb/s" if acur > 0 else ""

        if self.mode in ("inline", "single", "oneline", "line"):
            if vcur > 0 and acur > 0:
                return f"V: {vcur} Kb/s A: {acur} Kb/s"
            elif vcur > 0:
                return f"V: {vcur} Kb/s"
            elif acur > 0:
                return f"A: {acur} Kb/s"
            return ""

        if vcur > 0 and acur > 0:
            return f"V: {vcur} Kb/s\nA: {acur} Kb/s"

    text = property(getText)

    def doSuspend(self, suspended):
        if DBG:
            AGDEBUG(
                "[AglareBitrate:suspended] >>> self.is_suspended={}, suspended={}".format(
                    self.is_suspended, suspended))                                               

        if not suspended:
            self.is_suspended = False
            self.start_timer.start(100, True)
        else:
            self.start_timer.stop()
            self.is_suspended = True
            self.my_console.ePopen('killall -9 bitrate', self.clear_values)

    def start(self):
        if not self.is_running:
            if self.source.service:
                if DBG:
                    AGDEBUG("[AglareBitrate:start] initiate run_timer")
                self.is_running = True
                self.run_timer.start(100, True)
            else:
                if DBG:
                    AGDEBUG(
                        "[AglareBitrate:start] wait 100ms for self.source.service")
                self.start_timer.start(100, True)

    def run_bitrate(self):
        if DBG:
            AGDEBUG("[AglareBitrate:run_bitrate] >>>")

        adapter = 0
        demux = 0

        try:
            stream = self.source.service.stream()
            if stream:
                if DBG:
                    AGDEBUG(
                        "[AglareBitrate:run_bitrate] Collecting stream data...")
                stream_data = stream.getStreamingData()
                if stream_data:
                    demux = max(stream_data.get('demux', 0), 0)
                    adapter = max(stream_data.get('adapter', 0), 0)
        except Exception as e:
            if DBG:
                AGDEBUG(
                    "[AglareBitrate:run_bitrate] Exception collecting stream data: {}".format(e))

        try:
            info = self.source.service.info()
            vpid = info.getInfo(iServiceInformation.sVideoPID)
            apid = info.getInfo(iServiceInformation.sAudioPID)
        except Exception as e:
            if DBG:
                AGDEBUG(
                    "[AglareBitrate:run_bitrate] Exception collecting service info: {}".format(e))
            return

        if vpid < 0 and apid < 0:
            if DBG:
                AGDEBUG("[AglareBitrate:run_bitrate] Skipping - no valid PIDs")
            self.run_timer.start(100, True)
            return

        vpid = max(vpid, 0)
        apid = max(apid, 0)

        self.clear_values()

        if isImageType('vti'):
            cmd = 'killall -9 bitrate > /dev/null 2>&1; nice bitrate {} {} {}'.format(
                demux, vpid, apid)
        else:
            cmd = 'killall -9 bitrate > /dev/null 2>&1; nice bitrate {} {} {} {}'.format(
                adapter, demux, vpid, apid)

        if DBG:
            AGDEBUG('[AglareBitrate:run_bitrate] starting "{}"'.format(cmd))
        self.container.execute(cmd)

    def clear_values(self, *args):
        if DBG:
            AGDEBUG("[AglareBitrate:clear_values] >>>")

        self.is_running = False
        self.vmin = self.vmax = self.vavg = self.vcur = 0
        self.amin = self.amax = self.aavg = self.acur = 0
        self.remaining_data = ''
        self.data_lines = []
        Converter.changed(self, (self.CHANGED_POLL,))

    def app_closed(self, retval):
        if DBG:
            AGDEBUG(
                "[AglareBitrate:app_closed] >>> retval={}, is_suspended={}".format(
                    retval, self.is_suspended))                    

        if self.is_suspended:
            self.clear_values()
        else:
            self.run_timer.start(100, True)

    def data_avail(self, data):
        if DBG:
            AGDEBUG(
                "[AglareBitrate:data_avail] >>> data '{}'\n\tself.remaining_data='{}'".format(
                    data, self.remaining_data))           

        data_str = self.remaining_data + \
            (str(data) if six.PY2 else str(data, 'utf-8', 'ignore'))
        lines = data_str.split('\n')

        self.remaining_data = lines[-1] if lines[-1] else ''
        lines = lines[:-1] if lines[-1] else lines

        self.data_lines.extend(lines)

        if len(self.data_lines) >= 2:
            try:
                vparts = self.data_lines[0].split()
                if len(vparts) >= 4:
                    self.vmin, self.vmax, self.vavg, self.vcur = map(
                        int, vparts[:4])

                aparts = self.data_lines[1].split()
                if len(aparts) >= 4:
                    self.amin, self.amax, self.aavg, self.acur = map(
                        int, aparts[:4])
            except (ValueError, IndexError) as e:
                if DBG:
                    AGDEBUG(
                        "[AglareBitrate:data_avail] Parse error: {}".format(e))

            self.data_lines = []
            Converter.changed(self, (self.CHANGED_POLL,))