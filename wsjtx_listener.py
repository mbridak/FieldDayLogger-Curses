"""We welcome the spawn of Satan(FT8) into our home."""
import logging
import struct
import socket


class WsjtxListener:
    """Listen for UDP packets from wsjt-x"""

    def __init__(self):
        self.multicast_port = 2237
        self.multicast_group = "224.1.1.1"
        self.interface_ip = "0.0.0.0"
        self.datadict = {}
        self.dupdict = {}
        self.band = None
        self.mode = None
        self.ft8dupe = None
        self.wsjtx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.wsjtx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.wsjtx.bind(("", self.multicast_port))
        mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton(
            self.interface_ip
        )
        self.wsjtx.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, bytes(mreq))

    @staticmethod
    def getint(bytestring):
        """
        Returns an int from a bigendian signed 4 byte string
        """
        return int.from_bytes(bytestring, byteorder="big", signed=True)

    @staticmethod
    def getuint(bytestring):
        """
        Returns an int from a bigendian unsigned 4 byte string
        """
        return int.from_bytes(bytestring, byteorder="big", signed=False)

    def getvalue(self, item):
        """I don't remember what this does."""
        if item in self.datadict:
            return self.datadict[item]
        return "NOT_FOUND"

    def get_udp(self):
        """
        This will process incomming UDP log packets from WSJT-X.
        I Hope...
        """
        self.datadict = {}
        datagram = self.wsjtx.recv(1500)
        logging.info("%s", datagram)

        if datagram[0:4] != b"\xad\xbc\xcb\xda":
            return  # bail if no wsjt-x magic number
        version = self.getuint(datagram[4:8])
        packettype = self.getuint(datagram[8:12])
        uniquesize = self.getint(datagram[12:16])
        unique = datagram[16 : 16 + uniquesize].decode()
        payload = datagram[16 + uniquesize :]

        if packettype == 0:  # Heartbeat
            hbmaxschema = self.getuint(payload[0:4])
            hbversion_len = self.getint(payload[4:8])
            hbversion = payload[8 : 8 + hbversion_len].decode()
            line = (
                f"heartbeat: sv:{version} p:{packettype} "
                f"u:{unique}: ms:{hbmaxschema} av:{hbversion}"
            )
            logging.info(line)
            return

        if packettype == 1:  # Status
            [dialfreq] = struct.unpack(">Q", payload[0:8])
            modelen = self.getint(payload[8:12])
            mode = payload[12 : 12 + modelen].decode()
            payload = payload[12 + modelen :]
            dxcalllen = self.getint(payload[0:4])
            dxcall = payload[4 : 4 + dxcalllen].decode()
            logging.info(
                "Status: sv:%s p:%s u:%s df:%s m:%s dxc:%s",
                version,
                packettype,
                unique,
                dialfreq,
                mode,
                dxcall,
            )

            if f"{dxcall}{self.band}{self.mode}" in self.dupdict:
                self.ft8dupe = f"{dxcall} {self.band}M {self.mode} FT8 Dupe!"
            return

        if packettype == 2:  # Decode commented out because we really don't care
            return

        if packettype != 12:
            return  # bail if not logged ADIF
        # if log packet it will contain this nugget.
        gotcall = datagram.find(b"<call:")
        if gotcall != -1:
            datagram = datagram[gotcall:]  # strip everything else
        else:
            return  # Otherwise we don't want to bother with this packet

        data = datagram.decode()
        splitdata = data.upper().split("<")

        for data in splitdata:
            if data:
                tag = data.split(":")
                if tag == ["EOR>"]:
                    break
                self.datadict[tag[0]] = tag[1].split(">")[1].strip()

        contest_id = self.getvalue("CONTEST_ID")
        if contest_id == "ARRL-FIELD-DAY":
            call = self.getvalue("CALL")
            dayt = self.getvalue("QSO_DATE")
            tyme = self.getvalue("TIME_ON")
            the_dt = f"{dayt[0:4]}-{dayt[4:6]}-{dayt[6:8]} {tyme[0:2]}:{tyme[2:4]}:{tyme[4:6]}"
            freq = int(float(self.getvalue("FREQ")) * 1000000)
            band = self.getvalue("BAND").split("M")[0]
            grid = self.getvalue("GRIDSQUARE")
            name = self.getvalue("NAME")
            if grid == "NOT_FOUND" or name == "NOT_FOUND":
                if grid == "NOT_FOUND":
                    grid = ""
                if name == "NOT_FOUND":
                    name = ""
            hisclass, hissect = self.getvalue("SRX_STRING").split(" ")
            try:
                power = int(float(self.getvalue("TX_PWR")))
            except ValueError:
                power = None

            contact = (
                call,
                hisclass,
                hissect,
                the_dt,
                freq,
                band,
                "DI",
                power,
                grid,
                name,
            )
            return contact
