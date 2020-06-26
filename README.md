## K6GTE Field Day logger

The logger is written in Python 3, and uses the curses lib. It will work with Linux and Mac, but since the Windows curses lib is lacking it will not work properly in Windows.

The log is stored in an sqlite3 database file 'FieldDay.db'. If you need to wipe everything and start clean, just delete this file. The screen size expected by the program is an 80 x 24 character terminal. Nothing needs to be installed, compiled etc... Just make FieldDayLogger.py executable and run it within the same folder.

![Alt text](https://github.com/mbridak/FieldDayLogger/raw/master/logger.png)


## Caveats
This is a simple logger ment for single op, it's not usable for clubs.

## Commands:
Commands start with a period character in the callsign field and are immediately followed by any information needed by the command.

```
.H displays a short list of commands.
.Q Quit the program.
.Kyourcall Sets your callsign. .KK6GTE will set it to K6GTE.
.Cyourclass Sets your class. .C1O wil set your class to 1O.
.Syoursection Sets your section. .SORG sets your section to ORG.
.P# Sets the power level, .P5 will set the power to 5 watts.
.MCW .MPH .MDI Sets the mode. CW Morse, PH Phone, DI Digital.
.B# sets the band, .B40 for 40 meters.
.D# Deletes log entry. .D26 will delete the log line starting with 026.
.E# Edits log entry. .E26 will edit the log line starting with 026.
.L Generate Cabrillo log file for submission.
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

## Features

#### Radio Polling via rigctld
If you run rigctld on the computer that you are logging from, the radio will be polled for band/mode updates automatically. There is an indicator at the bottom of the logging window to indicate polling status. Dim if no connection or timeout, and highlighted if all okay.

![Alt text](https://github.com/mbridak/wfd_py_logger/raw/master/rigctld.png)

#### Editing an existing contact
Use the Up/Down arrow keys or PageUp/PageDown to scroll the contact into view. Your mouse scroll wheel may work as well. Double left click on the contact to edit, or use the '.E' command. Use the TAB or Up/Down arrow keys to move between fields. Backspace to erase and retype what you need.
Once done press the Enter key to save, or the Escape key to exit.

#### Super Check Partial
If you type more than two characters in the callsign field the program will filter the input through a "Super Check Partial" routine and show you possible matches to known contesting call signs. Is this useful? Doubt it.

#### Section partial check
As you type the section abbreviation you are presented with a list of all possible sections that start with what you have typed.

#### DUP checking
Once you type a complete callsign and press TAB to advance to the next field. The callsign is checked against previous callsigns in your log. It will list any prior contact made with the band and mode of the contact. If the band and mode are the same as the one you are currently using, the listing will be highlighted to alert you that this is a DUP.

#### Autofill
If you have worked this person before on another band/mode the program will load the class and section used previously for this call so you will not have to enter this info again.

## TODO
  * Enter a contact at a specific time.

Let me know if you think of something else.