##
##    This file is part of Smoopi (http://smoothieware.org/). This version is heavily based on hb04.py (https://github.com/wolfmanjm/kivy-smoothie-host/tree/master/modules).
##    Smoothie is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
##    Smoothie is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
##    You should have received a copy of the GNU General Public License along with Smoothie. If not, see <http://www.gnu.org/licenses/>.
##
##    alkabal@free.fr@2019 based on predecessor from morris@wolfman.com
##    Thanks for sharing and thanks for help from Arthur and wolfmanjm
##


# implements interface  for the whb04b USB pendant

from easyhid import Enumeration
from kivy.logger import Logger
from kivy.app import App

import threading
import traceback
import math
import configparser
import time

whb04b = None


def start(args=""):
    global whb04b
    # print("start with args: {}".format(args))
    pid, vid = args.split(':')
    whb04b = WHB04B(int(pid, 16), int(vid, 16))
    whb04b.start()
    return True


def stop():
    global whb04b
    whb04b.stop()


class WHB04BHID:
    PACKET_LEN = 64
    TIMEOUT = 1000  # milliseconds
    CONNECT_RETRIES = 3

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.hid = None
        self.opened = False
        return None

    # Initialize libhid and connect to USB device.
    #
    # @vid - Vendor ID of the USB device.
    # @pid - Product ID of the USB device.
    #
    # USB vendor  ID = 0x10ce
    # USB product ID = 0xeb93
    #
    # Returns True on success.
    # Returns False on failure.
    def open(self, vid, pid):
        self.opened = False

        # Stores an enumeration of all the connected USB HID devices
        # en = Enumeration(vid=vid, pid=pid)
        en = Enumeration()
        # for d in en.find():
        #     print(d.description())

        # return a list of devices based on the search parameters
        devices = en.find(vid=vid, pid=pid, interface=0)
        if not devices:
            Logger.info("WHB04BHID: No matching device found")
            return None

        if len(devices) > 1:
            Logger.info("WHB04BHID: more than one device found: {}".format(devices))
            return None

        # open the device
        self.hid = devices[0]
        self.hid.open()

        Logger.debug("WHB04BHID: Opened: {}".format(self.hid.description()))
        self.opened = True
        return True

    # Close HID connection and clean up.
    #
    # Returns True on success.
    # Returns False on failure.
    def close(self):
        self.hid.close()
        self.opened = False
        return True

    # Send a USB packet to the connected USB device.
    #
    # @packet  - Data, in string format, to send to the USB device.
    # @timeout - Read timeout, in milliseconds. Defaults to TIMEOUT.
    #
    # Returns True on success.
    # Returns False on failure.
    def send(self, packet, timeout=TIMEOUT):
        n = self.hid.write(packet)
        return n

    # Read data from the connected USB device.
    #
    # @plen    - Number of bytes to read. Defaults to PACKET_LEN.
    # @timeout - Read timeout, in milliseconds. Defaults to TIMEOUT.
    #
    # Returns the received bytes on success.
    # Returns None on failure.
    def recv(self, plen=PACKET_LEN, timeout=TIMEOUT):
        packet = self.hid.read(size=plen, timeout=timeout)
        return packet

    # send feature report, but breaks it into 7 byte packets
    def write(self, data):
        n = 0
        n += self.hid.send_feature_report(data[0:7], 0x06)
        n += self.hid.send_feature_report(data[7:14], 0x06)
        n += self.hid.send_feature_report(data[14:21], 0x06)
        return n

# button definitions
BUT_NONE = 0
BUT_RESET = 1
BUT_STOP = 2
BUT_START = 3
BUT_FEEDP = 4
BUT_FEEDM = 5
BUT_SPINDLEP = 6
BUT_SPINDLEM = 7
BUT_MHOME = 8
BUT_SAFEZ = 9
BUT_WHOME= 10
BUT_SPINDLE = 11
BUT_FN = 12
BUT_PROBEZ = 13
BUT_MPG = 14
BUT_STEP = 15
BUT_MACRO10 = 16


