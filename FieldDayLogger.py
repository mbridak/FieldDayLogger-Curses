#!/usr/bin/env python3
"""
Field Day Logger Curses
Who's at fault: Mike Bridak K6GTE
Contact_______: michael.bridak@gmail.com
"""

# COLOR_BLACK	Black
# COLOR_BLUE	Blue
# COLOR_CYAN	Cyan (light greenish blue)
# COLOR_GREEN	Green
# COLOR_MAGENTA	Magenta (purplish red)
# COLOR_RED	Red
# COLOR_WHITE	White
# COLOR_YELLOW	Yellow

# "🗃️ ⁉ 👁️ 🕳️ 🪪 💩 🚫 🛰️ 📡 🌥️ 🗺"

# The next 3 lines prove I'm a bad person.
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=global-statement

from math import radians, sin, cos, atan2, sqrt, asin, pi
from itertools import chain
import curses
import time
import sys
import os
import re
import socket
from pathlib import Path
from shutil import copyfile
from curses.textpad import rectangle
from curses import wrapper
from datetime import datetime, timedelta
import threading
import logging
import uuid
import queue
from json import loads, dumps, JSONDecodeError
import requests

from lib.cat_interface import CAT
from lib.lookup import HamDBlookup, HamQTH, QRZlookup
from lib.database import DataBase
from lib.cwinterface import CW
from lib.edittextfield import EditTextField
from lib.wsjtx_listener import WsjtxListener
from lib.settings import SettingsScreen
from lib.version import __version__

if Path("./debug").exists():
    logging.basicConfig(
        filename="debug.log",
        filemode="w+",
        format=(
            "[%(asctime)s] %(levelname)s %(module)s - "
            "%(funcName)s Line %(lineno)d:\n%(message)s"
        ),
        datefmt="%H:%M:%S",
        level=logging.DEBUG,
    )
    logging.debug("Debug started")
else:
    logging.basicConfig(level=logging.CRITICAL)

# If no preference file exists, one is created from this dictionary.
preference = {
    "mycall": "Call",
    "myclass": "",
    "mysection": "",
    "power": "100",
    "altpower": 0,
    "usehamdb": 0,
    "useqrz": 0,
    "usehamqth": 0,
    "lookupusername": "w1aw",
    "lookuppassword": "secret",
    "userigctld": 0,
    "useflrig": 0,
    "CAT_ip": "localhost",
    "CAT_port": 4532,
    "cloudlog": 0,
    "cloudlogapi": "c01234567890123456789",
    "cloudlogurl": "https://www.cloudlog.com/Cloudlog/index.php/api/",
    "cloudlogstationid": "",
    "usemarker": 0,
    "markerfile": ".xplanet/markers/ham",
    "cwtype": 0,
    "CW_IP": "localhost",
    "CW_port": 6789,
    "useserver": 1,
    "multicast_group": "224.1.1.1",
    "multicast_port": "2239",
    "interface_ip": "0.0.0.0",
}
# incase preference becomes corrupt make a backup.
reference_preference = preference.copy()

ft8_watcher = WsjtxListener()

contactlookup = {
    "call": "",
    "grid": "",
    "bearing": "",
    "name": "",
    "nickname": "",
    "error": "",
    "distance": "",
}
os.environ.setdefault("ESCDELAY", "25")
stdscr = curses.initscr()
height, width = stdscr.getmaxyx()
hiscall_field = EditTextField(stdscr, y=9, x=1, length=14)
hisclass_field = EditTextField(stdscr, y=9, x=20, length=4)
hissection_field = EditTextField(stdscr, y=9, x=27, length=3)

if height < 24 or width < 80:
    print("Terminal size needs to be at least 80x24")
    curses.endwin()
    sys.exit()
qsoew = 0
qso_edit_fields = None
qso = []
end_program = False
cat_control = None
look_up = None
cloudlogauthenticated = False
BackSpace = 263
Escape = 27
QuestionMark = 63
EnterKey = 10
Space = 32

# Since Field Day is not a 'contest', there are no band limitations
bands = (
    "160",
    "80",
    "40",
    "20",
    "15",
    "10",
    "6",
    "2",
    "222",
    "432",
    "SAT",
)
dfreq = {
    "160": "1.830",
    "80": "3.530",
    "60": "53.300",
    "40": "7.030",
    "20": "14.030",
    "15": "21.030",
    "10": "28.030",
    "6": "50.030",
    "2": "144.030",
    "222": "222.030",
    "432": "432.030",
    "SAT": "0.0",
}

modes = ("PH", "CW", "DI")
band = "40"
mode = "CW"
qrp = False
highpower = False
contacts = ""
contactsOffset = 0
logNumber = 0
kbuf = ""
editbuf = ""
maxFieldLength = [17, 5, 7, 20, 4, 3, 4]
maxEditFieldLength = [10, 17, 5, 4, 20, 4, 3, 4, 10]
inputFieldFocus = 0
editFieldFocus = 1
hiscall = ""
hissection = ""
hisclass = ""
mygrid = None
db = DataBase("FieldDay.db")
fkeys = {}
cw = None

wrkdsections = []
scp = []
secPartial = {}
secName = {}
secState = {}
oldfreq = "0"
oldmode = ""
rigonline = None

# New stuff for multiuser
people = {}
connect_to_server = False
groupcall = None
server_commands = []
server_seen = None
server_udp = None
udp_fifo = queue.Queue()
multicast_group = "224.1.1.1"
multicast_port = 2239
interface_ip = "0.0.0.0"


