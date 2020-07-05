## K6GTE Field Day logger

The logger is written in Python 3, and uses the curses lib. It will work with Linux and Mac, but since the Windows curses lib is lacking it will not work properly in Windows.

The log is stored in an sqlite3 database file 'FieldDay.db'. If you need to wipe everything and start clean, just delete this file. The screen size expected by the program is an 80 x 24 character terminal. Nothing needs to be installed, compiled etc... Just make FieldDayLogger.py executable and run it within the same folder.

![Alt text](https://github.com/mbridak/FieldDayLogger/raw/master/pics/logger.png)


## Caveats
This is a simple logger ment for single op, it's not usable for clubs.

## What was learned from Field Day 2020.

It worked fairly well. I figured out pretty quickly that I should have made the space bar advance to the next field like the TAB key does. I made that change then pushed the changes to github during Field Day.

Everything else worked just about as expected.

## Commands:
Commands start with a period character in the callsign field and are immediately followed by any information needed by the command.

```
.H displays a short list of commands.
.Q Quit the program.
.Kyourcall Sets your callsign. .KK6GTE will set it to K6GTE.
.Cyourclass Sets your class. .C1E will set your class to 1E.
.Syoursection Sets your section. .SORG sets your section to ORG.
.P# Sets the power level, .P5 will set the power to 5 watts.
.MCW .MPH .MDI Sets the mode. CW Morse, PH Phone, DI Digital.
.B# sets the band, .B40 for 40 meters.
.D# Deletes log entry. .D26 will delete the log line starting with 026.
.E# Edits log entry. .E26 will edit the log line starting with 026.
.L Generate Cabrillo, ADIF and stats.
[esc] abort input, clear all fields.
```

After the command is entered press the TAB key to execute it.

## Initial Setup
When run for the first time, you will need to set your callsign, class, section, band, mode and power used for the contacts.

So when I initially start the program I would enter the following:

```
.KK6GTE
.C1B
.SORG
.P5
.B40
.MCW
``` 
This says I'm K6GTE 1B ORG, running 5 watts CW on 40 Meters.

## Logging
Okay you've made a contact. Enter the call in the call field. As you type it in, it will do a super check partial (see below). Press TAB or SPACE to advance to the next field. Once the call is complete it will do a DUP check (see below). It will try and Autofill the next fields (see below). When entering the section, it will do a section partial check (see below). Press the ENTER key to submit the Q to the log. If it's a busted call or a dup, press the ESC key to clear all inputs and start again.
Once you type a complete callsign and press TAB or SPACE to advance to the next field. The callsign is checked against previous callsigns in your log. It will list any prior contact made showing the band and mode of the contact. If the band and mode are the same as the one you are currently using, the listing will be highlighted, the screen will flash, a bell will sound to alert you that this is a DUP. At this point you and the other OP can argue back and forth about who's wrong. In the end you'll put your big boy pants on and make a decision if you'll enter the call or not.

## Features

#### Radio Polling via rigctld
If you run rigctld on the computer that you are logging from, the radio will be polled for band/mode updates automatically. There is an indicator at the bottom of the logging window to indicate polling status. Dim if no connection or timeout, and highlighted if all okay.

![Alt text](https://github.com/mbridak/FieldDayLogger/raw/master/pics/rigctld.png)

#### Editing an existing contact
Use the Up/Down arrow keys or PageUp/PageDown to scroll the contact into view. Your mouse scroll wheel may work as well. Double left click on the contact to edit, or use the '.E' command. Use the TAB or Up/Down arrow keys to move between fields. Backspace to erase and retype what you need.
Once done press the Enter key to save, or the Escape key to exit.

![Alt text](https://github.com/mbridak/FieldDayLogger/raw/master/pics/editcontact.png)

#### Super Check Partial
If you type more than two characters in the callsign field the program will filter the input through a "Super Check Partial" routine and show you possible matches to known contesting call signs. Is this useful? Doubt it.

![Alt text](https://github.com/mbridak/FieldDayLogger/raw/master/pics/scp.png)

#### Section partial check
As you type the section abbreviation you are presented with a list of all possible sections that start with what you have typed.

![Alt text](https://github.com/mbridak/FieldDayLogger/raw/master/pics/sectioncheckpartial.png)

#### DUP checking
Once you type a complete callsign and press TAB or SPACE to advance to the next field. The callsign is checked against previous callsigns in your log. It will list any prior contact made showing the band and mode of the contact. If the band and mode are the same as the one you are currently using, the listing will be highlighted, the screen will flash, a bell will sound to alert you that this is a DUP. At this point you and the other OP can argue back and forth about who's wrong. In the end you'll put your big boy pants on and make a decision if you'll enter the call or not.

![Alt text](https://github.com/mbridak/FieldDayLogger/raw/master/pics/dupe_check.png)


#### Autofill
If you have worked this person before on another band/mode the program will load the class and section used previously for this call so you will not have to enter this info again.

#### The Log
If you've gotten this far I commend you. Let's hope this part actually works, 'cause if you spent 24 hours yelling into a mic, tapity tap taping a Morse key and clickity click clicking on an FT8 screen and all you get is 'sad trombone'... Well...

The command '.L' will as far as I can tell generate a cabrillo log file which you should edit to add your name, email address, home address and possible club affiliation. It will also generate a statistics file with a band/mode breakdown, which is something you'll have to hand enter on the ARRL submission page.

I've used cr/lf line endings because that's what the log checker expects. So if you edit the file you might want to run the file through 'unix2dos' to make sure the checker does not choke. 

I've added an adif export of sorts. There's a logistical problem with data modes. Field Day does not care what the data mode is, it's just recorded as a generic data contact. So I didn't bother to capture that in the database. So since most of america and maybe canada will use FT8 because it's the new hotness, I just made the data contacts map over to FT8 in ADIF. Sorry. 

## TODO
  * Enter a contact at a specific time.

Let me know if you think of something else.
