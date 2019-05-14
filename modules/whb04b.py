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
            Logger.debug("WHB04BHID: No matching device found")
            return None

        if len(devices) > 1:
            Logger.debug("WHB04BHID: more than one device found: {}".format(devices))
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
    # @plen     - Number of bytes to read. Defaults to PACKET_LEN.
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
        n += self.hid.send_feature_report(data[0:8], 0x07)
        n += self.hid.send_feature_report(data[8:16], 0x07)
        n += self.hid.send_feature_report(data[16:24], 0x07)
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
#BUT_FN = 12
BUT_PROBEZ = 13
BUT_MPG = 14
BUT_STEP = 15
BUT_MACRO10 = 16


class WHB04B():
    lcd_data = [
        0xFE, 0xFD, 1, # id + seed
        0,           # Status
        0, 0, 0, 0,  # X WC
        0, 0, 0, 0,  # Y WC
        0, 0, 0, 0,  # Z WC
        0, 0,        # F ovr
        0, 0,        # S ovr
        0, 0, 0, 0,  # padding
    ]
    
    lock = threading.RLock()
    # button look up table
    
#        12: "fn",

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

    alut = {0x06: 'OFF', 0x11: 'X', 0x12: 'Y', 0x13: 'Z', 0x14: 'A', 0x15: 'B', 0x16: 'C'} # button off + set Axis
    slut = {0x0d: '0.001', 0x0e: '0.01', 0x0f: '0.1', 0x10: '1', 0x1a: '0', 0x1b: '0', 0x1c: '0'} # button for set step multiplier
    mlut = {0x0d: '2', 0x0e: '5', 0x0f: '10', 0x10: '30', 0x1a: '60', 0x1b: '100', 0x1c: '0'} # button for set mpg %
    llut = {0x0d: '0', 0x0e: '0', 0x0f: '0', 0x10: '0', 0x1a: '0', 0x1b: '0', 0x1c: '0.001'} # button for set lead mode
    mul = 1
    status = 1
   # mullut = {0x00: 0, 0x01: 1, 0x02: 5, 0x03: 10, 0x04: 20, 0x05: 30, 0x06: 40, 0x07: 50, 0x08: 100, 0x09: 500, 0x0A: 1000}
    macrobut = {}
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
#            self.mul = config.getint("defaults", "multiplier", fallback=8)

        except Exception as err:
            Logger.warning('WHB04B: WARNING - exception parsing config file: {}'.format(err))

    def handle_button(self, btn, axis):
        name = self.butlut[btn]

        if(name in self.macrobut):
            # use redefined macro
            cmd = self.macrobut[name]
            if "{axis}" in cmd:
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
#        elif btn == BUT_FEEDP:
#            # adjust feed override
#            self.f_ovr += 1
#            if self.f_ovr < 10:
#                self.f_ovr = 10
#            self.setovr(self.f_ovr, self.s_ovr)
##            self.update_lcd()
#        elif btn == BUT_FEEDM:
#            # adjust feed override
#            self.f_ovr -= 1
#            if self.f_ovr < 10:
#                self.f_ovr = 10
#            self.setovr(self.f_ovr, self.s_ovr)
##            self.update_lcd()
#        elif btn == BUT_SPINDLEP:
#            # adjust S override, laser power? (TODO maybe this is tool speed?)
#            self.s_ovr += 100
#            if self.s_ovr < 1:
#                self.s_ovr = 1
#            self.setovr(self.f_ovr, self.s_ovr)
##            self.update_lcd()
#        elif btn == BUT_SPINDLEM:
#            # adjust S override, laser power? (TODO maybe this is tool speed?)
#            self.s_ovr -= 100
#            if self.s_ovr < 1:
#                self.s_ovr = 1
#            self.setovr(self.f_ovr, self.s_ovr)
##            self.update_lcd()
        elif btn == BUT_START:
            # TODO if running then pause
            self.app.main_window.start_last_file()

        if cmd:
            self.app.comms.write("{}\n".format(cmd))
            return True

        return False

    def handle_buttonfn(self, btn2, axis):
        name = self.butlutfn[btn2]

        if(name in self.macrobut):
            # use redefined macro
            cmd = self.macrobut[name]
            if "{axis}" in cmd:
                cmd = cmd.replace("{axis}", axis)
            elif "find-center" == cmd:
                self.app.tool_scripts.find_center()
                return True

            self.app.comms.write("{}\n".format(cmd))
            return True

        # macro button dont have default functions
        cmd = None
        
        return False




    def _run(self):
        self.app = App.get_running_app()
        self.load_macros()

        while not self.quit:
            try:
                # Open a connection to the WHB04B
                if self.hid.open(self.vid, self.pid):

                    Logger.info("WHB04B: Connected to HID device %04X:%04X" % (self.vid, self.pid))

