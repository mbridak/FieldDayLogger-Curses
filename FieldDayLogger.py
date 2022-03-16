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

# The next 3 lines prove I'm a bad person.
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=global-statement

import curses
import time
import sys
import os
import sqlite3
import socket
from pathlib import Path

from curses.textpad import rectangle
from curses import wrapper
from datetime import datetime

import logging
from json import loads, dumps
import requests
from cat_interface import CAT
from lookup import HamDBlookup, HamQTH, QRZlookup

if Path("./debug").exists():
    logging.basicConfig(
        filename="debug.log",
        filemode="w",
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG,
    )
    logging.debug("Debug started")
else:
    logging.basicConfig(level=logging.CRITICAL)

preference = {
    "mycall": "Call",
    "myclass": "Class",
    "mysection": "Section",
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
}


stdscr = curses.initscr()
height, width = stdscr.getmaxyx()
if height < 24 or width < 80:
    print("Terminal size needs to be at least 80x24")
    curses.endwin()
    sys.exit()
qsoew = 0
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

database = "FieldDay.db"

wrkdsections = []
scp = []
secPartial = {}
secName = {}
secState = {}
oldfreq = "0"
oldmode = ""
rigonline = False


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


def create_DB():
    """create a database and table if it does not exist"""
    try:
        with sqlite3.connect(database) as conn:
            cursor = conn.cursor()
            sql_table = (
                "CREATE TABLE IF NOT EXISTS contacts "
                "(id INTEGER PRIMARY KEY, "
                "callsign text NOT NULL, "
                "class text NOT NULL, "
                "section text NOT NULL, "
                "date_time text NOT NULL, "
                "band text NOT NULL, "
                "mode text NOT NULL, "
                "power INTEGER NOT NULL);"
            )
            cursor.execute(sql_table)
            conn.commit()
    except sqlite3.Error as err:
        print(err)


def readpreferences():
    """
    Restore preferences if they exist, otherwise create some sane defaults.
    """
    global preference, cat_control, look_up
    logging.info("readpreferences:")
    try:
        if os.path.exists("./fd_preferences.json"):
            with open(
                "./fd_preferences.json", "rt", encoding="utf-8"
            ) as file_descriptor:
                preference = loads(file_descriptor.read())
                logging.info("reading: %s", preference)
        else:
            writepreferences()
            curses.endwin()
            print(
                "\n\nA basic configuration file has been written to: ./fd_preferences.json"
            )
            print("Please edit this file and relaunch the program.\n\n")
            sys.exit()
    except IOError as exception:
        logging.critical("readpreferences: %s", exception)
    logging.info(preference)

    cat_control = None
    if preference["useflrig"]:
        cat_control = CAT("flrig", preference["CAT_ip"], preference["CAT_port"])
    if preference["userigctld"]:
        cat_control = CAT("rigctld", preference["CAT_ip"], preference["CAT_port"])

    if preference["useqrz"]:
        look_up = QRZlookup(preference["lookupusername"], preference["lookuppassword"])
        # self.callbook_icon.setText("QRZ")
        if look_up.session:
            pass
            # self.callbook_icon.setStyleSheet("color: rgb(128, 128, 0);")
        else:
            pass
            # self.callbook_icon.setStyleSheet("color: rgb(136, 138, 133);")

    if preference["usehamdb"]:
        look_up = HamDBlookup()
        # self.callbook_icon.setText("HamDB")
        # self.callbook_icon.setStyleSheet("color: rgb(128, 128, 0);")

    if preference["usehamqth"]:
        look_up = HamQTH(
            preference["lookupusername"],
            preference["lookuppassword"],
        )
        # self.callbook_icon.setText("HamQTH")
        if look_up.session:
            pass
            # self.callbook_icon.setStyleSheet("color: rgb(128, 128, 0);")
        else:
            pass
            # self.callbook_icon.setStyleSheet("color: rgb(136, 138, 133);")

    cloudlogauth()