def relpath(filename):
    """
    Checks to see if program has been packaged with pyinstaller.
    If so base dir is in a temp folder.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = getattr(sys, "_MEIPASS")
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)


def has_internet():
    """pings external dns server to check internet"""
    try:
        socket.create_connection(("1.1.1.1", 53))
        return True
    except OSError:
        return False


def show_people():
    """Display operators"""
    rev_dict = {}
    for key, value in people.items():
        rev_dict.setdefault(value, set()).add(key)
    result = set(
        chain.from_iterable(
            values for key, values in rev_dict.items() if len(values) > 1
        )
    )
    # users_list.clear()
    # users_list.insertPlainText("    Operators\n")
    for op_callsign in people:
        if op_callsign in result:
            pass
            # self.users_list.setTextColor(QtGui.QColor(245, 121, 0))
            # self.users_list.insertPlainText(
            #     f"{op_callsign.rjust(6,' ')} {self.people.get(op_callsign).rjust(6, ' ')}\n"
            # )
            # self.users_list.setTextColor(QtGui.QColor(211, 215, 207))
        else:
            pass
            # self.users_list.insertPlainText(
            #     f"{op_callsign.rjust(6,' ')} {self.people.get(op_callsign).rjust(6, ' ')}\n"
            # )


def show_dirty_records():
    """Checks for dirty records, Changes Generate Log button to give visual indication."""
    if connect_to_server:
        result = db.count_all_dirty_contacts()
        all_dirty_count = result.get("alldirty")
        if all_dirty_count:
            pass
            # self.genLogButton.setStyleSheet("background-color: red;")
            # self.genLogButton.setText(f"UnVfyd: {all_dirty_count}")
        else:
            pass
            # self.genLogButton.setStyleSheet("background-color: rgb(92, 53, 102);")
            # self.genLogButton.setText("Generate Logs")


def resolve_dirty_records():
    """Go through dirty records and submit them to the server."""
    if connect_to_server:
        records = db.fetch_all_dirty_contacts()
        # infobox.setTextColor(QtGui.QColor(211, 215, 207))
        # infobox.insertPlainText(f"Resolving {len(records)} unsent contacts.\n")
        # app.processEvents()
        if records:
            for count, dirty_contact in enumerate(records):
                contact = {}
                contact["cmd"] = "POST"
                contact["station"] = preference.get("mycall")
                stale = datetime.now() + timedelta(seconds=30)
                contact["expire"] = stale.isoformat()
                contact["unique_id"] = dirty_contact.get("unique_id")
                contact["hiscall"] = dirty_contact.get("callsign")
                contact["class"] = dirty_contact.get("class")
                contact["section"] = dirty_contact.get("section")
                contact["date_and_time"] = dirty_contact.get("date_time")
                contact["frequency"] = dirty_contact.get("frequency")
                contact["band"] = dirty_contact.get("band")
                contact["mode"] = dirty_contact.get("mode")
                contact["power"] = dirty_contact.get("power")
                contact["grid"] = dirty_contact.get("grid")
                contact["opname"] = dirty_contact.get("opname")
                server_commands.append(contact)
                bytesToSend = bytes(dumps(contact), encoding="ascii")
                try:
                    server_udp.sendto(
                        bytesToSend,
                        (multicast_group, int(multicast_port)),
                    )
                except OSError as err:
                    logging.warning("%s", err)
                time.sleep(0.1)  # Do I need this?
                # infobox.insertPlainText(f"Sending {count}\n")
                # app.processEvents()


def clear_dirty_flag(unique_id):
    """clear the dirty flag on record once response is returned from server."""
    db.clear_dirty_flag(unique_id)
    show_dirty_records()


def remove_confirmed_commands(data):
    """Removed confirmed commands from the sent commands list."""
    for index, item in enumerate(server_commands):
        if item.get("unique_id") == data.get("unique_id") and item.get(
            "cmd"
        ) == data.get("subject"):
            server_commands.pop(index)
            clear_dirty_flag(data.get("unique_id"))
            # infoline.setText(f"Confirmed {data.get('subject')}")


def check_for_stale_commands():
    """
    Check through server commands to see if there has not been a reply in 30 seconds.
    Resubmits those that are stale.
    """
    if connect_to_server:
        for index, item in enumerate(server_commands):
            expired = datetime.strptime(item.get("expire"), "%Y-%m-%dT%H:%M:%S.%f")
            if datetime.now() > expired:
                newexpire = datetime.now() + timedelta(seconds=30)
                server_commands[index]["expire"] = newexpire.isoformat()
                bytesToSend = bytes(dumps(item), encoding="ascii")
                try:
                    server_udp.sendto(
                        bytesToSend,
                        (multicast_group, int(multicast_port)),
                    )
                except OSError as err:
                    logging.warning("%s", err)


def send_chat():
    """Sends UDP chat packet with text entered in chat_entry field."""
    message = "stub"  # chat_entry.text()
    packet = {"cmd": "CHAT"}
    packet["sender"] = preference.get("mycall")
    packet["message"] = message
    bytesToSend = bytes(dumps(packet), encoding="ascii")
    try:
        server_udp.sendto(bytesToSend, (multicast_group, int(multicast_port)))
    except OSError as err:
        logging.warning("%s", err)
    # chat_entry.setText("")


def display_chat(sender, body):
    """Displays the chat history."""
    if preference.get("mycall") in body.upper():
        pass
        # chatlog.setTextColor(QtGui.QColor(245, 121, 0))
    # chatlog.insertPlainText(f"\n{sender}: {body}")
    # chatlog.setTextColor(QtGui.QColor(211, 215, 207))
    # chatlog.ensureCursorVisible()


def watch_udp():
    """Puts UDP datagrams in a FIFO queue"""
    while True:
        if connect_to_server:
            try:
                datagram = server_udp.recv(1500)
            except socket.timeout:
                time.sleep(1)
                continue
            if datagram:
                udp_fifo.put(datagram)
        else:
            time.sleep(1)


def check_udp_queue():
    """checks the UDP datagram queue."""
    global server_seen
    global groupcall
    if server_seen:
        if datetime.now() > server_seen:
            pass
            # group_call_indicator.setStyleSheet(
            #     "border: 1px solid green;\nbackground-color: red;\ncolor: yellow;"
            # )
    while not udp_fifo.empty():
        datagram = udp_fifo.get()
        try:
            json_data = loads(datagram.decode())
        except UnicodeDecodeError as err:
            the_error = f"Not Unicode: {err}\n{datagram}"
            logging.info(the_error)
            continue
        except JSONDecodeError as err:
            the_error = f"Not JSON: {err}\n{datagram}"
            logging.info(the_error)
            continue
        logging.info("%s", json_data)

        if json_data.get("cmd") == "PING":
            if json_data.get("station"):
                band_mode = f"{json_data.get('band')} {json_data.get('mode')}"
                if people.get(json_data.get("station")) != band_mode:
                    people[json_data.get("station")] = band_mode
                show_people()
            if json_data.get("host"):
                server_seen = datetime.now() + timedelta(seconds=30)
                # group_call_indicator.setStyleSheet("border: 1px solid green;")
            continue

        if json_data.get("cmd") == "RESPONSE":
            if json_data.get("recipient") == preference.get("mycall"):
                if json_data.get("subject") == "HOSTINFO":
                    groupcall = str(json_data.get("groupcall"))
                    # myclassEntry.setText(str(json_data.get("groupclass")))
                    # mysectionEntry.setText(str(json_data.get("groupsection")))
                    # group_call_indicator.setText(groupcall)
                    # changemyclass()
                    # changemysection()
                    # mycallEntry.hide()
                    server_seen = datetime.now() + timedelta(seconds=30)
                    # group_call_indicator.setStyleSheet("border: 1px solid green;")
                    return
                if json_data.get("subject") == "LOG":
                    pass
                    # infoline.setText("Server Generated Log.")
                remove_confirmed_commands(json_data)
                continue

        if json_data.get("cmd") == "CHAT":
            display_chat(json_data.get("sender"), json_data.get("message"))
            continue

        if json_data.get("cmd") == "GROUPQUERY":
            if groupcall:
                send_status_udp()


def query_group():
    """Sends request to server asking for group call/class/section."""
    update = {
        "cmd": "GROUPQUERY",
        "station": preference["mycall"],
    }
    bytesToSend = bytes(dumps(update), encoding="ascii")
    try:
        server_udp.sendto(bytesToSend, (multicast_group, int(multicast_port)))
    except OSError as err:
        logging.warning("%s", err)


def send_status_udp():
    """Send status update to server informing of our band and mode"""
    if connect_to_server:
        if groupcall is None and preference["mycall"] != "":
            query_group()
            return

        update = {
            "cmd": "PING",
            "mode": mode,
            "band": band,
            "station": preference["mycall"],
        }
        bytesToSend = bytes(dumps(update), encoding="ascii")
        try:
            server_udp.sendto(bytesToSend, (multicast_group, int(multicast_port)))
        except OSError as err:
            logging.warning("%s", err)

        check_for_stale_commands()


def clearcontactlookup():
    """clearout the contact lookup"""
    contactlookup["call"] = ""
    contactlookup["grid"] = ""
    contactlookup["name"] = ""
    contactlookup["nickname"] = ""
    contactlookup["error"] = ""
    contactlookup["distance"] = ""
    contactlookup["bearing"] = ""


def lookupmygrid():
    """lookup my own gridsquare"""
    global mygrid
    if look_up and has_internet():
        mygrid, _, _, _ = look_up.lookup(preference["mycall"])
        logging.info("%s", mygrid)


def lazy_lookup(acall: str):
    """El Lookup De Lazy"""
    if look_up and has_internet():
        if acall == contactlookup["call"]:
            return
        contactlookup["call"] = acall
        (
            contactlookup["grid"],
            contactlookup["name"],
            contactlookup["nickname"],
            contactlookup["error"],
        ) = look_up.lookup(acall)
        if contactlookup["name"] == "NOT_FOUND NOT_FOUND":
            contactlookup["name"] = "NOT_FOUND"
        if contactlookup["grid"] == "NOT_FOUND":
            contactlookup["grid"] = ""
        if contactlookup["grid"] and mygrid:
            contactlookup["distance"] = distance(mygrid, contactlookup["grid"])
            contactlookup["bearing"] = bearing(mygrid, contactlookup["grid"])
            # displayinfo(f"{contactlookup['name'][:33]}", line=1)
            # displayinfo(
            #     f"{contactlookup['grid']} "
            #     f"{round(contactlookup['distance'])}km "
            #     f"{round(contactlookup['bearing'])}deg"
            # )
        logging.info("%s", contactlookup)


def distance(grid1: str, grid2: str) -> float:
    """
    Takes two maidenhead gridsquares and returns the distance between the two in kilometers.
    """
    lat1, lon1 = gridtolatlon(grid1)
    lat2, lon2 = gridtolatlon(grid2)
    return round(haversine(lon1, lat1, lon2, lat2))


def bearing(grid1: str, grid2: str) -> float:
    """calculate bearing to contact"""
    lat1, lon1 = gridtolatlon(grid1)
    lat2, lon2 = gridtolatlon(grid2)
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)
    londelta = lon2 - lon1
    why = sin(londelta) * cos(lat2)
    exs = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(londelta)
    brng = atan2(why, exs)
    brng *= 180 / pi

    if brng < 0:
        brng += 360

    return round(brng)


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees)
    """
    # convert degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    aye = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    cee = 2 * asin(sqrt(aye))
    arrgh = 6372.8  # Radius of earth in kilometers.
    return cee * arrgh


def gridtolatlon(maiden):
    """
    Converts a maidenhead gridsquare to a latitude longitude pair.
    """
    maiden = str(maiden).strip().upper()

    length = len(maiden)
    if not 8 >= length >= 2 and length % 2 == 0:
        return 0, 0

    lon = (ord(maiden[0]) - 65) * 20 - 180
    lat = (ord(maiden[1]) - 65) * 10 - 90

    if length >= 4:
        lon += (ord(maiden[2]) - 48) * 2
        lat += ord(maiden[3]) - 48

    if length >= 6:
        lon += (ord(maiden[4]) - 65) / 12 + 1 / 24
        lat += (ord(maiden[5]) - 65) / 24 + 1 / 48

    if length >= 8:
        lon += (ord(maiden[6])) * 5.0 / 600
        lat += (ord(maiden[7])) * 2.5 / 600

    return lat, lon


def call_lookup(call):
    """Lookup call on QRZ"""
    grid = False
    name = False
    internet_good = has_internet()
    if look_up and internet_good:
        grid, name, _, _ = look_up.lookup(call)
    return grid, name


def cloudlogauth():
    """Authenticate cloudlog"""
    global cloudlogauthenticated
    cloudlogauthenticated = False
    if preference["cloudlog"]:
        try:
            test = f"{preference['cloudlogurl'][:-3]}auth/{preference['cloudlogapi']}"
            r = requests.get(test, params={}, timeout=2.0)
            if r.status_code == 200 and r.text.find("<status>") > 0:
                if (
                    r.text[r.text.find("<status>") + 8 : r.text.find("</status>")]
                    == "Valid"
                ):
                    cloudlogauthenticated = True
        except requests.exceptions.RequestException as err:
            logging.debug("****Cloudlog Auth Error:****\n%s", err)