#                    # setup LCD with current settings
#                    self.setwcs(self.app.wpos)
##                    self.setmcs(self.app.mpos[0:3])
#                    self.setovr(self.f_ovr, self.s_ovr)
##                    self.setfs(self.app.frr, self.app.sr)
##                    self.setmul(self.mul)
#                    self.setstatus(self.status)
#                    self.update_lcd()

                    # get notified when these change
#                    self.app.bind(wpos=self.update_wpos)
##                    self.app.bind(mpos=self.update_mpos)
#                    self.app.bind(fro=self.update_fro)

                    # Infinite loop to read data from the WHB04B
                    while not self.quit:
                        data = self.hid.recv(timeout=1000)
                        if data is None:
                            continue

                        size = len(data)
                        if size == 0:
                            # timeout
                            if self.app.is_connected:
                                if self.f_ovr != self.app.fro:
                                    self.app.comms.write("M220 S{}".format(self.f_ovr))
                                if self.s_ovr != self.app.sr:
                                     self.app.comms.write("M221 S{}".format(self.s_ovr));
#                                self.refresh_lcd()
                            continue

                        if data[0] != 0x04:
                            Logger.error("WHB04B: Not an WHB04B HID packet")
                            continue

#                        unused = data[1]
                        btn_1 = data[2]
                        btn_2 = data[3]
                        speed_mode = data[4]
                        axis_mode = data[5]
                        wheel = self.twos_comp(data[6], 8)
#                        checksum = data[7]
                        Logger.debug("whb04b: btn_1: {}, btn_2: {}, speed: {}, axis: {}, wheel: {}".format(btn_1, btn_2, self.slut[speed_mode], self.alut[axis_mode], wheel))
         
                        # only select rotary mode buttons
                        if btn_1 == BUT_STEP:
                            #self.mul += 1
                            #if self.mul > 10:
                            #    self.mul = 1
                            #self.setmul(self.mul)
                            # TODO create MASK xxxxxx??
                            self.status = 1
                            self.setstatus(self.status)
#                            self.update_lcd()
                            continue

                        if btn_1 == BUT_MPG:
                            #self.mul -= 1
                            #if self.mul < 1:
                            #    self.mul = 10
                            #self.setmul(self.mul)
                            # TODO create MASK xxxxxx??
                            self.status = 2
                            self.setstatus(self.status)
#                            self.update_lcd()
                            continue

                        if not self.app.is_connected:
                            continue

                        if btn_1 == BUT_STOP and self.app.status != 'Alarm':
                            self.app.comms.write('\x18')
                            continue

                        if btn_1 == BUT_RESET and self.app.status == 'Alarm':
                            self.app.comms.write('$X\n')
                            continue

                        # dont do jogging etc if printing unless we are suspended
                        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
                            continue

                        if axis_mode == 6:
                            # when OFF all other buttons are ignored
                            continue

                        axis = self.alut[axis_mode]   
                        f_over = self.f_ovr
                        s_over = self.s_ovr
#                        f_over = self.slut[speed_mode]

                        # handle other fixed and macro buttons
                        if btn_1 != 0 and btn_1 != 12 and self.handle_button(btn_1, axis):
                            continue
                            
                        # handle other fixed and macro buttons
                        if btn_2 != 0 and btn_1 == 12 and self.handle_buttonfn(btn_2, axis):
                            continue

                        if wheel != 0:
#                            if axis == 'F':
#                                # adjust feed override
#                                self.f_ovr += wheel
#                                if self.f_ovr < 10:
#                                    self.f_ovr = 10
#                                self.setovr(self.f_ovr, self.s_ovr)
#                                self.update_lcd()
#                                continue
#                            if axis == 'S':
#                                # adjust S override, laser power? (TODO maybe this is tool speed?)
#                                self.s_ovr += wheel
#                                if self.s_ovr < 1:
#                                    self.s_ovr = 1
#                                self.setovr(self.f_ovr, self.s_ovr)
#                                self.update_lcd()
#                                continue

                            # must be one of XYZABC so send jogging command
                            # velocity_mode:
                            # step= -1 if wheel < 0 else 1
                            # s = -wheel if wheel < 0 else wheel
                            # if s > 5: s == 5 # seems the max realistic we get
                            # speed= s/5.0 # scale where 5 is max speed
                            step = wheel  # speed of wheel will move more increments rather than increase feed rate
#                            dist = 0.001 * step * self.slut[self.speed_mode]
#                            dist = 0.001 * step * self.slut[speed_mode]
                            dist = 0.001 * step * self.mlut[speed_mode]
                            speed = 1.0
                            self.app.comms.write("$J {}{} F{}\n".format(axis, dist, speed))
                            Logger.debug("$J {}{} F{}\n".format(axis, dist, speed))

                    # Close the WHB04B connection
                    self.hid.close()

                    Logger.info("WHB04B: Disconnected from HID device")

                else:
                    Logger.debug("whb04b: Failed to open HID device %04X:%04X" % (self.vid, self.pid))

            except Exception:
                Logger.error("WHB04B: Exception - {}".format(traceback.format_exc()))
                if self.hid.opened:
                    self.hid.close()

#            self.app.unbind(wpos=self.update_wpos)
##            self.app.unbind(mpos=self.update_mpos)
#            self.app.unbind(fro=self.update_fro)
            if not self.quit:
                # retry connection in 5 seconds unless we were asked to quit
                time.sleep(5)

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
            (f, i) = math.modf(v)  # split into fraction and integer
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
        self.lcd_data[3] = m
        self.lock.release()
          
    def setwcs(self, a):
        self._setv(4, a)

#    def setmcs(self, a):
#        self._setv(15, a)

    def setovr(self, f, s):
        (l, h) = self.to_le(int(round(f)))
        self.lock.acquire()
        self.lcd_data[16] = l
        self.lcd_data[17] = h
        (l, h) = self.to_le(int(round(s)))
        self.lcd_data[18] = l
        self.lcd_data[19] = h
        self.lock.release()

#    def setfs(self, f, s):
#        (l, h) = self.to_le(int(round(f)))
#        self.lock.acquire()
#        self.lcd_data[31] = l
#        self.lcd_data[32] = h
#        (l, h) = self.to_le(int(round(s)))
#        self.lcd_data[33] = l
#        self.lcd_data[34] = h
#        self.lock.release()

#    def setmul(self, m):
#        self.lock.acquire()
#        self.lcd_data[2] = m
#        self.lock.release()


#    def setinch(self, b):
#        self.lock.acquire()
#        self.lcd_data[36] = 0x80 if b else 0x00
#        self.lock.release()

    def update_lcd(self):
        self.lock.acquire()
        n = self.hid.write(self.lcd_data)
        self.lock.release()
        Logger.debug("Sent {} out of {}".format(n, len(self.lcd_data)))
        Logger.debug("LCD {}".format(self.lcd_data))

    def refresh_lcd(self):
#        self.setfs(self.app.frr, self.app.sr)
#        if self.app.status == "Run":
#            self.setmul(self.mul | 0x60)
#        elif self.app.status == "Home":
#            self.setmul(self.mul | 0x50)
#        elif self.app.status == "Alarm":
#            self.setmul(self.mul | 0x20)
#        else:
#            self.setmul(self.mul)

#        self.setinch(self.app.is_inch)
        self.update_lcd()

    def update_wpos(self, i, v):
        self.setwcs(v)
        self.update_lcd()

#    def update_mpos(self, i, v):
#        self.setmcs(v[0:3])
#        self.update_lcd()

    def update_fro(self, i, v):
        self.f_ovr = v
        self.setovr(self.f_ovr, self.s_ovr)