def writepreferences():
    """
    Write preferences to json file.
    """
    try:
        logging.info("writepreferences:")
        with open("./fd_preferences.json", "wt", encoding="utf-8") as file_descriptor:
            file_descriptor.write(dumps(preference, indent=4))
            logging.info("writing: %s", preference)
    except IOError as exception:
        logging.critical("writepreferences: %s", exception)


def log_contact(logme):
    """Log a contact to the db"""
    try:
        with sqlite3.connect(database) as conn:
            sql = (
                "INSERT INTO contacts"
                "(callsign, class, section, date_time, band, mode, power) "
                "VALUES(?,?,?,datetime('now'),?,?,?)"
            )
            cur = conn.cursor()
            cur.execute(sql, logme)
            conn.commit()
    except sqlite3.Error as err:
        displayinfo(err)
    workedSections()
    sections()
    stats()
    logwindow()
    postcloudlog()


def delete_contact(contact):
    """delete contact from db"""
    try:
        with sqlite3.connect(database) as conn:
            sql = f"delete from contacts where id={contact}"
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
    except sqlite3.Error as err:
        displayinfo(err)
    workedSections()
    sections()
    stats()
    logwindow()


def change_contact(record):
    """Update contact in database"""
    with sqlite3.connect(database) as conn:
        sql = (
            "update contacts set "
            f"callsign = '{record[1]}', "
            f"class = '{record[2]}', "
            f"section = '{record[3]}', "
            f"date_time = '{record[4]}', "
            f"band = '{record[5]}', "
            f"mode = '{record[6]}', "
            f"power = '{record[7]}' "
            f"where id={record[0]}"
        )
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()


def read_sections():
    """
    Reads in the ARRL sections into some internal dictionaries.
    """
    try:
        with open(relpath("arrl_sect.dat"), "r", encoding="utf-8") as file_descriptor:
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
                    logging.warning("read_sections: %s", exception)
    except IOError as exception:
        logging.critical("read_sections: read error: %s", exception)


def sectionCheck(sec):
    """Section check partial"""
    if sec == "":
        sec = "^"
    seccheckwindow = curses.newpad(20, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    x = list(secName.keys())
    xx = list(filter(lambda y: y.startswith(sec), x))
    count = 0
    for xxx in xx:
        seccheckwindow.addstr(count, 1, secName[xxx])
        count += 1
    stdscr.refresh()
    seccheckwindow.refresh(0, 0, 12, 1, 20, 33)


def readSCP():
    """read section check partial file"""
    global scp
    f = open(relpath("MASTER.SCP"), "r", encoding="utf-8")
    scp = f.readlines()
    f.close()
    scp = list(map(lambda x: x.strip(), scp))


def superCheck(acall):
    """Supercheck partial"""
    return list(filter(lambda x: x.startswith(acall), scp))


def dcontacts():
    """I don't remember what this does... This is why commenting code is important."""
    rectangle(stdscr, 0, 0, 7, 55)
    contactslabel = "Recent Contacts"
    contactslabeloffset = (49 / 2) - len(contactslabel) / 2
    stdscr.addstr(0, int(contactslabeloffset), contactslabel)


def stats():
    """Calculates and displays stats."""
    y, x = stdscr.getyx()
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute("select count(*) from contacts where mode = 'CW'")
        cwcontacts = str(cursor.fetchone()[0])
        cursor.execute("select count(*) from contacts where mode = 'PH'")
        phonecontacts = str(cursor.fetchone()[0])
        cursor.execute("select count(*) from contacts where mode = 'DI'")
        digitalcontacts = str(cursor.fetchone()[0])
        cursor.execute(
            "SELECT count(*) FROM contacts where "
            "datetime(date_time) >=datetime('now', '-15 Minutes')"
        )
        last15 = str(cursor.fetchone()[0])
        cursor.execute(
            "SELECT count(*) FROM contacts where "
            "datetime(date_time) >=datetime('now', '-1 Hours')"
        )
        lasthour = str(cursor.fetchone()[0])
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
    # fixme
    # scoring has changed for 2022, 100W max PEP
    qrpcheck()
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "select count(*) as cw from contacts where mode = 'CW' and power < 101"
        )
        cw = str(cursor.fetchone()[0])
        cursor.execute(
            "select count(*) as ph from contacts where mode = 'PH' and power < 101"
        )
        ph = str(cursor.fetchone()[0])
        cursor.execute(
            "select count(*) as di from contacts where mode = 'DI' and power < 101"
        )
        di = str(cursor.fetchone()[0])
    the_score = (int(cw) * 2) + int(ph) + (int(di) * 2)
    multiplier = 2
    if qrp and bool(preference["altpower"]):
        multiplier = 5
    return the_score * multiplier


