# K6GTE Field Day logger (Curses)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)  [![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)  [![Made With:Curses](https://img.shields.io/badge/Made%20with-Curses-green)](https://docs.python.org/3/library/curses.html) ![PyPI - Downloads](https://img.shields.io/pypi/dm/fdcurses?label=PYPI-Downloads&logo=pypi)

![logo](https://raw.githubusercontent.com/mbridak/FieldDayLogger-Curses/master/fdcurses/data/k6gte.fdcurses.svg)

The logger is written in Python 3, and uses the curses lib. It will work with Linux and Mac, but since the Windows curses lib is lacking it will not work properly in Windows.

The log is stored in an sqlite3 database file 'FieldDay.db'. If you need to wipe everything and start clean, just delete this file. The screen size expected by the program is an 80 x 24 character terminal.

You may have to install Tkinter. It's used for clipboard access.

`sudo apt install python3-tk`

## Installation and running

```bash
# install
pip install fdcurses

# update
pip install -U fdcurses

# remove
pip uninstall fdcurses

# running
fdcurses
```

![Alt text](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/logger.png)

# Recent changes

- [23-2-5] Fixed crash when too many SCP matches happen.
- [23-2-5] Safer dict key access.
- [23-2-4] Repackaged for PyPi. Updated RAC sections.
Added an aggregation server for group/club logging.

# The basic functionality

## Commands

Commands start with a period character in the callsign field and are immediately followed by any information needed by the command.

```text
.H displays a short list of commands.
.Q Quit the program.
.P# Sets the power level, .P5 will set the power to 5 watts.
.MCW .MPH .MDI Sets the mode. CW Morse, PH Phone, DI Digital.
.B# sets the band, .B40 for 40 meters.
.D# Deletes log entry. .D26 will delete the log line starting with 026.
.E# Edits log entry. .E26 will edit the log line starting with 026.
.L Generate Cabrillo, ADIF and stats.
.S Settings Screen.
.G Group settings.
.C Group Chat.
[esc] abort input, clear all fields.
```

After the command is entered press the ENTER key to execute it.

## Initial Setup

Before operating for the first time, you will need to edit the settings. Use the `.S` command to pull up the settings screen. You use the TAB and Shift TAB keys to move between the fields. Enter key to commit changes. Esc key to exit without saving.

![Settings Screen](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/settings_screen.png)

The CW_port can be set to 6789 for cwdaemon and winkeydaemon, 8000 for PyWinkeyer.

## Logging

Okay you've made a contact. Enter the call in the call field. As you type it in, it will do a super check partial (see below). Press TAB or SPACE to advance to the next field. Once the call is complete it will do a DUP check (see below). It will try and Autofill the next fields (see below). When entering the section, it will do a section partial check (see below). Press the ENTER key to submit the Q to the log. It can send contact to Cloudlog (see below). If it's a busted call or a dup, press the ESC key to clear all inputs and start again.

## Features

#### Radio Polling via rigctld or flrig

If you run rigctld or flrig on the computer that you are logging from, the radio will be polled for band/mode updates automatically. There is an indicator at the bottom of the logging window to indicate polling status. :anger: if no connection or timeout, and :radio: if all okay.

![Alt text](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/rigctld.png)

If you're running this in a Raspberry Pi terminal, you may not get the emoji status icons. You may need to install "no tofu" fonts. I believe `sudo apt install fonts-noto` should install them.

#### CW macros

The macros are stored in the cwmacros_fd.txt file. The fields to edit are pretty straightforward. Each line has 3 fields separated by the pipe `|` character. The first is the Fkey being assigned. The second is a useless label. The third is the actual macro. the bits between the curly braces gets replaced by actual values

`F1|Run CQ|cq fd {MYCALL} {MYCALL} k`

You may run into a problem with your terminal program taking the F keys and doing things with them.
For instance, Gnome-Terminal wanted to full screen the terminal when I pressed F11.
I had to remap that to Shift+F11 in the terminal preference shortcuts.
It also wanted to show a menu each time you pressed F10.
That can be suppressed in the terminals preferences general section.

If you're using cwdaemon you can change the cw sending speed by pressing + or -.
You can abort CW output by pressing `ESC`.

#### Callsign lookups

An option of callsign lookups for gridsquare and op name is offered by one of three services: QRZ, HamDB or HamQTH. The use of these can be turned on or off by editing the JSON preference file. The lookup happens in it's own thread and is kicked off after the cursor leaves the call field. If the look up is successful, you'll see the status line at the bottom change giving you name, grid, bearing and distance to contact.

![lookup result](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/lookup-result.png)

#### WSJT-X FT8

We monitor the multicast address used by wsjt-x for UDP packets. If the packet says we've made a contact, we automatically add the contact to the Field Day log.

#### Cloudlog

If you use Cloudlog, contacts can be pushed to your Cloudlog server.
The use of this can be turned on or off by editing the JSON preference file.

#### Editing an existing contact

Use the Up/Down arrow keys or PageUp/PageDown to scroll the contact into view. Your mouse scroll wheel may work as well. Double left click on the contact to edit, or use the '.E' command. Use the TAB or Up/Down arrow keys to move between fields. Backspace to erase and retype what you need.
Once done press the Enter key to save, or the Escape key to exit.

![Alt text](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/editcontact.png)

#### Super Check Partial

If you type more than two characters in the callsign field the program will filter the input through a "Super Check Partial" routine and show you possible matches to known contesting call signs. Is this useful? Doubt it.

![Alt text](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/scp.png)

#### Section partial check

As you type the section abbreviation you are presented with a list of all possible sections that start with what you have typed.

![Alt text](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/sectioncheckpartial.png)

#### DUP checking

Once you type a complete callsign and press TAB or SPACE to advance to the next field. The callsign is checked against previous callsigns in your log. It will list any prior contact made showing the band and mode of the contact. If the band and mode are the same as the one you are currently using, the listing will be highlighted, the screen will flash, a bell will sound to alert you that this is a DUP. At this point you and the other OP can argue back and forth about who's wrong. In the end you'll put your big boy pants on and make a decision if you'll enter the call or not.

![Alt text](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/dupe_check.png)

#### Autofill

If you have worked this person before on another band/mode the program will load the class and section used previously for this call so you will not have to enter this info again.

#### The Log

If you've gotten this far I commend you. Let's hope this part actually works, 'cause if you spent 24 hours yelling into a mic, tapity tap taping a Morse key and clickity click clicking on an FT8 screen and all you get is 'sad trombone'... Well...

The command '.L' will as far as I can tell generate a Cabrillo log file which you should edit to add your name, email address, home address and possible club affiliation. It will also generate a statistics file with a band/mode breakdown, which is something you'll have to hand enter on the ARRL submission page.

I've used cr/lf line endings because that's what the log checker expects. So if you edit the file you might want to run the file through 'unix2dos' to make sure the checker does not choke.

I've added an ADIF export of sorts. There's a logistical problem with data modes. Field Day does not care what the data mode is, it's just recorded as a generic data contact. So I didn't bother to capture that in the database. So since most of america and maybe canada will use FT8 because it's the new hotness, I just made the data contacts map over to FT8 in ADIF. Sorry. 

# The Aggregation Server

## Group / Club logging

I have added a group contact aggregating server. This can be run on the same
computer as the client program, or on a separate dedicated PC or Raspberry Pi
on the same network.

![Picture showing main server screen](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/server_pic.png)

### Server configuration

The configuration file for the server is a JSON file 'server_preferences.json'.

```json
{
    "ourcall": "W1AW",
    "ourclass": "3A",
    "oursection": "ORG",
    "bonus": {
        "emergency_power": {
            "bool": 0,
            "station_count": 0
        },
        "media_publicity": 0,
        "public_location": 0,
        "public_info_table": 0,
        "message_to_section_manager": 0,
        "message_handling": {
            "bool": 0,
            "message_count": 0
        },
        "satellite_qso": 0,
        "w1aw_bulletin": 0,
        "educational_activity": 0,
        "elected_official_visit": 0,
        "agency_representative_visit": 0,
        "gota": 0,
        "web_submission": 0,
        "youth_participation": {
            "bool": 0,
            "youth_count": 0
        },
        "social_media": 0,
        "safety_officer": 0
    },
    "batterypower": 1,
    "name": "Hiram Maxim",
    "address": "225 Main Street",
    "city": "Newington",
    "state": "CT",
    "postalcode": "06111",
    "country": "USA",
    "email": "Hiram.Maxim@arrl.net",
    "mullticast_group": "224.1.1.1",
    "multicast_port": 2239,
    "interface_ip": "0.0.0.0"
}
```

Go ahead and edit this file before running the server. Feel free to leave the
last 3 items as they are unless you have good reason not too. The rest should
be straight forward.

Under the bonuses section, if your group qualifies for a bonus, replace the '0'
next to the bonus with a '1'. Three of the bonuses require a count of items
qualifiying you for the bonus. For example Message Handling. If your group
qualifies for this, change the value of 'bool' to a 1, and then 'message_count'
to the number of messages handled.

### Running The Server

The server is a terminal / curses program and uses standard libraries that
should already be installed.

Just make server.py executable and run it the same way as the client.

### Client configuration for groups

In the main screen, enter the `.G` command.

![Picture showing settings dialog tab](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/groupsettings.png)

Go ahead and place a check next to 'Use aggregation server'. Rejoyce and let
merriment be had by all. Be sure and have your callsign already set before
checking this. If you forgot, Uncheck it, set your callsign and then check it.

A couple of things will change on the client when this is done. You will see
that your callsign will disappear and be replaced with your clubs call that the
server reports. The portion of the screen where all the different ARRL sections
are displayed will be replaced by a group chat window.

### Chat Window

![Picture showing chat window](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/groupchatwindow.png)

The chat window is pretty straight forward. If someone mentions you in the chat
that line will be highlighted with an accent color.

To enter text into the chat. Enter the `.C` command.

To exit the chat and return to logging contacts, press `ESC`.

There is one command you can type into the chat window that may be of use.
if you type @stats into the window the server will dump out some stats into the
chat.

```text
Server: 
Band   CW    PH    DI
 160     0     0     0
  80     0     0    25
  40     0   159     0
  20     1   162   126
  15     0     0     0
  10     0     0     0
   6     0    17     0
   2     0     0     0

Score: 1284
Last Hour: 271
Last 15: 81
```

Since most people will not be able to see the screen of the server, if it has
one at all. You may find this useful.

### How to know the server is there

Most likely, the server will be in some other tent/building/area of the room.
Every 10 seconds or so the server will send out a UDP network packet saying
it's there. As long as your client keeps seeing these packets the group call
indicator at the bottom of the screen will look like:

![Picture showing server status](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/serverokay.png)

But if about 30 seconds go by with no update from the server, the indicator
will change to:

![Picture showing server status](https://github.com/mbridak/FieldDayLogger-Curses/raw/master/pics/servernobueno.png)

Go check on it.

### Logging reliability

As mentioned before, We're using UDP traffic to pass data back and forth to the
server. UDP traffic is a 'Fire and forget' method. Akin to a bunch of people
in the same room yelling at eachother. Everyone can hear you, but you don't
know if anyone heard what you said. This has both Advantages and Disadvantages.
One advantage is that your program is not stuck waiting for a reply or timeout
locking up your user interface. The disadvantage is you have no idea if anyone
took note of what you had said.

This works fine in a local network since the traffic doesn't have to survive
the trip through the big bad tubes of the internet. That being said, someone
may trip on a cord, unplugging the router/switch/wireless gateway. Or someone
may be trying to use WIFI and they are Soooooo far away you can barely see
their tent. Or worse you have EVERYONE on WIFI, and there are packet collisions
galore degrading your network.

To account for this, the client logging program keeps track of recent packets
sent, noting the time they were sent at. The server after getting a packet,
generates a response to the sender with it's unique identifyer. Once the client
gets the response from the server, it will remove the request on the local side
and print a little message at the bottom of the screen giving you a visual
confirmation that the command was acted upon by the server.
If the server does not respond either because the response was lost or the
request never made it to reply too. The client will resend the
packet every 30 seconds until it gets a reply.

But all this may still result in the server not having a copy of your contact.
To account for this, when the "Generate Logs" button is pressed on the client,
the client will resend all the logged contacts that have not gotten responses
from the server. You can keep doing this, if need be,  until it gets them all.

Chat traffic is best effort. Either everyone sees your plea for more beer or
they don't. No retry is made for chat traffic. Just get your butt up and make
the trip to the cooler.

### Generating the cabrillo file

If any of the networked clients enters the `.L` command, the server will be
told to generate it's cabrillo file, it will be named
'WhatEverYourClubCallIs.log'

If for some reason no clients exist to enter the command you can launch the
server with the -l flag `./server.py -l` the log will be generated and the
program will exit.

### I'm sure there are short cummings

It's early days, and I've mainly tested the operations with the client logging
program and several simulated operators, see file in `testing/simulant.py`
Real world use for Field Day in September is hard to come by. So I'm sure there
are a couple of things I forgot, or didn't account for.

If you are part of a group of linux using Hams, please take this for a spin and
tell me what I missed or could do better.