def getband(freq):
    """
    Takes a frequency in hz and returns the band.
    """
    if freq.isnumeric():
        frequency = int(float(freq))
        if 2000000 > frequency > 1800000:
            return "160"
        if 4000000 > frequency > 3500000:
            return "80"
        if 5406000 > frequency > 5330000:
            return "60"
        if 7300000 > frequency > 7000000:
            return "40"
        if 10150000 > frequency > 10100000:
            return "30"
        if 14350000 > frequency > 14000000:
            return "20"
        if 18168000 > frequency > 18068000:
            return "17"
        if 21450000 > frequency > 21000000:
            return "15"
        if 24990000 > frequency > 24890000:
            return "12"
        if 29700000 > frequency > 28000000:
            return "10"
        if 54000000 > frequency > 50000000:
            return "6"
        if 148000000 > frequency > 144000000:
            return "2"

    return "0"


def getmode(rigmode):
    """Returns mode compatible with logging"""
    if rigmode in ("CW", "CWR"):
        return "CW"
    if rigmode in ("USB", "LSB", "FM", "AM"):
        return "PH"
    return "DI"  # All else digital


def poll_radio():
    """Polls the radio for band and mode"""
    global oldfreq, oldmode, rigonline
    if cat_control:
        newfreq = cat_control.get_vfo()
        newmode = cat_control.get_mode()
        if newfreq == "" or newmode == "":
            rigonline = False
            return
        rigonline = True
        if newfreq != oldfreq or newmode != oldmode:
            oldfreq = newfreq
            oldmode = newmode
            setband(str(getband(newfreq)))
            setmode(str(getmode(newmode)))
    else:
        rigonline = None


def read_cw_macros():
    """
    Reads in the CW macros, firsts it checks to see if the file exists. If it does not,
    and this has been packaged with pyinstaller it will copy the default file from the
    temp directory this is running from... In theory.
    """
    if (
        getattr(sys, "frozen", False)
        and hasattr(sys, "_MEIPASS")
        and not Path("./cwmacros_fd.txt").exists()
    ):
        logging.info("copying default macro file.")
        copyfile(relpath("cwmacros_fd.txt"), "./cwmacros_fd.txt")
    with open("./cwmacros_fd.txt", "r", encoding="utf-8") as file_descriptor:
        for line in file_descriptor:
            try:
                fkey, buttonname, cwtext = line.split("|")
                fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
            except ValueError as err:
                logging.info("%s", err)


def process_macro(macro):
    """process string substitutions"""
    macro = macro.upper()
    macro = macro.replace("{MYCALL}", preference["mycall"])
    macro = macro.replace("{MYCLASS}", preference["myclass"])
    macro = macro.replace("{MYSECT}", preference["mysection"])
    macro = macro.replace("{HISCALL}", hiscall)
    return macro


def check_function_keys(key):
    """Sends a CW macro if a function key was pressed."""
    if cw:
        if key == curses.KEY_F1 and "F1" in fkeys:
            cw.sendcw(process_macro(fkeys["F1"][1]))
        elif key == curses.KEY_F2 and "F2" in fkeys:
            cw.sendcw(process_macro(fkeys["F2"][1]))
        elif key == curses.KEY_F3 and "F3" in fkeys:
            cw.sendcw(process_macro(fkeys["F3"][1]))
        elif key == curses.KEY_F4 and "F4" in fkeys:
            cw.sendcw(process_macro(fkeys["F4"][1]))
        elif key == curses.KEY_F5 and "F5" in fkeys:
            cw.sendcw(process_macro(fkeys["F5"][1]))
        elif key == curses.KEY_F6 and "F6" in fkeys:
            cw.sendcw(process_macro(fkeys["F6"][1]))
        elif key == curses.KEY_F7 and "F7" in fkeys:
            cw.sendcw(process_macro(fkeys["F7"][1]))
        elif key == curses.KEY_F8 and "F8" in fkeys:
            cw.sendcw(process_macro(fkeys["F8"][1]))
        elif key == curses.KEY_F9 and "F9" in fkeys:
            cw.sendcw(process_macro(fkeys["F9"][1]))
        elif key == curses.KEY_F10 and "F10" in fkeys:
            cw.sendcw(process_macro(fkeys["F10"][1]))
        elif key == curses.KEY_F11 and "F11" in fkeys:
            cw.sendcw(process_macro(fkeys["F11"][1]))
        elif key == curses.KEY_F12 and "F12" in fkeys:
            cw.sendcw(process_macro(fkeys["F12"][1]))
        elif key == 43 and cw.servertype == 1:
            cw.speed += 1
            cw.sendcw(f"\x1b2{cw.speed}")
            statusline()
        elif key == 45 and cw.servertype == 1:
            cw.speed -= 1
            if cw.speed < 5:
                cw.speed = 5
            cw.sendcw(f"\x1b2{cw.speed}")
            statusline()


def readpreferences():
    """
    Restore preferences if they exist, otherwise create some sane defaults.
    """
    global preference, cat_control, look_up, cw
    logging.debug("")
    try:
        if os.path.exists("./fd_preferences.json"):
            with open(
                "./fd_preferences.json", "rt", encoding="utf-8"
            ) as file_descriptor:
                preference = loads(file_descriptor.read())
                logging.info("%s", preference)
                preference["mycall"] = preference["mycall"].upper()
                preference["myclass"] = preference["myclass"].upper()
                preference["mysection"] = preference["mysection"].upper()
        else:
            writepreferences()

    except IOError as exception:
        logging.critical("%s", exception)
    logging.info(preference)
    cat_control = None
    cw = None
    look_up = None
    try:

        if preference["useflrig"]:
            cat_control = CAT("flrig", preference["CAT_ip"], preference["CAT_port"])
        if preference["userigctld"]:
            cat_control = CAT("rigctld", preference["CAT_ip"], preference["CAT_port"])

        if preference["cwtype"]:
            cw = CW(preference["cwtype"], preference["CW_IP"], preference["CW_port"])
            cw.speed = 20
            if preference["cwtype"] == 1:
                cw.sendcw("\x1b220")

        if preference["useqrz"]:
            look_up = QRZlookup(
                preference["lookupusername"], preference["lookuppassword"]
            )

        if preference["usehamdb"]:
            look_up = HamDBlookup()

        if preference["usehamqth"]:
            look_up = HamQTH(
                preference["lookupusername"],
                preference["lookuppassword"],
            )

        if look_up and preference["mycall"] != "CALL":
            _thethread = threading.Thread(
                target=lookupmygrid,
                daemon=True,
            )
            _thethread.start()
        cloudlogauth()
    except KeyError as err:
        logging.warning("Corrupt preference, %s, loading clean version.", err)
        preference = reference_preference.copy()
        with open("./fd_preferences.json", "wt", encoding="utf-8") as file_descriptor:
            file_descriptor.write(dumps(preference, indent=4))
            logging.info("writing: %s", preference)


def writepreferences():
    """
    Write preferences to json file.
    """
    try:
        logging.debug("")
        with open("./fd_preferences.json", "wt", encoding="utf-8") as file_descriptor:
            file_descriptor.write(dumps(preference, indent=4))
            logging.info("%s", preference)
    except IOError as exception:
        logging.critical("%s", exception)


def log_contact(logme):
    """Log a contact to the db"""
    db.log_contact(logme)
    workedSections()
    sections()
    stats()
    logwindow()
    postcloudlog()


# FIXME import from fdlogger gui
# def log_contact(self):
#     """Log the current contact"""
#     self.show_dirty_records()
#     if (
#         len(self.callsign_entry.text()) == 0
#         or len(self.class_entry.text()) == 0
#         or len(self.section_entry.text()) == 0
#     ):
#         return
#     if not self.cat_control:
#         self.oldfreq = int(float(self.fakefreq(self.band, self.mode)) * 1000)
#     unique_id = uuid.uuid4().hex
#     contact = (
#         self.callsign_entry.text(),
#         self.class_entry.text(),
#         self.section_entry.text(),
#         self.oldfreq,
#         self.band,
#         self.mode,
#         int(self.power_selector.value()),
#         self.contactlookup["grid"],
#         self.contactlookup["name"],
#         unique_id,
#     )
#     self.db.log_contact(contact)

#     stale = datetime.now() + timedelta(seconds=30)
#     if self.connect_to_server:
#         contact = {
#             "cmd": "POST",
#             "hiscall": self.callsign_entry.text(),
#             "class": self.class_entry.text(),
#             "section": self.section_entry.text(),
#             "mode": self.mode,
#             "band": self.band,
#             "frequency": self.oldfreq,
#             "date_and_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
#             "power": int(self.power_selector.value()),
#             "grid": self.contactlookup["grid"],
#             "opname": self.contactlookup["name"],
#             "station": self.preference["mycall"],
#             "unique_id": unique_id,
#             "expire": stale.isoformat(),
#         }
#         self.server_commands.append(contact)
#         bytesToSend = bytes(dumps(contact), encoding="ascii")
#         try:
#             self.server_udp.sendto(
#                 bytesToSend, (self.multicast_group, int(self.multicast_port))
#             )
#         except OSError as err:
#             logging.warning("%s", err)

#     self.sections()
#     self.stats()
#     self.updatemarker()
#     self.logwindow()
#     self.clearinputs()
#     self.postcloudlog()
#     self.clearcontactlookup()


def delete_contact(contact):
    """delete contact from db"""
    db.delete_contact(contact)
    workedSections()
    sections()
    stats()
    logwindow()