def qrpcheck():
    """checks if we are qrp"""
    global qrp
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("select count(*) as qrpc from contacts where mode = 'CW' and power > 5")
    log = c.fetchall()
    qrpc = list(log[0])[0]
    c.execute("select count(*) as qrpp from contacts where mode = 'PH' and power > 5")
    log = c.fetchall()
    qrpp = list(log[0])[0]
    c.execute("select count(*) as qrpd from contacts where mode = 'DI' and power > 5")
    log = c.fetchall()
    qrpd = list(log[0])[0]
    conn.close()
    qrp = not qrpc + qrpp + qrpd


def getBandModeTally(the_band, the_mode):
    """Returns the count and power of all contacts used on a band using one mode"""
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "select count(*) as tally, MAX(power) as mpow from contacts "
            f"where band = '{the_band}' AND mode ='{the_mode}'"
        )
        return cursor.fetchone()


def getbands():
    """Returns a list of bands used"""
    bandlist = []
    conn = ""
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("select DISTINCT band from contacts")
    x = c.fetchall()
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
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute("select * from contacts order by date_time ASC")
        log = cursor.fetchall()
    grid = False
    with open(logname, "w", encoding="UTF-8") as file_descriptor:
        print("<ADIF_VER:5>2.2.0", end="\r\n", file=file_descriptor)
        print("<EOH>", end="\r\n", file=file_descriptor)
        for counter, contact in enumerate(log):
            _, opcall, opclass, opsection, the_datetime, the_band, the_mode, _ = contact
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
            yy, xx = stdscr.getyx()
            stdscr.move(15, 1)
            stdscr.addstr(f"QRZ Gridsquare Lookup: {counter + 1}")
            stdscr.move(yy, xx)
            stdscr.refresh()
            grid, name = call_lookup(opcall)
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
            if grid:
                print(
                    f"<GRIDSQUARE:{len(grid)}>{grid}",
                    end="\r\n",
                    file=file_descriptor,
                )
            if name:
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
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute("select * from contacts order by id DESC")
        contact = cursor.fetchone()
    _, opcall, opclass, opsection, the_datetime, the_band, the_mode, _ = contact
    grid, name = call_lookup(opcall)
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
    # bonuses = 0
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "select * from contacts where power < 101 order by date_time ASC"
        )
        log = cursor.fetchall()
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
            _, opcall, opclass, opsection, the_datetime, the_band, the_mode, _ = contact
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
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("select * from contacts order by date_time desc")
    log = c.fetchall()
    conn.close()
    logNumber = 0
    for x in log:
        (
            logid,
            opcall,
            opclass,
            opsection,
            the_datetime,
            the_band,
            the_mode,
            the_power,
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
        logNumber += 1
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
    if contactsOffset < 0:
        contactsOffset = 0
    contacts.refresh(contactsOffset, 0, 1, 1, 6, 54)


def dupCheck(acall):
    """checks for duplicates"""
    oy, ox = stdscr.getyx()
    scpwindow = curses.newpad(1000, 33)
    rectangle(stdscr, 11, 0, 21, 34)

    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "select callsign, class, section, band, mode "
            f"from contacts where callsign like '{acall}' "
            "order by band"
        )
        log = cursor.fetchall()

    counter = 0
    for contact in log:
        decorate = ""
        hiscallsign, _, _, hisband, hismode = contact
        if hisband == band and hismode == mode:
            decorate = curses.color_pair(1)
            curses.flash()
            curses.beep()
        else:
            decorate = curses.A_NORMAL
        scpwindow.addstr(counter, 0, f"{hiscallsign}: {hisband} {hismode}", decorate)
        counter = counter + 1
    stdscr.refresh()
    scpwindow.refresh(0, 0, 12, 1, 20, 33)
    stdscr.move(oy, ox)