class WHB04B():
    lcd_data = [
        0xFE, 0xFD, 0xFE, # id + seed
        0,           # Status
        0, 0, 0, 0,  # X WC
        0, 0, 0, 0,  # Y WC
        0, 0, 0, 0,  # Z WC
        0, 0,        # F ovr
        0, 0,        # S ovr
        0,           # padding
    ]

    lock = threading.RLock()
    # button look up table

    butlut = {
        1: "reset",
        2: "stop",
        3: "start",
        4: "feed+",
        5: "feed-",
        6: "spindle+",
        7: "spindle-",
        8: "mhome",
        9: "safez",
        10: "whome",
        11: "spindle",
        13: "probez",
        14: "mpg",
        15: "step",
        16: "macro10",
    }

    butlutfn = {
        1: "macro11",
        2: "macro12",
        3: "macro13",
        4: "macro1",
        5: "macro2",
        6: "macro3",
        7: "macro4",
        8: "macro5",
        9: "macro6",
        10: "macro7",
        11: "macro8",
        13: "macro9",
        14: "macro14",
        15: "macro15",
        16: "macro16",
    }

    axislut = {0x06: 'OFF', 0x11: 'X', 0x12: 'Y', 0x13: 'Z', 0x14: 'A', 0x15: 'B', 0x16: 'C'} # button off or set Axis
    steplut = {0x0d: 0.001, 0x0e: 0.01, 0x0f: 0.1, 0x10: 1, 0x1a: 1, 0x1b: 1, 0x1c: 0}        # combined button for set step   #or 0x1c = lead = move locked
    mpglut = {0x0d: 2, 0x0e: 5, 0x0f: 10, 0x10: 30, 0x1a: 60, 0x1b: 100, 0x1c: 0}             # combined button for set mpg %  #or 0x1c = lead = move locked
    conlut = {0x0d: 1, 0x0e: 2, 0x0f: 3, 0x10: 4, 0x1a: 5, 0x1b: 6, 0x1c: 0}                  # con mode look up table this appears after set lead mode and go back the rotary button
    status = 0x40                                                                             # start with lead mode
    macrobut = {}
    fovermax = 1
    fovermin = 1
    foverrange = 1
    sovermax = 1
    sovermin = 1
    soverrange = 1
    f_ovr = 100
    s_ovr = 100

    def __init__(self, vid, pid):
        # WHB04B vendor ID and product ID
        self.vid = vid
        self.pid = pid
        self.hid = WHB04BHID()

    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
            val = val - (1 << bits)         # compute negative value
        return val                          # return positive value as is

    def start(self):
        self.quit = False
        self.t = threading.Thread(target=self._run)
        self.t.start()

    def stop(self):
        self.quit = True
        self.t.join()

    def load_macros(self):
        try:
            config = configparser.ConfigParser()
            config.read('whb04b.ini')
            # load user defined macro buttons
            for (key, v) in config.items('macros'):
                self.macrobut[key] = v
                
            # load any default settings
            self.fovermax = config.getint("defaults", "fovmax", fallback=8)
            self.fovermin = config.getint("defaults", "fovmin", fallback=8)
            self.foverrange = config.getint("defaults", "fovrange", fallback=8)
            self.sovermax = config.getint("defaults", "sovmax", fallback=8)
            self.sovermin = config.getint("defaults", "sovmin", fallback=8)
            self.soverrange = config.getint("defaults", "sovrange", fallback=8)

        except Exception as err:
            Logger.warning("WHB04B: WARNING - exception parsing config file: {}".format(err))
            self.app.main_window.async_display("WHB04B - WARNING - exception parsing config file: {}".format(err))



    def handle_buttonrun(self, btn, axis):
        # some buttons have default functions and are available when machine is running and can't be remapped

        if btn == BUT_FEEDP:
            self.f_ovr += self.foverrange
            if self.f_ovr > self.fovermax:
                self.f_ovr = self.fovermax
            self.setovr(self.f_ovr, self.s_ovr)
            self.setstatus(self.status)
            self.update_lcd()
            return True
        elif btn == BUT_FEEDM:
              self.f_ovr -= self.foverrange
              if self.f_ovr < self.fovermin:
                  self.f_ovr = self.fovermin
              self.setovr(self.f_ovr, self.s_ovr)
              self.setstatus(self.status)
              self.update_lcd()
              return True
        elif btn == BUT_SPINDLEP:
              self.s_ovr += self.soverrange                     # adjust S override, (TODO  this is tool speed or laser power)
              if self.s_ovr > self.sovermax:
                  self.s_ovr = self.sovermax
              self.setovr(self.f_ovr, self.s_ovr)
              self.setstatus(self.status)
              self.update_lcd()
              return True
        elif btn == BUT_SPINDLEM:
              self.s_ovr -= self.soverrange                      # adjust S override, (TODO  this is tool speed or laser power)
              if self.s_ovr < self.sovermin:
                  self.s_ovr = self.sovermin
              self.setovr(self.f_ovr, self.s_ovr)
              self.setstatus(self.status)
              self.update_lcd()
              return True
        elif btn == BUT_STEP:
              self.status = 0x01
              self.setovr(self.f_ovr, self.s_ovr)
              self.setstatus(self.status)
              self.update_lcd()
              oneshotdebug4 = 0                                                                     #
              oneshotdebug5 = 0
              self.app.main_window.async_display("WHB04B - STEP MODE")
              return True
        elif btn == BUT_MPG:
              self.status = 0x02
              self.setovr(self.f_ovr, self.s_ovr)
              self.setstatus(self.status)
              self.update_lcd()
              oneshotdebug4 = 0                                                                     #
              oneshotdebug5 = 0
              self.app.main_window.async_display("WHB04B - MPG MODE")
              return True
        elif btn == BUT_MACRO10:
              if self.status <= 0x02:
                 self.status = self.status + 0x80                           # set mode absolue for DRO if mode is relative and con or step or mpg
              elif self.status <= 0x42:
                 self.status = self.status + 0x40                           # set mode absolue for DRO if mode is RESET
              elif self.status >= 0x80:
                 self.status = self.status - 0x80                           # set mode relative for DRO if mode is absolue and con or step or mpg
              self.setstatus(self.status)
              self.update_lcd()
              return True
        elif btn == BUT_RESET:
              if self.app.status == 'Alarm' and self.app.is_connected:
                  self.app.main_window.do_kill()                             # ask smoopi to clear alarm after killall
              return True
        elif btn == BUT_STOP and self.app.status != 'Alarm':
              self.app.main_window._abort_print(True)                         # send killall to smoopi
              return True
        elif btn == BUT_START:
              if not self.app.main_window.is_printing and not self.app.main_window.paused:
                      self.app.main_window.async_display("WHB04B - Do start last file")      # display ok on rpi
                      self.app.main_window.start_last_file()        # i think for CNC better to remove this function
                      return True
              elif self.app.main_window.paused or self.app.main_window.is_printing:
                    self.app.main_window.async_display("WHB04B - Do Resume/Pause")                    # display ok on rpi
                    self.app.main_window.start_print()              # the check is done inside smoopi
                    return True
        return False


    def handle_button(self, btn, axis):
        name = self.butlut[btn]

        if(name in self.macrobut):
            # use redefined macro and standard button from ini + check if script with @
            
            cmd = self.macrobut[name]            
            
            if cmd.startswith('@'):
                self._send_script(cmd[1:])
                self.app.main_window.async_display("Script sended: {}".format(cmd))
                return True
            elif "{axis}" in cmd:
                cmd = cmd.replace("{axis}", axis)
            elif "find-center" == cmd:
                self.app.tool_scripts.find_center()
                return True

            self.app.comms.write("{}\n".format(cmd))
            return True
        # some buttons have default functions
        cmd = None
        if btn == BUT_SPINDLE:
            cmd = "M5" if self.app.is_spindle_on else "M3"

        if cmd:
            self.app.comms.write("{}\n".format(cmd))
            return True
        return False



    def handle_buttonfn(self, btn, axis):
        name = self.butlutfn[btn]

        if(name in self.macrobut):
            # use redefined macro and standard button from ini + check if script with @

          cmd = self.macrobut[name]            
            
          if cmd.startswith('@'):
                self._send_script(cmd[1:])
                self.app.main_window.async_display("Script sended: {}".format(cmd))
                return True
          elif "{axis}" in cmd:
                cmd = cmd.replace("{axis}", axis)
          elif "find-center" == cmd:
                self.app.tool_scripts.find_center()
                return True
          elif self.app.is_mist_on and btn == BUT_MPG:          # Toggle macro for mist ON/OFF regarding the actual state
                cmd = self.macrobut["macro14toggle"]
          elif self.app.is_flood_on and btn == BUT_STEP:         # Toggle macro for flood ON/OFF regarding the actual state
                cmd = self.macrobut["macro15toggle"]
          
          self.app.comms.write("{}\n".format(cmd))
          return True
        # macro button haven't default functions
        return False


    def _send_script(self, fn):
        try:
            with open(fn) as f:
                for line in f:
                    self.app.comms.write('{}'.format(line))

        except Exception:
            self.app.main_window.async_display("ERROR: File not found: {}".format(fn))


    def _run(self):
        self.app = App.get_running_app()
        self.load_macros()

        oneshotdebug = 0                                                                      # init var for display one time only Connected to HID... here for prevent : referenced before assignment
        oneshotdebug2 = 0                                                                     # init var for display one time only Failed to open HID...
        oneshotdebug3 = 0                                                                     # init var for display one time only Pendant i not powered
        oneshotdebug4 = 0                                                                     # init var for display one time only Failed to open HID...
        oneshotdebug5 = 0                                                                     # init var for display one time only Pendant i not powered

        while not self.quit:
            try:
                # Open a connection to the WHB04B
                if self.hid.open(self.vid, self.pid):
                    if oneshotdebug == 0:
                        oneshotdebug = 1                                                      # update var for display one time only Connected to HID...
                        oneshotdebug2 = 0                                                     # update var for display ont time only Failed to open HID...
                        Logger.info("WHB04B: Connected to HID device receptor %04X:%04X" % (self.vid, self.pid))
                        self.app.main_window.async_display("WHB04B - Connected to HID device receptor %04X:%04X" % (self.vid, self.pid))

                    axis_mode = 0x00                                                          # patch for init this var each time you connect to the device for prevent the stupid error : referenced before assignment
                    self.status = 0x00                                                        # patch for init this var each time you connect to the device for prevent the stupid error : referenced before assignment
                    self.clear_lcd()                                                          # when AXIS OFF all other buttons ignored 0x40 display RESET : not work because device does not read input data
                    self.app.bind(fro=self.update_fro)                                        # update pendant feed override from smoothie value if changed by smoothie

                    # Infinite loop to read data from the WHB04B when app is NOT connected so wait for connection and use subloop when connected
