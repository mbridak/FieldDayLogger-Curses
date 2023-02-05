"""Group class"""
# pylint: disable=invalid-name
# pylint: disable=too-many-function-args

import curses
import time

try:
    from fdcurses.lib.edittextfield import EditTextField
except ModuleNotFoundError:
    from lib.edittextfield import EditTextField


class GroupSettingsScreen:
    """Group settings screen"""

    BACK_SPACE = 263
    TAB = 9
    SHIFT_TAB = 353
    ESCAPE = 27
    QUESTIONMARK = 63
    ENTERKEY = 10
    SPACE = 32
    WIDTH = 76
    HEIGHT = 10
    WINY = 1
    WINX = 2
    TITLE = "GROUP SETTINGS"
    MENU = [
        "",
        "",
        "                              GROUP SETTINGS",
        "",
        " Use aggregation server: [ ]",
        " Multicast Group:                      Multicast Port:",
        " Interface IP:",
        "",
        "",
    ]

    def __init__(self, preference):
        """setup settings screen"""
        self.preference = preference
        self.input_field_focus = 0
        self.screen = curses.newwin(self.HEIGHT, self.WIDTH, self.WINY, self.WINX)
        self.screen.keypad(True)
        self.screen.nodelay(True)
        self.screen.box()
        self._title()

        self.useserver = EditTextField(self.screen, 5, 27, 1, curses.A_UNDERLINE)
        self.useserver.set_bool(True)
        self.useserver.set_state(bool(preference.get("useserver")))

        self.multicast_group = EditTextField(self.screen, 6, 19, 16, curses.A_UNDERLINE)
        self.multicast_group.lowercase(True)
        self.multicast_group.set_text(preference.get("multicast_group"))

        self.multicast_port = EditTextField(self.screen, 6, 56, 5, curses.A_UNDERLINE)
        self.multicast_port.set_text(str(preference.get("multicast_port")))

        self.interface_ip = EditTextField(self.screen, 7, 16, 16, curses.A_UNDERLINE)
        self.interface_ip.lowercase(True)
        self.interface_ip.set_text(preference.get("interface_ip"))

        self.input_fields = [
            self.useserver,
            self.multicast_group,
            self.multicast_port,
            self.interface_ip,
        ]

        self._display_menu()

    def _title(self):
        position = int((self.WIDTH / 2) - (len(self.TITLE) / 2))
        self.screen.addch(0, position - 1, curses.ACS_RTEE)
        self.screen.addstr(0, position, self.TITLE)
        self.screen.addch(curses.ACS_LTEE)

    def _display_menu(self):
        """Displays menu text and input fields"""
        for vert, line in enumerate(self.MENU):
            self.screen.addstr(vert + 1, 1, line)
        for item in self.input_fields:
            item.get_focus()
        self.useserver.get_focus()

    def show(self):
        """show screen"""
        self.useserver.get_focus()
        self.screen.refresh()
        while True:
            c = self.screen.getch()
            if c == self.TAB:
                self.input_field_focus += 1
                if self.input_field_focus > len(self.input_fields) - 1:
                    self.input_field_focus = 0
                self.input_fields[self.input_field_focus].get_focus()
                continue
            if c == self.SHIFT_TAB:
                self.input_field_focus -= 1
                if self.input_field_focus < 0:
                    self.input_field_focus = len(self.input_fields) - 1
                self.input_fields[self.input_field_focus].get_focus()
                continue
            if c == self.ESCAPE:
                self.screen.erase()
                return False
            if c == self.ENTERKEY:
                self.preference["multicast_group"] = self.multicast_group.text()
                self.preference["useserver"] = self.useserver.get_state()
                try:
                    self.preference["multicast_port"] = int(self.multicast_port.text())
                except ValueError:
                    self.preference["multicast_port"] = 0
                self.preference["interface_ip"] = self.interface_ip.text()
                self.screen.erase()
                return self.preference
            self.input_fields[self.input_field_focus].getchar(c)
            time.sleep(0.01)

    def close(self):
        """not useful yet"""
        self.screen.endwin()