def displaySCP(matches):
    """displays section check partial results"""
    scpwindow = curses.newpad(1000, 33)
    rectangle(stdscr, 11, 0, 21, 34)
    for x in matches:
        wy, wx = scpwindow.getyx()
        if (33 - wx) < len(str(x)):
            scpwindow.move(wy + 1, 0)
        scpwindow.addstr(f"{x} ")
    stdscr.refresh()
    scpwindow.refresh(0, 0, 12, 1, 20, 33)


def workedSections():
    """finds all sections worked"""
    global wrkdsections
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("select distinct section from contacts")
    all_rows = c.fetchall()
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
    stdscr.addstr(8, 20, "class")
    rectangle(stdscr, 8, 26, 10, 34)
    stdscr.addstr(8, 27, "Section")


def clearentry():
    """Clear text entry fields"""
    global inputFieldFocus, hiscall, hissection, hisclass, kbuf
    hiscall = ""
    hissection = ""
    hisclass = ""
    kbuf = ""
    inputFieldFocus = 0
    displayInputField(2)
    displayInputField(1)
    displayInputField(0)


def highlightBonus(bonus):
    """Returns 'dim' or highlighted color pair."""
    if bonus:
        return curses.color_pair(1)
    return curses.A_DIM


def statusline():
    """shows status line at bottom of screen"""
    y, x = stdscr.getyx()
    now = datetime.now().isoformat(" ")[5:19].replace("-", "/")
    utcnow = datetime.utcnow().isoformat(" ")[5:19].replace("-", "/")
    try:
        stdscr.addstr(22, 59, f"Local: {now}")
        stdscr.addstr(23, 61, f"UTC: {utcnow}")
    except curses.error as err:
        logging.debug("statusline: %s", err)

    stdscr.addstr(23, 1, "Band:        Mode:")
    stdscr.addstr(23, 7, f"  {band}  ", curses.A_REVERSE)
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
    stdscr.addstr(23, 50, "Rig", highlightBonus(rigonline))

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
    """Sets you callsign for logging and writes preference."""
    preference["mycall"] = str(c)
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
    rectangle(stdscr, 11, 0, 21, 34)
    wy, wx = stdscr.getyx()
    help_message = [
        ".H this message  |.E### edit QSO",
        ".Q quit program  |.D### del QSO",
        ".Kyourcall       |.L Generate Log",
        ".Cyourclass      |",
        ".Syoursection    |[esc] abort inp",
        ".B## change bands|",
        ".M[CW,PH,DI] mode|",
        ".P## change power|",
        "                 |",
    ]
    stdscr.move(12, 1)
    for count, x in enumerate(help_message):
        stdscr.addstr(12 + count, 1, x)
    stdscr.move(wy, wx)
    stdscr.refresh()


def displayinfo(info):
    """It.. Well, displays a line of info..."""
    y, x = stdscr.getyx()
    stdscr.move(20, 1)
    stdscr.addstr(info)
    stdscr.move(y, x)
    stdscr.refresh()


def displayLine():
    """I'm sure this does important stuff."""
    filler = "                        "
    line = kbuf + filler[: -len(kbuf)]
    stdscr.move(9, 1)
    stdscr.addstr(line)
    stdscr.move(9, len(kbuf) + 1)
    stdscr.refresh()


def displayInputField(field):
    """this displays an input field."""
    filler = "                 "
    if field == 0:
        filler = "                 "
        y = 1
    elif field == 1:
        filler = "     "
        y = 20
    elif field == 2:
        filler = "       "
        y = 27
    stdscr.move(9, y)
    if kbuf == "":
        stdscr.addstr(filler)
    else:
        line = kbuf + filler[: -len(kbuf)]
        stdscr.addstr(line.upper())
    stdscr.move(9, len(kbuf) + y)
    stdscr.refresh()