#####################################################################################################################################################################################
                    while not self.quit:
                        data = self.hid.recv(timeout=500)
                        if data is None:
                            Logger.debug("WHB04B: NONE DATA - {}".format(data))
                            self.app.main_window.async_display("WHB04B - NONE DATA - {}".format(data))  # never see this appening ??? what is the result and what is wanted for data None from HB04 ???
                            continue

                        size = len(data)                                                                # FULL SIZE RECEIVED 64 OR BUG ? Maybee try to cut and see what append
                        #self.app.main_window.async_display("WHB04B - DATA - {}".format(data))
                        #self.app.main_window.async_display("WHB04B - SIZE - {}".format(size))

                        if not self.app.is_connected:
                            self.clear_lcd()                                                            # when host not connected all buttons are ignored 0x40 display RESET on the pdt : not work because device does not read input data
                            #self.app.main_window.async_display("WHB04B - UNCONNECTED HOST to smoothie CLEAR LCD")
                            if data[2] == 0x01:
                                self.app.main_window.connect()                                          # pushe reset when unconnected ask smoopi for open serial port to smoothie : IndexError: list index out of range but work...
                            continue

                        if size == 0:
                            # start subloop here when do nothing but app is connected so refresh LCD with machine position
#####################################################################################################################################################################################
                            if axis_mode == 0x06:                                                # before patch at startup this var is not initialised and display this error
                                self.clear_lcd()                                                 # UnboundLocalError: local variable 'axis_mode' referenced before assignment
                                continue                                                         # when AXIS OFF all other buttons ignored 0x40 display RESET : not work because device does not read input data

                            if self.app.is_connected:
                                if self.f_ovr != self.app.fro:
                                    self.app.comms.write("M220 S{}\n".format(self.f_ovr))        # update smoothie feed override from pendant value if changed by pendant
                                #if self.s_ovr != self.app.sr:
                                #   self.app.comms.write("M221 S{}\n".format(self.s_ovr))        # not sure if this work only for extruder or temp or work also for spindle

                                if axis_mode > 0x10 and axis_mode < 0x14:
                                    self.setovr(self.f_ovr, self.s_ovr)
                                    self.setstatus(self.status)
                                    if self.status < 0x80:
                                        self.setwcs(self.app.wpos)                               # axis value for XYZ mode relative
                                    elif self.status >= 0x80:
                                          self.setmcs(self.app.mpos)                             # axis value for XYZ mode absolue
                                    self.update_lcd()
                                elif axis_mode > 0x13 and axis_mode < 0x17:
                                      self.clear_dro()                                           # clear DRO for ABC axis if less than 6 axis display 0.000
                                      self.setovr(self.f_ovr, self.s_ovr)
                                      self.setstatus(self.status)
                                      self.setmcs(self.app.mpos[3:6])                            # axis value for ABC only available mode absolue
                                      self.update_lcd()
                                elif axis_mode == 0x06:
                                      self.clear_lcd()                                           # when AXIS OFF all other buttons ignored 0x40 display RESET : not work because device does not read input data
                                elif axis_mode == 0x00:
                                      self.status = 0x00                                         # init mode for startup or after disconnecting host from smoothie : display CON
                                      self.setstatus(self.status)
                                      self.update_lcd()

                            continue
                            # end subloop here when do nothing but app is connected so refresh LCD with machine position