def change_contact(record):
    """Update contact in database"""
    db.change_contact(record)


def read_sections():
    """
    Reads in the ARRL sections into some internal dictionaries.
    """
    try:
        with open(
            relpath("./data/arrl_sect.dat"), "r", encoding="utf-8"
        ) as file_descriptor:
            while 1:
                line = file_descriptor.readline().strip()  # read a line and put in db
                if not line:
                    break
                if line[0] == "#":
                    continue
                try:
                    _, state, canum, abbrev, name = str.split(line, None, 4)
                    secName[abbrev] = abbrev + " " + name + " " + canum
                    secState[abbrev] = state
                    for i in range(len(abbrev) - 1):
                        partial = abbrev[: -i - 1]
                        secPartial[partial] = 1
                except ValueError as exception:
                    logging.warning("%s", exception)
    except IOError as exception:
        logging.critical("read error: %s", exception)


def section_check(sec):
    """Section check partial"""
    y, x = stdscr.getyx()
    if sec == "":
        sec = "^"
    seccheckwindow = curses.newpad(20, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    snkeys = list(secName.keys())
    xx = list(filter(lambda y: y.startswith(sec), snkeys))
    count = 0
    for xxx in xx:
        seccheckwindow.addstr(count, 1, secName[xxx])
        count += 1
    stdscr.refresh()
    seccheckwindow.refresh(0, 0, 12, 1, 20, 33)
    stdscr.move(y, x)


def readSCP():
    """read section check partial file"""
    global scp
    f = open(relpath("./data/MASTER.SCP"), "r", encoding="utf-8")
    scp = f.readlines()
    f.close()
    scp = list(map(lambda x: x.strip(), scp))


def super_check(acall):
    """Supercheck partial"""
    return list(filter(lambda x: x.startswith(acall), scp))


def dcontacts():
    """I don't remember what this does... This is why commenting code is important."""
    rectangle(stdscr, 0, 0, 7, 55)
    contactslabel = "Recent Contacts"
    contactslabeloffset = (55 / 2) - len(contactslabel) / 2
    stdscr.addstr(0, int(contactslabeloffset), contactslabel)


def contacts_label():
    """
    Centers a string to create a label for the Recent contacts window.
    Seems stupid but it's used like 4 times.
    """
    rectangle(stdscr, 0, 0, 7, 55)
    contactslabel = "Recent Contacts"
    contactslabeloffset = (55 / 2) - len(contactslabel) / 2
    stdscr.addstr(0, int(contactslabeloffset), contactslabel)


def stats():
    """Calculates and displays stats."""
    y, x = stdscr.getyx()
    (
        cwcontacts,
        phonecontacts,
        digitalcontacts,
        _,
        last15,
        lasthour,
        _,
        _,
    ) = db.stats()
    rectangle(stdscr, 0, 57, 7, 79)
    statslabel = "Score Stats"
    statslabeloffset = (25 / 2) - len(statslabel) / 2
    stdscr.addstr(0, 57 + int(statslabeloffset), statslabel)
    stdscr.addstr(1, 58, "Total CW:")
    stdscr.addstr(2, 58, "Total PHONE:")
    stdscr.addstr(3, 58, "Total DIGITAL:")
    stdscr.addstr(4, 58, "QSO POINTS:          ")
    stdscr.addstr(5, 58, "QSOs LAST HOUR:")
    stdscr.addstr(6, 58, "QSOs LAST 15MIN:")
    stdscr.addstr(1, 75, cwcontacts.rjust(4))
    stdscr.addstr(2, 75, phonecontacts.rjust(4))
    stdscr.addstr(3, 75, digitalcontacts.rjust(4))
    stdscr.addstr(4, 70, str(score()).rjust(9))
    stdscr.addstr(5, 76, lasthour.rjust(3))
    stdscr.addstr(6, 76, last15.rjust(3))
    stdscr.move(y, x)


def score():
    """Calculates the score"""
    global qrp
    qrp, _ = db.qrp_check()
    cdub, ph, di = db.contacts_under_101watts()
    the_score = (int(cdub) * 2) + int(ph) + (int(di) * 2)
    multiplier = 2
    if qrp and bool(preference["altpower"]):
        multiplier = 5
    return the_score * multiplier


def getBandModeTally(the_band, the_mode):
    """Returns the count and power of all contacts used on a band using one mode"""
    return db.get_band_mode_tally(the_band, the_mode)


def getbands():
    """Returns a list of bands used"""
    bandlist = []
    x = db.get_bands()
    if x:
        for count in x:
            bandlist.append(count[0])
        return bandlist
    return []


def generateBandModeTally():
    """Creates a file with a breakdown of bands, modes and power used."""
    blist = getbands()
    bmtfn = "Statistics.txt"
    with open(bmtfn, "w", encoding="UTF-8") as file_descriptor:
        print("\t\tCW\tPWR\tDI\tPWR\tPH\tPWR", end="\r\n", file=file_descriptor)
        print("-" * 60, end="\r\n", file=file_descriptor)
        for b in bands:
            if b in blist:
                cwt = getBandModeTally(b, "CW")
                dit = getBandModeTally(b, "DI")
                pht = getBandModeTally(b, "PH")
                print(
                    f"Band:\t{b}\t{cwt[0]}\t{cwt[1]}\t{dit[0]}\t{dit[1]}\t{pht[0]}\t{pht[1]}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print("-" * 60, end="\r\n", file=file_descriptor)


def getState(section):
    """Returns the state of a particular ARRL section"""
    try:
        state = secState[section]
        if state != "--":
            return state
    except IndexError:
        return False
    return False


def adif():
    """Generates an ADIF file"""
    logname = "FieldDay.adi"
    log = db.fetch_all_contacts_asc()
    grid = False
    with open(logname, "w", encoding="UTF-8") as file_descriptor:
        print("<ADIF_VER:5>2.2.0", end="\r\n", file=file_descriptor)
        print("<EOH>", end="\r\n", file=file_descriptor)
        for contact in log:
            (
                _,
                opcall,
                opclass,
                opsection,
                the_datetime,
                the_band,
                the_mode,
                _,
                grid,
                name,
            ) = contact
            if the_mode == "DI":
                the_mode = "FT8"
            if the_mode == "PH":
                the_mode = "SSB"
            if the_mode == "CW":
                rst = "599"
            else:
                rst = "59"
            loggeddate = the_datetime[:10]
            loggedtime = the_datetime[11:13] + the_datetime[14:16]
            print(
                f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>"
                f"{''.join(loggeddate.split('-'))}",
                end="\r\n",
                file=file_descriptor,
            )
            print(
                f"<TIME_ON:{len(loggedtime)}>{loggedtime}",
                end="\r\n",
                file=file_descriptor,
            )
            print(f"<CALL:{len(opcall)}>{opcall}", end="\r\n", file=file_descriptor)
            print(f"<MODE:{len(the_mode)}>{the_mode}", end="\r\n", file=file_descriptor)
            print(
                f"<BAND:{len(the_band + 'M')}>{the_band}M",
                end="\r\n",
                file=file_descriptor,
            )
            print(
                f"<FREQ:{len(dfreq[the_band])}>{dfreq[the_band]}",
                end="\r\n",
                file=file_descriptor,
            )
            print(f"<RST_SENT:{len(rst)}>{rst}", end="\r\n", file=file_descriptor)
            print(f"<RST_RCVD:{len(rst)}>{rst}", end="\r\n", file=file_descriptor)
            print(
                f"<STX_STRING:{len(preference['myclass'] + ' ' + preference['mysection'])}>"
                f"{preference['myclass']} {preference['mysection']}",
                end="\r\n",
                file=file_descriptor,
            )
            print(
                f"<SRX_STRING:{len(opclass + ' ' + opsection)}>{opclass} {opsection}",
                end="\r\n",
                file=file_descriptor,
            )
            print(
                f"<ARRL_SECT:{len(opsection)}>{opsection}",
                end="\r\n",
                file=file_descriptor,
            )
            print(
                f"<CLASS:{len(opclass)}>{opclass}",
                end="\r\n",
                file=file_descriptor,
            )
            state = getState(opsection)
            if state:
                print(f"<STATE:{len(state)}>{state}", end="\r\n", file=file_descriptor)
            if grid and grid != "NOT_FOUND":
                print(
                    f"<GRIDSQUARE:{len(grid)}>{grid}",
                    end="\r\n",
                    file=file_descriptor,
                )
            if name and name != "NOT_FOUND":
                print(f"<NAME:{len(name)}>{name}", end="\r\n", file=file_descriptor)
            print("<COMMENT:14>ARRL-FIELD-DAY", end="\r\n", file=file_descriptor)
            print("<EOR>", end="\r\n", file=file_descriptor)
            print("", end="\r\n", file=file_descriptor)
    yy, xx = stdscr.getyx()
    stdscr.move(15, 1)
    stdscr.addstr("Done.                     ")
    stdscr.move(yy, xx)
    stdscr.refresh()


def postcloudlog():
    """posts a contacts to cloudlog."""
    if not preference["cloudlogapi"] or not cloudlogauthenticated:
        return
    (
        _,
        opcall,
        opclass,
        opsection,
        the_datetime,
        the_band,
        the_mode,
        _,
        grid,
        name,
    ) = db.fetch_last_contact()
    if the_mode == "CW":
        rst = "599"
    else:
        rst = "59"
    loggeddate = the_datetime[:10]
    loggedtime = the_datetime[11:13] + datetime[14:16]
    adifq = (
        f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>"
        f"{''.join(loggeddate.split('-'))}"
        f"<TIME_ON:{len(loggedtime)}>{loggedtime}"
        f"<CALL:{len(opcall)}>{opcall}"
        f"<MODE:{len(the_mode)}>{the_mode}"
        f"<BAND:{len(the_band)+1}>{the_band}"
        f"<FREQ:{len(dfreq[the_band])}>{dfreq[the_band]}"
        f"<RST_SENT:{len(rst)}>{rst}"
        f"<RST_RCVD:{len(rst)}>{rst}"
        f"<STX_STRING:{len(preference['myclass']+preference['mysection'])+1}>"
        f"{preference['myclass']} {preference['mysection']}"
        f"<SRX_STRING:{len(opclass+opsection)+1}>{opclass} {opsection}"
        f"<ARRL_SECT:{len(opsection)}>{opsection}"
        f"<CLASS:{len(opclass)}>{opclass}"
    )
    state = getState(opsection)
    if state:
        adifq += f"<STATE:{len(state)}>{state}"
    if grid:
        adifq += f"<GRIDSQUARE:{len(grid)}>{grid}"
    if name:
        adifq += f"<NAME:{len(name)}>{name}"
    adifq += "<COMMENT:14>ARRL-FIELD-DAY" "<EOR>"

    payloadDict = {"key": preference["cloudlogapi"], "type": "adif", "string": adifq}
    jsonData = dumps(payloadDict)
    _ = requests.post(preference["cloudlogurl"], jsonData)


def cabrillo():
    """generates a cabrillo file"""
    logname = "FieldDay.log"
    log = db.fetch_all_contacts_asc()
    catpower = ""
    if qrp:
        catpower = "QRP"
    else:
        catpower = "LOW"
    with open(logname, "w", encoding="UTF-8") as file_descriptor:
        print("START-OF-LOG: 3.0", end="\r\n", file=file_descriptor)
        print(f"LOCATION: {preference['mysection']}", end="\r\n", file=file_descriptor)
        print(f"CALLSIGN: {preference['mycall']}", end="\r\n", file=file_descriptor)
        print("CONTEST: ARRL-FIELD-DAY", end="\r\n", file=file_descriptor)
        print("CLUB:", end="\r\n", file=file_descriptor)
        print(
            "CATEGORY-OPERATOR: SINGLE-OP\r\n"
            "CATEGORY-ASSISTED: NON-ASSISTED\r\n"
            "CATEGORY-BAND: ALL\r\n"
            "CATEGORY-MODE: MIXED\r\n"
            "CATEGORY-STATION: PORTABLE\r\n"
            "CATEGORY-TRANSMITTER: ONE",
            end="\r\n",
            file=file_descriptor,
        )
        print(f"CATEGORY-POWER: {catpower}", end="\r\n", file=file_descriptor)
        print(f"CLAIMED-SCORE: {score()}", end="\r\n", file=file_descriptor)
        print(f"OPERATORS: {preference['mycall']}", end="\r\n", file=file_descriptor)
        print("NAME: ", end="\r\n", file=file_descriptor)
        print("ADDRESS: ", end="\r\n", file=file_descriptor)
        print("ADDRESS-CITY: ", end="\r\n", file=file_descriptor)
        print("ADDRESS-STATE: ", end="\r\n", file=file_descriptor)
        print("ADDRESS-POSTALCODE: ", end="\r\n", file=file_descriptor)
        print("ADDRESS-COUNTRY: ", end="\r\n", file=file_descriptor)
        print("EMAIL: ", end="\r\n", file=file_descriptor)
        print("CREATED-BY: K6GTE Field Day Logger", end="\r\n", file=file_descriptor)
        for contact in log:
            (
                _,
                opcall,
                opclass,
                opsection,
                the_datetime,
                the_band,
                the_mode,
                _,
                _,
                _,
            ) = contact
            if the_mode == "DI":
                the_mode = "DG"
            loggeddate = the_datetime[:10]
            loggedtime = the_datetime[11:13] + the_datetime[14:16]
            print(
                f"QSO: {the_band.rjust(3)}M "
                f"{the_mode} "
                f"{loggeddate} "
                f"{loggedtime} "
                f"{preference['mycall'].ljust(14)} "
                f"{preference['myclass'].ljust(3)} "
                f"{preference['mysection'].ljust(5)} "
                f"{opcall.ljust(14)} "
                f"{opclass.ljust(3)} "
                f"{opsection}",
                end="\r\n",
                file=file_descriptor,
            )
        print("END-OF-LOG:", end="\r\n", file=file_descriptor)

    generateBandModeTally()

    oy, ox = stdscr.getyx()
    window = curses.newpad(10, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    window.addstr(0, 0, f"Log written to: {logname}")
    window.addstr(1, 0, "Stats written to: Statistics.txt")
    window.addstr(2, 0, "Writing ADIF to: FieldDay.adi")
    stdscr.refresh()
    window.refresh(0, 0, 12, 1, 20, 33)
    stdscr.move(oy, ox)
    adif()
    writepreferences()
    statusline()
    stats()


def logwindow():
    """Updates the logwindow with contacts in DB"""
    global contacts, contactsOffset, logNumber
    contactsOffset = 0  # clears scroll position
    callfiller = "          "
    classfiller = "   "
    sectfiller = "   "
    modefiller = "  "
    zerofiller = "000"
    contacts = curses.newpad(1000, 80)
    log = db.fetch_all_contacts_desc()
    for logNumber, x in enumerate(log):
        (
            logid,
            opcall,
            opclass,
            opsection,
            the_datetime,
            the_band,
            the_mode,
            the_power,
            _,
            _,
        ) = x
        logid = zerofiller[: -len(str(logid))] + str(logid)
        opcall = opcall + callfiller[: -len(opcall)]
        opclass = opclass + classfiller[: -len(opclass)]
        opsection = opsection + sectfiller[: -len(opsection)]
        the_band = the_band + sectfiller[: -len(the_band)]
        the_mode = the_mode + modefiller[: -len(the_mode)]
        logline = (
            f"{logid} {opcall} {opclass} {opsection} {the_datetime} "
            f"{the_band} {the_mode} {the_power}"
        )
        contacts.addstr(logNumber, 0, logline)
    stdscr.refresh()
    contacts.refresh(0, 0, 1, 1, 6, 54)


def logup():
    """moves the log up one line"""
    global contactsOffset
    contactsOffset += 1
    if contactsOffset > (logNumber - 6):
        contactsOffset = logNumber - 6
    contacts.refresh(contactsOffset, 0, 1, 1, 6, 54)


def logpagedown():
    """moves the log down one page"""
    global contactsOffset
    contactsOffset += 10
    if contactsOffset > (logNumber - 6):
        contactsOffset = logNumber - 6
    contacts.refresh(contactsOffset, 0, 1, 1, 6, 54)


def logpageup():
    """moves the log up one page"""
    global contactsOffset
    contactsOffset -= 10
    if contactsOffset < 0:
        contactsOffset = 0
    contacts.refresh(contactsOffset, 0, 1, 1, 6, 54)


def logdown():
    """moves the log down one line"""
    global contactsOffset
    contactsOffset -= 1
    contactsOffset = max(contactsOffset, 0)
    contacts.refresh(contactsOffset, 0, 1, 1, 6, 54)


def dupCheck(acall):
    """checks for duplicates"""
    global hisclass, hissection
    oy, ox = stdscr.getyx()
    scpwindow = curses.newpad(1000, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    log = db.dup_check(acall)
    for counter, contact in enumerate(log):
        decorate = ""
        hiscallsign, hisclass, hissection, hisband, hismode = contact
        if hissection_field.text() == "":
            hissection_field.set_text(hissection)
            hissection_field.get_focus()
        if hisclass_field.text() == "":
            hisclass_field.set_text(hisclass)
            hisclass_field.get_focus()
        if hisband == band and hismode == mode:
            decorate = curses.color_pair(1)
            curses.flash()
            curses.beep()
        else:
            decorate = curses.A_NORMAL
        scpwindow.addstr(counter, 0, f"{hiscallsign}: {hisband} {hismode}", decorate)
    stdscr.refresh()
    scpwindow.refresh(0, 0, 12, 1, 20, 33)
    stdscr.move(oy, ox)


def displaySCP(matches):
    """displays section check partial results"""
    oy, ox = stdscr.getyx()
    scpwindow = curses.newpad(1000, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    for x in matches:
        wy, wx = scpwindow.getyx()
        if (33 - wx) < len(str(x)):
            scpwindow.move(wy + 1, 0)
        scpwindow.addstr(f"{x} ")
    stdscr.refresh()
    scpwindow.refresh(0, 0, 12, 1, 20, 33)
    stdscr.move(oy, ox)


def workedSections():
    """finds all sections worked"""
    global wrkdsections
    all_rows = db.sections()
    wrkdsections = str(all_rows)
    wrkdsections = (
        wrkdsections.replace("('", "")
        .replace("',), ", ",")
        .replace("',)]", "")
        .replace("[", "")
        .split(",")
    )


def workedSection(section):
    """displays all sections worked"""
    if section in wrkdsections:
        return curses.color_pair(1)
    return curses.A_DIM


def sectionsCol1():
    """Display sections in column 1"""
    rectangle(stdscr, 8, 35, 21, 43)
    stdscr.addstr(8, 36, "   DX  ", curses.A_REVERSE)
    stdscr.addstr(9, 36, "   DX  ", workedSection("DX"))
    stdscr.addstr(10, 36, "   1   ", curses.A_REVERSE)
    stdscr.addstr(11, 36, "CT", workedSection("CT"))
    stdscr.addstr(11, 41, "RI", workedSection("RI"))
    stdscr.addstr(12, 36, "EMA", workedSection("EMA"))
    stdscr.addstr(12, 41, "VT", workedSection("VT"))
    stdscr.addstr(13, 36, "ME", workedSection("ME"))
    stdscr.addstr(13, 40, "WMA", workedSection("WMA"))
    stdscr.addstr(14, 36, "NH", workedSection("NH"))
    stdscr.addstr(15, 36, "   2   ", curses.A_REVERSE)
    stdscr.addstr(16, 36, "ENY", workedSection("ENY"))
    stdscr.addstr(16, 40, "NNY", workedSection("NNY"))
    stdscr.addstr(17, 36, "NLI", workedSection("NLI"))
    stdscr.addstr(17, 40, "SNJ", workedSection("SNJ"))
    stdscr.addstr(18, 36, "NNJ", workedSection("NNJ"))
    stdscr.addstr(18, 40, "WNY", workedSection("WNY"))


def sectionsCol2():
    """Display sections in column 2"""
    rectangle(stdscr, 8, 44, 21, 52)
    stdscr.addstr(8, 45, "   3   ", curses.A_REVERSE)
    stdscr.addstr(9, 45, "DE", workedSection("DE"))
    stdscr.addstr(9, 49, "MDC", workedSection("MDC"))
    stdscr.addstr(10, 45, "EPA", workedSection("EPA"))
    stdscr.addstr(10, 49, "WPA", workedSection("WPA"))
    stdscr.addstr(11, 45, "   4   ", curses.A_REVERSE)
    stdscr.addstr(12, 45, "AL", workedSection("AL"))
    stdscr.addstr(12, 50, "SC", workedSection("SC"))
    stdscr.addstr(13, 45, "GA", workedSection("GA"))
    stdscr.addstr(13, 49, "SFL", workedSection("SFL"))
    stdscr.addstr(14, 45, "KY", workedSection("KY"))
    stdscr.addstr(14, 50, "TN", workedSection("TN"))
    stdscr.addstr(15, 45, "NC", workedSection("NC"))
    stdscr.addstr(15, 50, "VA", workedSection("VA"))
    stdscr.addstr(16, 45, "NFL", workedSection("NFL"))
    stdscr.addstr(16, 50, "VI", workedSection("VI"))
    stdscr.addstr(17, 45, "PR", workedSection("PR"))
    stdscr.addstr(17, 49, "WCF", workedSection("WCF"))


def sectionsCol3():
    """Display sections in column 3"""
    rectangle(stdscr, 8, 53, 21, 61)
    stdscr.addstr(8, 54, "   5   ", curses.A_REVERSE)
    stdscr.addstr(9, 54, "AR", workedSection("AR"))
    stdscr.addstr(9, 58, "NTX", workedSection("NTX"))
    stdscr.addstr(10, 54, "LA", workedSection("LA"))
    stdscr.addstr(10, 59, "OK", workedSection("OK"))
    stdscr.addstr(11, 54, "MS", workedSection("MS"))
    stdscr.addstr(11, 58, "STX", workedSection("STX"))
    stdscr.addstr(12, 54, "NM", workedSection("NM"))
    stdscr.addstr(12, 58, "WTX", workedSection("WTX"))
    stdscr.addstr(13, 54, "   6   ", curses.A_REVERSE)
    stdscr.addstr(14, 54, "EB", workedSection("EB"))
    stdscr.addstr(14, 58, "SCV", workedSection("SCV"))
    stdscr.addstr(15, 54, "LAX", workedSection("LAX"))
    stdscr.addstr(15, 58, "SDG", workedSection("SDG"))
    stdscr.addstr(16, 54, "ORG", workedSection("ORG"))
    stdscr.addstr(16, 59, "SF", workedSection("SF"))
    stdscr.addstr(17, 54, "PAC", workedSection("PAC"))
    stdscr.addstr(17, 58, "SJV", workedSection("SJV"))
    stdscr.addstr(18, 54, "SB", workedSection("SB"))
    stdscr.addstr(18, 59, "SV", workedSection("SV"))


def sectionsCol4():
    """Display sections in column 4"""
    rectangle(stdscr, 8, 62, 21, 70)
    stdscr.addstr(8, 63, "   7   ", curses.A_REVERSE)
    stdscr.addstr(9, 63, "AK", workedSection("AK"))
    stdscr.addstr(9, 68, "NV", workedSection("NV"))
    stdscr.addstr(10, 63, "AZ", workedSection("AZ"))
    stdscr.addstr(10, 68, "OR", workedSection("OR"))
    stdscr.addstr(11, 63, "EWA", workedSection("EWA"))
    stdscr.addstr(11, 68, "UT", workedSection("UT"))
    stdscr.addstr(12, 63, "ID", workedSection("ID"))
    stdscr.addstr(12, 67, "WWA", workedSection("WWA"))
    stdscr.addstr(13, 63, "MT", workedSection("MT"))
    stdscr.addstr(13, 68, "WY", workedSection("WY"))
    stdscr.addstr(14, 63, "   8   ", curses.A_REVERSE)
    stdscr.addstr(15, 63, "MI", workedSection("MI"))
    stdscr.addstr(15, 68, "WV", workedSection("WV"))
    stdscr.addstr(16, 63, "OH", workedSection("OH"))
    stdscr.addstr(17, 63, "   9   ", curses.A_REVERSE)
    stdscr.addstr(18, 63, "IL", workedSection("IL"))
    stdscr.addstr(18, 68, "WI", workedSection("WI"))
    stdscr.addstr(19, 63, "IN", workedSection("IN"))


def sectionsCol5():
    """Display sections in column 5"""
    rectangle(stdscr, 8, 71, 21, 79)
    stdscr.addstr(8, 72, "   0   ", curses.A_REVERSE)
    stdscr.addstr(9, 72, "CO", workedSection("CO"))
    stdscr.addstr(9, 77, "MO", workedSection("MO"))
    stdscr.addstr(10, 72, "IA", workedSection("IA"))
    stdscr.addstr(10, 77, "ND", workedSection("ND"))
    stdscr.addstr(11, 72, "KS", workedSection("KS"))
    stdscr.addstr(11, 77, "NE", workedSection("NE"))
    stdscr.addstr(12, 72, "MN", workedSection("MN"))
    stdscr.addstr(12, 77, "SD", workedSection("SD"))
    stdscr.addstr(13, 72, "CANADA ", curses.A_REVERSE)
    stdscr.addstr(14, 72, "AB", workedSection("AB"))
    stdscr.addstr(14, 77, "NT", workedSection("NT"))
    stdscr.addstr(15, 72, "BC", workedSection("BC"))
    stdscr.addstr(15, 76, "ONE", workedSection("ONE"))
    stdscr.addstr(16, 72, "GTA", workedSection("GTA"))
    stdscr.addstr(16, 76, "ONN", workedSection("ONN"))
    stdscr.addstr(17, 72, "MAR", workedSection("MAR"))
    stdscr.addstr(17, 76, "ONS", workedSection("ONS"))
    stdscr.addstr(18, 72, "MB", workedSection("MB"))
    stdscr.addstr(18, 77, "QC", workedSection("QC"))
    stdscr.addstr(19, 72, "NL", workedSection("NL"))
    stdscr.addstr(19, 77, "SK", workedSection("SK"))
    stdscr.addstr(20, 72, "PE", workedSection("PE"))


def sections():
    """Check sections worked and display them"""
    workedSections()
    sectionsCol1()
    sectionsCol2()
    sectionsCol3()
    sectionsCol4()
    sectionsCol5()
    stdscr.refresh()


def entry():
    """show text entry fields"""
    rectangle(stdscr, 8, 0, 10, 18)
    stdscr.addstr(8, 1, "CALL")
    rectangle(stdscr, 8, 19, 10, 25)
    stdscr.addstr(8, 20, "Class")
    rectangle(stdscr, 8, 26, 10, 34)
    stdscr.addstr(8, 27, "Section")


def clearentry():
    """Clear text entry fields"""
    global inputFieldFocus, hiscall, hissection, hisclass
    logging.debug("")
    hiscall = ""
    hissection = ""
    hisclass = ""
    stdscr.addstr(9, 15, "  ")
    # stdscr.refresh()
    inputFieldFocus = 0
    hissection_field.set_text("")
    hissection_field.get_focus()
    hisclass_field.set_text("")
    hisclass_field.get_focus()
    hiscall_field.set_text("")
    hiscall_field.get_focus()
    clearcontactlookup()


def highlightBonus(bonus):
    """Returns 'dim' or highlighted color pair."""
    if bonus:
        return curses.color_pair(1)
    return curses.A_DIM


def setStatusMsg(msg):
    """displays a status message"""
    oy, ox = stdscr.getyx()
    window = curses.newpad(10, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    window.addstr(0, 0, str(msg))
    stdscr.refresh()
    window.refresh(0, 0, 12, 1, 20, 33)
    stdscr.move(oy, ox)


def statusline():
    """shows status line at bottom of screen"""
    y, x = stdscr.getyx()
    stdscr.addstr(22, 1, f"v{__version__}")
    now = datetime.now().isoformat(" ")[5:19].replace("-", "/")
    utcnow = datetime.utcnow().isoformat(" ")[5:19].replace("-", "/")
    try:
        stdscr.addstr(22, 59, f"Local: {now}")
        stdscr.addstr(23, 61, f"UTC: {utcnow}")
    except curses.error as err:
        if err != "addwstr() returned ERR":
            pass
            # logging.debug("statusline: %s", err)

    stdscr.addstr(23, 1, "Band:        Mode:")
    stdscr.addstr(23, 7, f"  {band}  ", curses.A_REVERSE)
    if cw is not None:
        if cw.servertype == 1 and mode == "CW":
            stdscr.addstr(23, 20, f"{mode} {cw.speed} ", curses.A_REVERSE)
        else:
            stdscr.addstr(23, 20, f"  {mode}  ", curses.A_REVERSE)
    else:
        stdscr.addstr(23, 20, f"  {mode}  ", curses.A_REVERSE)
    stdscr.addstr(23, 27, "                            ")
    stdscr.addstr(
        23,
        27,
        f" {preference['mycall']}|"
        f"{preference['myclass']}|"
        f"{preference['mysection']}|"
        f"{preference['power']}w ",
        curses.A_REVERSE,
    )
    if rigonline is None:
        stdscr.addstr(23, 58, "  ")
    if rigonline is True:
        stdscr.addstr(23, 58, "📻")
    if rigonline is False:
        stdscr.addstr(23, 58, "💢")

    if look_up:
        if look_up.session:
            stdscr.addstr(23, 55, "🌐")
        else:
            stdscr.addstr(23, 55, "🚫")
    else:
        stdscr.addstr(23, 55, "  ")
    stdscr.move(y, x)


def setpower(p):
    """Change power in watts and save as a preference"""
    preference["power"] = p
    writepreferences()
    statusline()


def setband(b):
    """Sets current band for logging."""
    global band
    band = b
    statusline()


def setmode(m):
    """Sets current mode for logging."""
    global mode
    mode = m
    statusline()


def setcallsign(c):
    """Sets your callsign for logging and writes preference."""
    preference["mycall"] = str(c)
    if preference["mycall"] != "":
        _thethread = threading.Thread(
            target=lookupmygrid,
            daemon=True,
        )
        _thethread.start()
    writepreferences()
    statusline()


def setclass(c):
    """Sets your class for logging and writes preference."""
    preference["myclass"] = str(c)
    writepreferences()
    statusline()


def setsection(s):
    """Stores your section for logging and writes preference."""
    preference["mysection"] = str(s)
    writepreferences()
    statusline()


def displayHelp():
    """Displays help screen"""
    wy, wx = stdscr.getyx()
    scpwindow = curses.newpad(9, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    ######################################
    help_message = [
        ".H display this message",
        ".S Settings screen",
        ".Q quit the program",
        ".E# edit a QSO",
        ".D# delete a QSO",
        ".B# change operating band",
        ".M[CW,PH,DI] operating mode",
        ".P## change logged power",
        ".L Generate Logs and stats",
    ]
    stdscr.move(12, 1)
    for count, x in enumerate(help_message):
        scpwindow.addstr(count, 1, x)
    stdscr.refresh()
    scpwindow.refresh(0, 0, 12, 1, 20, 33)
    stdscr.move(wy, wx)


def clearDisplayInfo():
    """erases the displayinfo area of the screen"""
    y, x = stdscr.getyx()
    for line in range(0, 9):
        stdscr.addstr(12 + line, 1, "                                 ")
    stdscr.move(y, x)
    stdscr.refresh()


def displayinfo(info, line=2):
    """It.. Well, displays a line of info..."""
    y, x = stdscr.getyx()
    stdscr.move(18 + line, 1)
    stdscr.addstr(str(info))
    stdscr.move(y, x)
    stdscr.refresh()


def processcommand(cmd):
    """Process a dot command"""
    global end_program, preference
    cmd = cmd[1:].upper()
    if cmd == "S":
        editsettings = SettingsScreen(preference)
        changes = editsettings.show()
        if changes:
            preference = changes
            writepreferences()
            readpreferences()
        stdscr.clear()
        contacts_label()
        logwindow()
        sections()
        stats()
        displayHelp()
        entry()
        stdscr.move(9, 1)
        return
    if cmd == "Q":  # Quit
        end_program = True
        return
    if cmd[:1] == "B":  # Change Band
        setband(cmd[1:])
        return
    if cmd[:1] == "M":  # Change Mode
        if cmd[1:] == "CW" or cmd[1:] == "PH" or cmd[1:] == "DI":
            setmode(cmd[1:])
        else:
            curses.flash()
            curses.beep()
        return
    if cmd[:1] == "P":  # Change Power
        setpower(cmd[1:])
        return
    if cmd[:1] == "D":  # Delete Contact
        delete_contact(cmd[1:])
        return
    if cmd[:1] == "E":  # Edit QSO
        editQSO(cmd[1:])
        return
    if cmd[:1] == "H":  # Print Help
        displayHelp()
        return
    if cmd[:1] == "K":  # Set your Call Sign
        setcallsign(cmd[1:])
        return
    if cmd[:1] == "C":  # Set your class
        setclass(cmd[1:])
        return
    if cmd[:1] == "S":  # Set your section
        setsection(cmd[1:])
        return
    if cmd[:1] == "L":  # Generate Cabrillo Log
        cabrillo()
        return
    curses.flash()
    curses.beep()


def proc_key(key):
    """Process raw key presses"""
    global inputFieldFocus, hiscall, hissection, hisclass  # Globals bad m-kay
    input_field = [hiscall_field, hisclass_field, hissection_field]
    if key == Escape:
        clearentry()
        clearDisplayInfo()
        if cw is not None:  # abort cw output
            if cw.servertype == 1:
                cw.sendcw("\x1b4")
        return
    if key == 9 or key == Space:
        inputFieldFocus += 1
        if inputFieldFocus > 2:
            inputFieldFocus = 0
        if inputFieldFocus == 0:
            hissection = hissection_field.text()  # store any input to previous field
            hiscall_field.get_focus()
        if inputFieldFocus == 1:
            logging.debug(
                "checking for dupe and grid %s - %s", hiscall, hiscall_field.text()
            )
            if hiscall != hiscall_field.text():
                if len(hiscall_field.text()) > 2 and hiscall_field.text()[:1] != ".":
                    dupCheck(hiscall_field.text())
                    if look_up:
                        if not look_up.session:
                            look_up.getsession()
                        if look_up.session:
                            logging.debug("Call the lazy")
                            x = threading.Thread(
                                target=lazy_lookup,
                                args=(hiscall_field.text(),),
                                daemon=True,
                            )
                            x.start()
                hiscall = hiscall_field.text()
            hisclass_field.get_focus()
        if inputFieldFocus == 2:
            hisclass = hisclass_field.text()
            hissection_field.get_focus()
        return
    if key == EnterKey:
        if inputFieldFocus == 0:
            hiscall = hiscall_field.text()
        elif inputFieldFocus == 1:
            hisclass = hisclass_field.text()
        elif inputFieldFocus == 2:
            hissection = hissection_field.text()
        if hiscall[:1] == ".":  # process command
            clearDisplayInfo()
            processcommand(hiscall)
            clearentry()
            return
        if hiscall == "" or hisclass == "" or hissection == "":
            return
        isCall = re.compile(
            "^(([0-9])?[A-z]{1,2}[0-9]/)?[A-Za-z]{1,2}[0-9]{1,3}[A-Za-z]{1,4}(/[A-Za-z0-9]{1,3})?$"
        )
        if re.match(isCall, hiscall):
            contact = (
                hiscall,
                hisclass,
                hissection,
                band,
                mode,
                int(preference["power"]),
                contactlookup["grid"],
                contactlookup["name"],
            )
            clearDisplayInfo()
            log_contact(contact)
            clearentry()
        else:
            setStatusMsg("Must be valid call sign")
        return
    if key == curses.KEY_DOWN:  # key down
        logup()
        return
    if key == curses.KEY_UP:  # key up
        logdown()
        return
    if key == 338:  # page down
        logpagedown()
        return
    if key == 339:  # page up
        logpageup()
        return
    input_field[inputFieldFocus].getchar(key)
    if inputFieldFocus == 0 and len(hiscall_field.text()) > 2:
        displaySCP(super_check(hiscall_field.text()))
    if inputFieldFocus == 2:
        section_check(hissection_field.text())
    check_function_keys(key)


def edit_key(key):
    """Process weird keys, esc, backspace, enter etc"""
    global editFieldFocus, end_program
    if key == 9:
        editFieldFocus += 1
        if editFieldFocus > 8:
            editFieldFocus = 1
        qso_edit_fields[editFieldFocus - 1].get_focus()
        return
    if key == EnterKey:
        qso[1] = qso_edit_fields[0].text()
        qso[2] = qso_edit_fields[1].text()
        qso[3] = qso_edit_fields[2].text()
        qso[4] = f"{qso_edit_fields[3].text()} {qso_edit_fields[4].text()}"
        qso[5] = qso_edit_fields[5].text()
        qso[6] = qso_edit_fields[6].text()
        qso[7] = qso_edit_fields[7].text()
        change_contact(qso)
        qsoew.erase()
        stdscr.clear()
        contacts_label()
        logwindow()
        sections()
        stats()
        displayHelp()
        entry()
        stdscr.move(9, 1)
        end_program = True
        return
    if key == Escape:
        qsoew.erase()
        stdscr.clear()
        contacts_label()
        logwindow()
        sections()
        stats()
        displayHelp()
        entry()
        stdscr.move(9, 1)
        end_program = True
        return
    if key == 258:  # arrow down
        editFieldFocus += 1
        if editFieldFocus > 8:
            editFieldFocus = 1
        qso_edit_fields[editFieldFocus - 1].get_focus()
        return
    if key in (259, 353):  # arrow up
        editFieldFocus -= 1
        if editFieldFocus < 1:
            editFieldFocus = 7
        qso_edit_fields[editFieldFocus - 1].get_focus()
        return
    qso_edit_fields[editFieldFocus - 1].getchar(key)


def displayEditField(field):
    """I Guess it displays the edit field...."""
    filler = "                 "
    if field == 1:
        filler = "                 "
    elif field == 2:
        filler = "     "
    elif field == 3:
        filler = "       "
    qsoew.move(field, 10)
    if qso[field] == "":
        qsoew.addstr(filler)
    else:
        line = qso[field] + filler[: -len(qso[field])]
        qsoew.addstr(line.upper())
    qsoew.move(field, len(qso[field]) + 10)
    qsoew.refresh()


def EditClickedQSO(line):
    """Edit a qso clicked in the log window."""
    global qsoew, qso, end_program, qso_edit_fields, editFieldFocus
    editFieldFocus = 1
    record = (
        contacts.instr((line - 1) + contactsOffset, 0, 55)
        .decode("utf-8")
        .strip()
        .split()
    )
    if record == []:
        return
    qso = [
        record[0],
        record[1],
        record[2],
        record[3],
        record[4] + " " + record[5],
        record[6],
        record[7],
        record[8],
    ]
    qsoew = curses.newwin(10, 40, 6, 10)
    qsoew.keypad(True)
    qsoew.nodelay(True)
    qsoew.box()

    qso_edit_field_1 = EditTextField(qsoew, 1, 10, 14)
    qso_edit_field_2 = EditTextField(qsoew, 2, 10, 3)
    qso_edit_field_3 = EditTextField(qsoew, 3, 10, 3)
    qso_edit_field_4 = EditTextField(qsoew, 4, 10, 10)
    qso_edit_field_5 = EditTextField(qsoew, 4, 21, 8)
    qso_edit_field_6 = EditTextField(qsoew, 5, 10, 3)
    qso_edit_field_7 = EditTextField(qsoew, 6, 10, 2)
    qso_edit_field_8 = EditTextField(qsoew, 7, 10, 3)

    qso_edit_field_1.set_text(record[1])
    qso_edit_field_2.set_text(record[2])
    qso_edit_field_3.set_text(record[3])
    qso_edit_field_4.set_text(record[4])
    qso_edit_field_5.set_text(record[5])
    qso_edit_field_6.set_text(record[6])
    qso_edit_field_7.set_text(record[7])
    qso_edit_field_8.set_text(str(record[8]))

    qso_edit_fields = [
        qso_edit_field_1,
        qso_edit_field_2,
        qso_edit_field_3,
        qso_edit_field_4,
        qso_edit_field_5,
        qso_edit_field_6,
        qso_edit_field_7,
        qso_edit_field_8,
    ]

    qsoew.addstr(1, 1, "Call   : ")
    qsoew.addstr(2, 1, "Class  : ")
    qsoew.addstr(3, 1, "Section: ")
    qsoew.addstr(4, 1, "At     : ")
    qsoew.addstr(5, 1, "Band   : ")
    qsoew.addstr(6, 1, "Mode   : ")
    qsoew.addstr(7, 1, "Power  : ")
    qsoew.addstr(8, 1, "[Enter] to save          [Esc] to exit")

    for displayme in qso_edit_fields:
        displayme.get_focus()
    qso_edit_fields[0].get_focus()

    while 1:
        statusline()
        stdscr.refresh()
        qsoew.refresh()
        c = qsoew.getch()
        if c != -1:
            logging.debug("Key: %d", c)
            edit_key(c)
        else:
            time.sleep(0.01)
        if end_program:
            end_program = False
            break


def editQSO(q):
    """Edit contact"""
    if q is False or q == "":
        setStatusMsg("Must specify a contact number")
        return
    global qsoew, qso, end_program, qso_edit_fields, editFieldFocus
    log = db.contact_by_id(q)
    logging.info("record: %s, log: %s", q, log)
    if not log:
        return
    qso = ["", "", "", "", "", "", "", "", "", ""]
    qso[0], qso[1], qso[2], qso[3], qso[4], qso[5], qso[6], qso[7], qso[8], qso[9] = log
    qsoew = curses.newwin(10, 40, 6, 10)
    qsoew.keypad(True)
    qsoew.nodelay(True)
    qsoew.box()
    editFieldFocus = 1
    qso_edit_field_1 = EditTextField(qsoew, 1, 10, 14)
    qso_edit_field_2 = EditTextField(qsoew, 2, 10, 3)
    qso_edit_field_3 = EditTextField(qsoew, 3, 10, 3)
    qso_edit_field_4 = EditTextField(qsoew, 4, 10, 10)
    qso_edit_field_5 = EditTextField(qsoew, 4, 21, 8)
    qso_edit_field_6 = EditTextField(qsoew, 5, 10, 3)
    qso_edit_field_7 = EditTextField(qsoew, 6, 10, 2)
    qso_edit_field_8 = EditTextField(qsoew, 7, 10, 3)

    qso_edit_field_1.set_text(log[1])
    qso_edit_field_2.set_text(log[2])
    qso_edit_field_3.set_text(log[3])
    dt = log[4].split()
    qso_edit_field_4.set_text(dt[0])
    qso_edit_field_5.set_text(dt[1])
    qso_edit_field_6.set_text(log[5])
    qso_edit_field_7.set_text(log[6])
    qso_edit_field_8.set_text(str(log[7]))

    qso_edit_fields = [
        qso_edit_field_1,
        qso_edit_field_2,
        qso_edit_field_3,
        qso_edit_field_4,
        qso_edit_field_5,
        qso_edit_field_6,
        qso_edit_field_7,
        qso_edit_field_8,
    ]
    qsoew.addstr(1, 1, f"Call   : {qso[1]}")
    qsoew.addstr(2, 1, f"Class  : {qso[2]}")
    qsoew.addstr(3, 1, f"Section: {qso[3]}")
    qsoew.addstr(4, 1, f"At     : {qso[4]}")
    qsoew.addstr(5, 1, f"Band   : {qso[5]}")
    qsoew.addstr(6, 1, f"Mode   : {qso[6]}")
    qsoew.addstr(7, 1, f"Power  : {qso[7]}")
    qsoew.addstr(8, 1, "[Enter] to save          [Esc] to exit")

    for displayme in qso_edit_fields:
        displayme.get_focus()
    qso_edit_fields[0].get_focus()

    while 1:
        statusline()
        stdscr.refresh()
        qsoew.refresh()
        c = qsoew.getch()
        if c != -1:
            edit_key(c)
        else:
            time.sleep(0.01)
        if end_program:
            end_program = False
            break


def get_ft8_qso():
    """Monitor FT8 contacts"""
    while True:
        ft8qso = ft8_watcher.get_udp()
        if ft8qso:
            contact = (
                ft8qso[0],
                ft8qso[1],
                ft8qso[2],
                ft8qso[5],
                "DI",
                preference["power"],
                ft8qso[8],
                ft8qso[9],
            )
            log_contact(contact)
            clearentry()


def main(s):  # pylint: disable=unused-argument
    """Main entry point for the program"""
    read_sections()
    readSCP()
    read_cw_macros()
    curses.start_color()
    curses.use_default_colors()
    if curses.can_change_color():
        curses.init_color(curses.COLOR_MAGENTA, 1000, 640, 0)
        curses.init_color(curses.COLOR_BLACK, 0, 0, 0)
        curses.init_color(curses.COLOR_CYAN, 500, 500, 500)
        curses.init_pair(1, curses.COLOR_MAGENTA, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    stdscr.attrset(curses.color_pair(0))
    stdscr.clear()
    dcontacts()
    sections()
    entry()
    logwindow()
    readpreferences()
    if preference["mycall"].upper() == "CALL":
        processcommand(" S")
    stats()
    displayHelp()
    cloudlogauth()
    stdscr.refresh()
    stdscr.move(9, 1)

    # start the listener for FT8 udp packets
    _ft8thread = threading.Thread(
        target=get_ft8_qso,
        daemon=True,
    )
    _ft8thread.start()
    poll_time = datetime.now()
    while 1:
        stdscr.refresh()
        ch = stdscr.getch()
        if ch == curses.KEY_MOUSE:
            buttons = ""
            try:
                _, x, y, _, buttons = curses.getmouse()
                if buttons == 65536:
                    logdown()
                if buttons == 2097152:
                    logup()
                if buttons == 8 and 0 < y < 7 and 0 < x < 56:
                    EditClickedQSO(y)
            except curses.error:
                pass
        elif ch != -1:
            proc_key(ch)
        else:
            time.sleep(0.01)
        if end_program:
            break
        if datetime.now() > poll_time:
            statusline()
            poll_radio()
            poll_time = datetime.now() + timedelta(seconds=1)


wrapper(main)