def processcommand(cmd):
    """Process a dot command"""
    global end_program
    cmd = cmd[1:].upper()
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
    global inputFieldFocus, hiscall, hissection, hisclass, kbuf  # Globals bad m-kay
    if key == 9 or key == Space:
        inputFieldFocus += 1
        if inputFieldFocus > 2:
            inputFieldFocus = 0
        if inputFieldFocus == 0:
            hissection = kbuf  # store any input to previous field
            stdscr.move(9, 1)  # move focus to call field
            kbuf = hiscall  # load current call into buffer
            stdscr.addstr(kbuf)
        if inputFieldFocus == 1:
            hiscall = kbuf  # store any input to previous field
            dupCheck(hiscall)
            stdscr.move(9, 20)  # move focus to class field
            kbuf = hisclass  # load current class into buffer
            stdscr.addstr(kbuf)
        if inputFieldFocus == 2:
            hisclass = kbuf  # store any input to previous field
            stdscr.move(9, 27)  # move focus to section field
            kbuf = hissection  # load current section into buffer
            stdscr.addstr(kbuf)
        return
    elif key == BackSpace:
        if kbuf != "":
            kbuf = kbuf[0:-1]
            if inputFieldFocus == 0 and len(kbuf) < 3:
                displaySCP(superCheck("^"))
            if inputFieldFocus == 0 and len(kbuf) > 2:
                displaySCP(superCheck(kbuf))
            if inputFieldFocus == 2:
                sectionCheck(kbuf)
        displayInputField(inputFieldFocus)
        return
    elif key == EnterKey:
        if inputFieldFocus == 0:
            hiscall = kbuf
        elif inputFieldFocus == 1:
            hisclass = kbuf
        elif inputFieldFocus == 2:
            hissection = kbuf
        if hiscall[:1] == ".":  # process command
            processcommand(hiscall)
            clearentry()
            return
        if hiscall == "" or hisclass == "" or hissection == "":
            return
        contact = (hiscall, hisclass, hissection, band, mode, int(preference["power"]))
        log_contact(contact)
        clearentry()
        return
    elif key == Escape:
        clearentry()
        return
    elif key == Space:
        return
    elif key == 258:  # key down
        logup()
    elif key == 259:  # key up
        logdown()
    elif key == 338:  # page down
        logpagedown()
    elif key == 339:  # page up
        logpageup()
    elif curses.ascii.isascii(key):
        if len(kbuf) < maxFieldLength[inputFieldFocus]:
            kbuf = kbuf.upper() + chr(key).upper()
            if inputFieldFocus == 0 and len(kbuf) > 2:
                displaySCP(superCheck(kbuf))
            if inputFieldFocus == 2 and len(kbuf) > 0:
                sectionCheck(kbuf)
    displayInputField(inputFieldFocus)