#####################################################################################################################################################################################

                            # here is the starting when data are received, whb04b send firstly the data with button pressed, and after send a data with button released
                            # for Axis and speed rotary knob the device send only the data without release button
                        if data[0] != 0x04:
                            Logger.error("WHB04B: Not an WHB04B HID packet")
                            self.app.main_window.async_display("WHB04B - data ERROR Not an WHB04B HID packet")
                            continue
                        elif oneshotdebug3 == 1:
                              oneshotdebug3 = 0                   # clear var here for reset debug state, used for display only one shot peandant not powered

                        seed = data[1]
                        btn_1 = data[2]
                        btn_2 = data[3]
                        speed_mode = data[4]
                        axis_mode = data[5]
                        wheel = self.twos_comp(data[6], 8)        # not really sure about what is ", 8" but without = not work
                        checksum = data[7]

                        axis = self.axislut[axis_mode]            # decode axis selected and load ASCII data for axis name

                        if axis_mode == 0x06:
                            self.clear_lcd()                      # when AXIS OFF all other buttons ignored 0x40 display RESET : not work because device does not read input data
                            self.app.main_window.async_display("WHB04B - AXIS OFF CLEAR LCD request by pendant")
                            continue

                        elif speed_mode == 0x1c:
                            self.status = 0x00                    # mode lead = move locked and after keep out from lead this mode are CON
                            self.setovr(self.f_ovr, self.s_ovr)   # or mode CON because we are out of lead and not in mpg or step or reset
                            self.setstatus(self.status)
                            self.update_lcd()
                            if oneshotdebug4 == 0:
                                oneshotdebug4 = 1
                                oneshotdebug5 = 0
                                self.app.main_window.async_display("WHB04B - LEAD MODE = Spindle override from Wheel")
                            #continue                             # Lead is not a momentary push button do not exit and restart loop from here !
                        elif self.status == 0x00 and speed_mode != 0x1c:
                              if oneshotdebug5 == 0:
                                  oneshotdebug5 = 1
                                  oneshotdebug4 = 0
                                  self.app.main_window.async_display("WHB04B - CON MODE = Feedrate override from Wheel")
                            #continue                             # Lead is not a momentary push button do not exit and restart loop from here !

                        if self.status == 0:
                           #Logger.debug("WHB04B: seed: {}, btn_1: {}, btn_2: {}, speed CON: {}, axis: {}, wheel: {}, checksum: {}".format(seed, btn_1, btn_2, self.conlut[speed_mode], self.axislut[axis_mode], wheel, checksum))
                           Logger.debug("WHB04B: btn_1: {}, btn_2: {}, speed CON: {}, axis: {}, wheel: {}".format(btn_1, btn_2, self.conlut[speed_mode], self.axislut[axis_mode], wheel))
                           #self.app.main_window.async_display("WHB04B: btn_1: {}, btn_2: {}, speed CON: {}, axis: {}, wheel: {}".format(btn_1, btn_2, self.conlut[speed_mode], self.axislut[axis_mode], wheel))
                        elif self.status == 1:
                           #Logger.debug("WHB04B: seed: {}, btn_1: {}, btn_2: {}, speed STEP: {}, axis: {}, wheel: {}, checksum: {}".format(seed, btn_1, btn_2, self.steplut[speed_mode], self.axislut[axis_mode], wheel, checksum))
                           Logger.debug("WHB04B: btn_1: {}, btn_2: {}, speed STEP: {}, axis: {}, wheel: {}".format(btn_1, btn_2, self.steplut[speed_mode], self.axislut[axis_mode], wheel))
                           #self.app.main_window.async_display("WHB04B: btn_1: {}, btn_2: {}, speed STEP: {}, axis: {}, wheel: {}".format(btn_1, btn_2, self.steplut[speed_mode], self.axislut[axis_mode], wheel))
                        elif self.status == 2:
                           #Logger.debug("WHB04B: seed: {}, btn_1: {}, btn_2: {}, speed MPG: {}, axis: {}, wheel: {}, checksum: {}".format(seed, btn_1, btn_2, self.mpglut[speed_mode], self.axislut[axis_mode], wheel, checksum))
                           Logger.debug("WHB04B: btn_1: {}, btn_2: {}, speed MPG: {}, axis: {}, wheel: {}".format(btn_1, btn_2, self.mpglut[speed_mode], self.axislut[axis_mode], wheel))
                           #self.app.main_window.async_display("WHB04B: btn_1: {}, btn_2: {}, speed MPG: {}, axis: {}, wheel: {}".format(btn_1, btn_2, self.mpglut[speed_mode], self.axislut[axis_mode], wheel))

                        # handle standard fixed buttons : available when gcode is running
                        if btn_1 != 0 and btn_1 != BUT_FN and self.handle_buttonrun(btn_1, axis):
                            continue

                        # handle standard fixed and as remapped buttons : not available when gcode is running
                        elif btn_1 != 0 and btn_1 != BUT_FN and self.handle_button(btn_1, axis) and not self.app.main_window.is_printing:
                            continue

                        # handle macro buttons : not available when gcode is running
                        elif btn_2 != 0 and btn_1 == BUT_FN and self.handle_buttonfn(btn_2, axis) and not self.app.main_window.is_printing:
                            continue

                        elif wheel != 0:
                            # must be one of XYZABC so send jogging command
                            # velocity_mode:
                            # step= -1 if wheel < 0 else 1
                            # s = -wheel if wheel < 0 else wheel
                            # if s > 5: s == 5 # seems the max realistic we get
                            # speed= s/5.0 # scale where 5 is max speed
                            step = wheel  # speed of wheel will move more increments rather than increase feed rate
                            if self.status == 2 and not self.app.main_window.is_printing:
                                dist = 0.001 * step * self.mpglut[speed_mode]    # mode mpg
                            elif self.status == 1 and not self.app.main_window.is_printing:
                               dist = self.steplut[speed_mode] * step            # mode step
                            elif self.status == 0 and speed_mode == 0x1c:
                               self.app.main_window.async_display("WHB04B - LEAD MODE = Spindle override from Wheel")
                               dist = 0                                          # mode lead = move locked
                               self.s_ovr += 1 * step * self.soverrange          # mode lead NOW = Spindle override activated after going out from lead mode
                               if self.s_ovr > self.sovermax:
                                   self.s_ovr = self.sovermax     
                               if self.s_ovr < self.sovermin:
                                   self.s_ovr = self.sovermin
                               self.setovr(self.f_ovr, self.s_ovr)
                            elif self.status == 0 and speed_mode != 0x1c:
                               self.app.main_window.async_display("WHB04B - CON MODE = Feedrate override from Wheel")
                               dist = 0
                               self.f_ovr += 1 * step * self.conlut[speed_mode]  # mode continu NOW = Feed override activated after go out from lead mode
                               if self.f_ovr > self.fovermax:
                                   self.f_ovr = self.fovermax     
                               if self.f_ovr < self.fovermin:
                                   self.f_ovr = self.fovermin
                               self.setovr(self.f_ovr, self.s_ovr)
                                                              

                            if dist != 0 and not self.app.main_window.is_printing:
                               speed = 1.0                                       # final check if mode lead = move skiped
                               self.app.comms.write("$J {}{} F{}\n".format(axis, dist, speed))
                               Logger.debug("$J {}{} F{}".format(axis, dist, speed))
                               dist = 0                                          # keep secure and reset dist each time

                            if axis_mode > 0x10 and axis_mode < 0x14:            # Update DRO when rotate wheel
                               if self.status < 0x80:
                                  self.setwcs(self.app.wpos)                     # axis value for XYZ
                               elif self.status >= 0x80:
                                  self.setmcs(self.app.mpos)                     # axis value for XYZ
                            elif axis_mode > 0x13 and axis_mode < 0x17:
                               self.clear_dro()                                  # clear DRO for ABC axis if less than 6 axis display 0.000
                               self.setmcs(self.app.mpos[3:6])                   # axis value for ABC
                            
                            self.update_lcd()

                    # Close the WHB04B connection
                    self.hid.close()                                             # never see this appening code keeped from HB04 ???
                    Logger.info("WHB04B: Disconnected from HID device")
                    self.app.main_window.async_display("WHB04B - Disconnected from HID device")

                else:
                    if oneshotdebug2 == 0:
                        oneshotdebug2 = 1                                        # update var for display ont time only Failed to open HID...
                        oneshotdebug = 0                                         # reset var for display one time only Connected to HID...
                        Logger.info("WHB04B: Failed to open HID device %04X:%04X" % (self.vid, self.pid))
                        self.app.main_window.async_display("WHB04B - Failed to open HID device %04X:%04X" % (self.vid, self.pid))


            except Exception:
                if oneshotdebug3 == 0:
                    d = traceback.format_exc()
                    if self.app.is_connected and ('KeyError: 0' or 'IndexError: list') in d:
                        oneshotdebug3 = 1                                        # update var for display one time only Pendant i not powered
                        Logger.debug("WHB04B: Pendant is not powered")
                        self.app.main_window.async_display("WHB04B - Pendant is not powered")
                    elif self.app.is_connected:
                          oneshotdebug3 = 0                                      # reset var here for display each needed time the exception error
                          Logger.error("WHB04B: Pendant Exception - {}".format(traceback.format_exc()))
                          self.app.main_window.async_display("WHB04B - Pendant Exception - {}".format(traceback.format_exc()))

                if self.hid.opened:
                    self.hid.close()

            self.app.unbind(fro=self.update_fro)                                 # stop update pendant feed override from smoothie value if changed by smoothie

            if not self.quit:
                time.sleep(5)                                                    # retry connection in 5 seconds unless we were asked to quit

    # converts a 16 bit value to little endian bytes suitable for WHB04B protocol
    def to_le(self, x, neg=False):
        lo = abs(x) & 0xFF
        hi = (abs(x) >> 8) & 0xFF
        if neg:
            hi |= 0x80
        return (lo, hi)

    def _setv(self, off, a):
        self.lock.acquire()
        for v in a:
            (f, i) = math.modf(v)      # split into fraction and integer
            f = int(round(f * 10000))  # we only need 3dp
            (l, h) = self.to_le(int(i))
            self.lcd_data[off] = l
            self.lcd_data[off + 1] = h
            (l, h) = self.to_le(f, v < 0)
            self.lcd_data[off + 2] = l
            self.lcd_data[off + 3] = h
            off += 4
        self.lock.release()

    def setstatus(self, m):
        self.lock.acquire()
        if self.app.status == 'Alarm':
            self.lcd_data[3] = 0x40    # if Alarm/Kill display RESET but keep DRO value
        else:
            self.lcd_data[3] = m
        self.lock.release()

    def setwcs(self, a):
        self._setv(4, a)

    def setmcs(self, a):
        self._setv(4, a)

    def setovr(self, f, s):
        (l, h) = self.to_le(int(round(f)))
        self.lock.acquire()
        self.lcd_data[16] = l
        self.lcd_data[17] = h
        (l, h) = self.to_le(int(round(s)))
        self.lcd_data[18] = l
        self.lcd_data[19] = h
        self.lock.release()

    def update_lcd(self):
        self.lock.acquire()
        n = self.hid.write(self.lcd_data)
        self.lock.release()
        #Logger.debug("Sent {} out of {}".format(n, len(self.lcd_data)))
        #Logger.debug("LCD update {}".format(self.lcd_data))
        #self.app.main_window.async_display("WHB04B - LCD update {}".format(self.lcd_data))

    def clear_lcd(self):
        self.lock.acquire()
        self.lcd_data[3] = 0x40             # status 0x40 = RESET and clear DRO value
        self.lcd_data[4] = 0
        self.lcd_data[5] = 0
        self.lcd_data[6] = 0
        self.lcd_data[7] = 0
        self.lcd_data[8] = 0
        self.lcd_data[9] = 0
        self.lcd_data[10] = 0
        self.lcd_data[11] = 0
        self.lcd_data[12] = 0
        self.lcd_data[13] = 0
        self.lcd_data[14] = 0
        self.lcd_data[15] = 0
        self.lcd_data[16] = 0
        self.lcd_data[17] = 0
        self.lcd_data[18] = 0
        self.lcd_data[19] = 0
        n = self.hid.write(self.lcd_data)
        self.lock.release()

    def clear_dro(self):
        self.lock.acquire()
        self.lcd_data[4] = 0
        self.lcd_data[5] = 0
        self.lcd_data[6] = 0
        self.lcd_data[7] = 0
        self.lcd_data[8] = 0
        self.lcd_data[9] = 0
        self.lcd_data[10] = 0
        self.lcd_data[11] = 0
        self.lcd_data[12] = 0
        self.lcd_data[13] = 0
        self.lcd_data[14] = 0
        self.lcd_data[15] = 0
        self.lock.release()

    def update_fro(self, i, v):
#        self.s_ovr = i
        self.f_ovr = v                      # update pendant feed override from smoothie value if changed by smoothie
        self.setovr(self.f_ovr, self.s_ovr)
