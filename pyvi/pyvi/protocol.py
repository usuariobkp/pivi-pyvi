# This file is part of the Pyvi software package. Released
# under the Creative Commons ATT-NC-ShareAlire license
# http://creativecommons.org/licenses/by-nc-sa/4.0/
# Copyright (C) 2014, 2015 LESS Industries S.A.
# Lucas Chiesa <lucas@lessinduestries.com>


from struct import Struct
from datetime import datetime
from math import sqrt


class Measurement:

    def __init__(self):
        self.id_ = None
        self.stamp = None
        self.Irms = None
        self.Vrms = None
        self.Power = None

    def get_server(self):
        return self.id_, self.Power, self.Irms, self.Vrms

    def get_mcu(self):
        # We **2 I and V here because we want to get the values as
        # the MCU would send them
        return self.id_, self.Power, self.Irms**2, self.Vrms**2

    def set(self, id_, Power, Irms2, Vrms2):
        self.id_ = id_
        self.Power = Power
        self.Irms = sqrt(Irms2)
        self.Vrms = sqrt(Vrms2)

    def __str__(self):
        return "ID %d, Vrms %.2f, Irms %.2f, Power %.2f" % (self.id_,
                                                            self.Vrms,
                                                            self.Irms,
                                                            self.Power)


class MCUComm:

    def __init__(self):
        """
        One circuit is defined as a string containing 5 fields
        | id_ (16 bits) | Power (32) | Irms**2 (32) | Vrms**2 (32) |
        """
        self.pkg = Struct("<Hfff")

    def unpack(self, string):
        m = Measurement()
        m.set(*self.pkg.unpack(string))
        return m

    def pack(self, measurement):
        return self.pkg.pack(*measurement.get_mcu())

    def read(self, cmd):
        a = reduce(lambda s, c: s + chr(int(c)), cmd, "")
        return self.unpack(a)


class ServerComm:

    def __init__(self, protocol=4, pivi_id=4):
        """
        We add a header with the protocol version when sending it to the cloud.
        We will not send phase for now.
        | HEADER | CIRCUIT | POWER | CURRENT | VOLTAGE | CRC |
        """
        self.prot = protocol
        self.pkg = Struct("<BIHIHfffH")
        self.header_struct = Struct("BIHI")
        pivi_mac = 900
        self.less_mac = pivi_mac + pivi_id

    def create_header(self, msg_type):
        """
        Creates the header for the PIVI measurment package.
        | Protocol | LESS MAC | MSG TYPE | TIMESTAMP |
        """
        t = self.create_timestamp()
        return (self.prot, self.less_mac, msg_type, t)

    def create_timestamp(self):
        """
        Creates a timestamp representation according to the LESS Protocol v4
        spec.
        """
        now = datetime.now()
        year = (now.year - 2000) << 27
        month = now.month << 22
        day = now.day << 17
        hour = now.hour << 12
        minute = now.minute << 6
        second = now.second

        timestamp = year + month + day + hour + minute + second
        return timestamp

    def _crc16(self, crc, byte):
        """
        Calculates crc16-ibm of a message.

        :param crc: CRC calculated in previous iteration.
                    For the first one it should be 0xFFFF.
        :param byte: New byte to calculate the CRC.
        :returns: Current CRC.
        """
        crc ^= byte
        for i in range(0, 8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = (crc >> 1)
        return crc

    def calc_crc16(self, msg):
        msg_int = [ord(c) for c in msg]
        crc = 0xFFFF
        for byte in msg_int[:-2]:
            self._crc16(crc, byte)

        return crc

    def pack(self, measurement):
        id_, P, I, V = measurement.get_server()
        h = self.create_header(1001)
        p = list(h)
        p.append(self.less_mac * 10 + id_)
        p.append(P)
        p.append(I)
        p.append(V)
        p.append(0)
        msg = self.pkg.pack(*p)
        crc = self.calc_crc16(msg)
        p[-1] = crc
        return self.pkg.pack(*p)

    def unpack(self, server_string):
        m = Measurement()
        a = self.pkg.unpack(server_string)
        m.set(a[4], a[5], a[6]**2, a[7]**2)
        return m
