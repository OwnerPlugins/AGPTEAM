# -*- coding: utf-8 -*-

# CaidBar Converter
# Copyright (c) 2boom 2014-16
# v.0.5
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# 04.03.2020 add Short, Full mod by MegAndretH
# 05.03.2020 fix crypt mod by Sirius
# 01.04.2025 @ lululla

from Components.Converter.Poll import Poll
from Components.Converter.Converter import Converter
from enigma import iServiceInformation
from Components.Element import cached
import os
import logging


class AglareCaidBar(Poll, Converter):
    """Enhanced CAID information display converter for Enigma2"""

    def __init__(self, type):
        Converter.__init__(self, type)
        Poll.__init__(self)
        self.logger = logging.getLogger("AglareCaidBar")

        params = type.split(',')
        self.main_color = self._convert_color(params[0].strip())
        self.emm_color = self._convert_color(params[1].strip())
        self.ecm_color = self._convert_color(params[2].strip())

        self.mode = "default"
        if len(params) > 3:
            self.mode = params[3].strip()

        self.custom_caids = []
        if len(params) > 4:
            self.custom_caids = params[4].split()

        self._init_caid_mappings()

        self.poll_interval = 1000
        self.poll_enabled = True
        self.current_caids = []

    def _init_caid_mappings(self):
        if self.mode == "Short":
            self.default_caids = [
                "SEC", "VIA", "IRD", "NDS", "CON",
                "PVU", "NAG", "EXS", "VRM", "BiSS"]
            self.caid_mappings = {
                "a": {
                    "01": "SEC", "05": "VIA", "06": "IRD", "07": "DIC",
                    "09": "NDS", "0B": "CON", "0D": "CRW", "0E": "PVU",
                    "10": "TAN", "18": "NAG", "22": "COD", "26": "BiSS",
                    "27": "EXS", "4B": "TOP", "54": "GOS", "55": "BUL",
                    "56": "VRM", "7B": "DRE", "A1": "ROS"},
                "b": {"17": "VRM"},
                "c": {"02": "BET", "22": "BET", "62": "BET"},
                "d": {
                    "20": "ACR", "BF": "SKY", "D0": "XCR", "D1": "XCR",
                    "D4": "OCR", "E0": "DRE", "E1": "DRE", "60": "SCR",
                    "61": "SCR", "63": "SCR", "70": "DCR", "EA": "CGU",
                    "EE": "BUL", "FC": "PAN"}}

        elif self.mode == "Full":
            self.default_caids = [
                "SECA", "VIACCESS", "IRDETO", "VIDEOGUARD", "CONAX",
                "POWERVU", "NAGRAVISION", "EXSET", "VERIMATRIX", "BiSS"
            ]
            self.caid_mappings = {
                "a": {
                    "01": "MEDIAGUARD", "05": "VIACCESS", "06": "IRDETO",
                    "07": "DIGICIPHER", "09": "VIDEOGUARD", "0B": "CONAX",
                    "0D": "CRYPTOWORKS", "0E": "POWERVU", "10": "TANDBERG",
                    "18": "NAGRAVISION", "22": "CODICRYPT", "26": "BiSS",
                    "27": "EXSET", "4B": "TOPVELL", "54": "GOSPELL",
                    "55": "BULCRYPT", "56": "VERIMATRIX", "7B": "DRE-CRYPT",
                    "A1": "ROSSCRYPT"},
                "b": {"17": "VERIMATRIX"},
                "c": {"02": "BETACRYPT", "22": "BETACRYPT", "62": "BETACRYPT"},
                "d": {
                    "20": "ALPHACRYPT", "BF": "SKYPILOT", "D0": "X-CRYPT",
                    "D1": "X-CRYPT", "D4": "OMNICRYPT", "E0": "DRE-CRYPT",
                    "E1": "DRE-CRYPT", "60": "SKYCRYPT", "61": "SKYCRYPT",
                    "63": "SKYCRYPT", "70": "DREAMCRYPT", "EA": "CRYPTOGUARD",
                    "EE": "BULCRYPT", "FC": "PANACCESS"}}

        else:
            self.default_caids = [
                "S", "V", "I", "ND", "CO", "PV", "N", "EX", "VM", "BI"
            ]
            self.caid_mappings = {
                "a": {
                    "01": "S", "05": "V", "06": "I", "07": "DC",
                    "09": "ND", "0B": "CO", "0D": "CW", "0E": "PV",
                    "10": "TA", "18": "N", "22": "CC", "26": "BI",
                    "27": "EX", "4B": "T", "54": "G", "55": "BC",
                    "56": "VM", "7B": "D", "A1": "RC"},
                "b": {"17": "VM"},
                "c": {"02": "BE", "22": "BE", "62": "BE"},
                "d": {
                    "20": "AC", "BF": "SP", "D0": "XC", "D1": "XC",
                    "D4": "OC", "E0": "D", "E1": "D", "60": "SC",
                    "61": "SC", "63": "SC", "70": "DC", "EA": "CG",
                    "EE": "BC", "FC": "P"}}

    def _convert_color(self, hex_color):
        color_map = {
            '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
            '6': '6', '7': '7', '8': '8', '9': '9',
            'a': ':', 'b': ';', 'c': '<', 'd': '=', 'e': '>', 'f': '?',
            'A': ':', 'B': ';', 'C': '<', 'D': '=', 'E': '>', 'F': '?'
        }
        return r'\c' + ''.join(color_map.get(c, '') for c in hex_color[1:])

    def _get_caid_from_ecm(self):
        ecm_files = ["/tmp/ecm.info", "/tmp/ecm1.info"]
        for ecm_file in ecm_files:
            if os.path.isfile(ecm_file):
                try:
                    with open(ecm_file, 'r') as f:
                        for line in f:
                            if "caid:" in line.lower():
                                return line.strip().split(
                                )[-1][2:].zfill(4).upper()
                            elif "caid" in line.lower():
                                return line.split(
                                    ',')[0].split()[-1][2:].upper()
                except Exception as e:
                    self.logger.warning(
                        f"Error reading ECM file {ecm_file}: {str(e)}")
        return ""

    def _get_caid_name(self, caid):
        if caid.startswith('4A'):
            return self.caid_mappings['d'].get(caid[2:], "?")
        elif caid.startswith('17'):
            if caid[2:] in self.caid_mappings['c']:
                return self.caid_mappings['c'].get(caid[2:], "?")
            return self.caid_mappings['b'].get(caid[:2], "?")
        return self.caid_mappings['a'].get(caid[:2], "?")

    @cached
    def getText(self):
        service = self.source.service
        if not service:
            return " ".join(
                f"{self.main_color}{caid}" for caid in self.default_caids)

        info = service.info()
        if not info:
            return ""

        caid_info = info.getInfoObject(iServiceInformation.sCAIDs)
        if not caid_info:
            return ""

        ecm_caid = self._get_caid_from_ecm()
        ecm_caid_name = self._get_caid_name(ecm_caid) if ecm_caid else None

        self.current_caids = []
        display_parts = []

        for caid in self.default_caids:
            if ecm_caid_name and caid == ecm_caid_name:
                display_parts.append(f"{self.ecm_color}{caid}")
            elif caid in (self._get_caid_name(f"{c:04X}"[:2]) for c in caid_info):
                display_parts.append(f"{self.emm_color}{caid}")
            else:
                display_parts.append(f"{self.main_color}{caid}")

        for caid in caid_info:
            caid_str = f"{caid:04X}"
            caid_name = self._get_caid_name(caid_str)

            if caid_name not in self.default_caids and caid_name not in self.current_caids:
                self.current_caids.append(caid_name)

                if ecm_caid_name and caid_name == ecm_caid_name:
                    display_parts.append(f"{self.ecm_color}{caid_name}")
                else:
                    display_parts.append(f"{self.emm_color}{caid_name}")

        return " ".join(display_parts)

    text = property(getText)

    def changed(self, what):
        if what[0] == self.CHANGED_SPECIFIC or what[0] == self.CHANGED_POLL:
            Converter.changed(self, what)


"""
<widget source="session.CurrentService" render="Label" position="100,100" size="400,30" font="Regular;20">
    <convert type="AglareCaidBar">#FFFFFF,#FF0000,#00FF00</convert>
</widget>
"""

"""
<widget source="session.CurrentService" render="Label" position="100,130" size="400,30" font="Regular;20">
    <convert type="AglareCaidBar">#FFFFFF,#FF0000,#00FF00,Short</convert>
</widget>
"""

"""
<widget source="session.CurrentService" render="Label" position="100,160" size="400,30" font="Regular;20">
    <convert type="AglareCaidBar">#FFFFFF,#FF0000,#00FF00,Full,SEC VIACCESS IRDETO</convert>
</widget>
"""