def edit_key(key):
    """Process weird keys, esc, backspace, enter etc"""
    global editFieldFocus, end_program
    if key == 9:
        editFieldFocus += 1
        if editFieldFocus > 7:
            editFieldFocus = 1
        qsoew.move(editFieldFocus, 10)  # move focus to call field
        qsoew.addstr(qso[editFieldFocus])
        return
    elif key == BackSpace:
        if qso[editFieldFocus] != "":
            qso[editFieldFocus] = str(qso[editFieldFocus])[0:-1]
        displayEditField(editFieldFocus)
        return
    elif key == EnterKey:
        change_contact(qso)
        qsoew.erase()
        stdscr.clear()
        rectangle(stdscr, 0, 0, 7, 55)
        contactslabel = "Recent Contacts"
        contactslabeloffset = (49 / 2) - len(contactslabel) / 2
        stdscr.addstr(0, int(contactslabeloffset), contactslabel)
        logwindow()
        sections()
        stats()
        displayHelp()
        entry()
        stdscr.move(9, 1)
        end_program = True
        return
    elif key == Escape:
        qsoew.erase()
        stdscr.clear()
        rectangle(stdscr, 0, 0, 7, 55)
        contactslabel = "Recent Contacts"
        contactslabeloffset = (49 / 2) - len(contactslabel) / 2
        stdscr.addstr(0, int(contactslabeloffset), contactslabel)
        logwindow()
        sections()
        stats()
        displayHelp()
        entry()
        stdscr.move(9, 1)
        end_program = True
        return
    elif key == Space:
        return
    elif key == 258:  # arrow down
        editFieldFocus += 1
        if editFieldFocus > 7:
            editFieldFocus = 1
        qsoew.move(editFieldFocus, 10)  # move focus to call field
        qsoew.addstr(str(qso[editFieldFocus]))
        return
    elif key == 259:  # arrow up
        editFieldFocus -= 1
        if editFieldFocus < 1:
            editFieldFocus = 7
        qsoew.move(editFieldFocus, 10)  # move focus to call field
        qsoew.addstr(str(qso[editFieldFocus]))
        return
    elif curses.ascii.isascii(key):
        if len(qso[editFieldFocus]) < maxEditFieldLength[editFieldFocus]:
            qso[editFieldFocus] = qso[editFieldFocus].upper() + chr(key).upper()
    displayEditField(editFieldFocus)


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
    global qsoew, qso, end_program
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
    qsoew.addstr(1, 1, f"Call   : {qso[1]}")
    qsoew.addstr(2, 1, f"Class  : {qso[2]}")
    qsoew.addstr(3, 1, f"Section: {qso[3]}")
    qsoew.addstr(4, 1, f"At     : {qso[4]}")
    qsoew.addstr(5, 1, f"Band   : {qso[5]}")
    qsoew.addstr(6, 1, f"Mode   : {qso[6]}")
    qsoew.addstr(7, 1, f"Powers : {qso[7]}")
    qsoew.addstr(8, 1, "[Enter] to save          [Esc] to exit")
    displayEditField(1)
    while 1:
        statusline()
        stdscr.refresh()
        qsoew.refresh()
        c = qsoew.getch()
        if c != -1:
            edit_key(c)
        else:
            time.sleep(0.1)
        if end_program:
            end_program = False
            break


def editQSO(q):
    """Edit contact"""
    global qsoew, qso, end_program
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute(f"select * from contacts where id={q}")
        log = cursor.fetchone()
    if not log:
        return
    qso = ["", "", "", "", "", "", "", ""]
    qso[0], qso[1], qso[2], qso[3], qso[4], qso[5], qso[6], qso[7] = log
    qsoew = curses.newwin(10, 40, 6, 10)
    qsoew.keypad(True)
    qsoew.nodelay(True)
    qsoew.box()
    qsoew.addstr(1, 1, f"Call   : {qso[1]}")
    qsoew.addstr(2, 1, f"Class  : {qso[2]}")
    qsoew.addstr(3, 1, f"Section: {qso[3]}")
    qsoew.addstr(4, 1, f"At     : {qso[4]}")
    qsoew.addstr(5, 1, f"Band   : {qso[5]}")
    qsoew.addstr(6, 1, f"Mode   : {qso[6]}")
    qsoew.addstr(7, 1, f"Powers : {qso[7]}")
    qsoew.addstr(8, 1, "[Enter] to save          [Esc] to exit")
    displayEditField(1)
    while 1:
        statusline()
        stdscr.refresh()
        qsoew.refresh()
        c = qsoew.getch()
        if c != -1:
            edit_key(c)
        else:
            time.sleep(0.1)
        if end_program:
            end_program = False
            break


def main(s):  # pylint: disable=unused-argument
    """Main entry point for the program"""
    read_sections()
    readSCP()
    create_DB()
    curses.start_color()
    curses.use_default_colors()
    if curses.can_change_color():
        curses.init_color(curses.COLOR_MAGENTA, 1000, 640, 0)
        curses.init_color(curses.COLOR_BLACK, 0, 0, 0)
        curses.init_color(curses.COLOR_CYAN, 500, 500, 500)
        curses.init_pair(1, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
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
    stats()
    displayHelp()
    cloudlogauth()
    stdscr.refresh()
    stdscr.move(9, 1)
    while 1:
        statusline()
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
            time.sleep(0.1)
        if end_program:
            break
        poll_radio()


wrapper(main)
