# implements interface  for the HB04 USB pendant

from easyhid import Enumeration
from kivy.logger import Logger
from kivy.app import App

import threading
import traceback
import math
import configparser
import time

hb04 = None


def start(args=""):
    global hb04
    # print("start with args: {}".format(args))
    pid, vid = args.split(':')
    hb04 = HB04(int(pid, 16), int(vid, 16))
    hb04.start()
    return True


def stop():
    global hb04
    hb04.stop()


class HB04HID:
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
            Logger.debug("HB04HID: No matching device found")
            return None

        if len(devices) > 1:
            Logger.debug("HB04HID: more than one device found: {}".format(devices))
            return None

        # open the device
        self.hid = devices[0]
        self.hid.open()

        Logger.debug("HB04HID: Opened: {}".format(self.hid.description()))
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
    # @len     - Number of bytes to read. Defaults to PACKET_LEN.
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
        n += self.hid.send_feature_report(data[21:28], 0x06)
        n += self.hid.send_feature_report(data[28:35], 0x06)
        n += self.hid.send_feature_report(data[35:42], 0x06)
        return n


# button definitions
BUT_NONE = 0
BUT_RESET = 23
BUT_STOP = 22
BUT_ORIGIN = 1
BUT_START = 2
BUT_REWIND = 3
BUT_PROBEZ = 4
BUT_SPINDLE = 12
BUT_HALF = 6
BUT_ZERO = 7
BUT_SAFEZ = 8
BUT_HOME = 9
BUT_MACRO1 = 10
BUT_MACRO2 = 11
BUT_MACRO3 = 5
BUT_MACRO6 = 15
BUT_MACRO7 = 16
BUT_STEP = 13
BUT_MPG = 14


class HB04():
    lcd_data = [
        0xFE, 0xFD, 1,
        0, 0, 0, 0,  # X WC
        0, 0, 0, 0,  # Y WC
        0, 0, 0, 0,  # Z WC
        0, 0, 0, 0,  # X MC
        0, 0, 0, 0,  # Y MC
        0, 0, 0, 0,  # Z MC
        0, 0,        # F ovr
        0, 0,        # S ovr
        0, 0,        # F
        0, 0,        # S
        0x01,        # step mul
        0,           # inch/mm
        0, 0, 0, 0, 0   # padding
    ]

    lock = threading.RLock()
    # button look up table
    butlut = {
        1: "origin",
        2: "start",
        3: "rewind",
        4: "probez",
        5: "macro3",
        6: "half",
        7: "zero",
        8: "safez",
        9: "home",
        10: "macro1",
        11: "macro2",
        12: "spindle",
        15: "macro6",
        16: "macro7",
    }

    alut = {0: 'off', 0x11: 'X', 0x12: 'Y', 0x13: 'Z', 0x18: 'A', 0x15: 'F', 0x14: 'S'}
    mul = 1
    mullut = {0x00: 0, 0x01: 1, 0x02: 5, 0x03: 10, 0x04: 20, 0x05: 30, 0x06: 40, 0x07: 50, 0x08: 100, 0x09: 500, 0x0A: 1000}
    macrobut = {}
    f_ovr = 100
    s_ovr = 100

    def __init__(self, vid, pid):
        # HB04 vendor ID and product ID
        self.vid = vid
        self.pid = pid
        self.hid = HB04HID()

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
            config.read('hb04.ini')
            # load user defined macro buttons
            for (key, v) in config.items('macros'):
                self.macrobut[key] = v

            # load any default settings
            self.mul = config.getint("defaults", "multiplier", fallback=8)

        except Exception as err:
            Logger.warning('HB04: WARNING - exception parsing config file: {}'.format(err))

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
        if btn == BUT_HOME:
            cmd = "$H"
        elif btn == BUT_ORIGIN:
            cmd = "G90 G0 X0 Y0"
        elif btn == BUT_PROBEZ:
            cmd = "G38.3 Z-25"
        elif btn == BUT_ZERO:
            cmd = "G10 L20 P0 {}0".format(axis)
        elif btn == BUT_SAFEZ:
            cmd = "G91 G0 Z20 G90"
        elif btn == BUT_SPINDLE:
            cmd = "M5" if self.app.is_spindle_on else "M3"
        elif btn == BUT_HALF:
            cmd = "G10 L20 P0 {}{}".format(axis, self.app.wpos[ord(axis) - ord('X')] / 2.0)
        elif btn == BUT_START:
            # TODO if running then pause
            self.app.main_window.start_last_file()
            return True

        if cmd:
            self.app.comms.write("{}\n".format(cmd))
            return True

        return False

    def _run(self):
        self.app = App.get_running_app()
        self.load_macros()

        while not self.quit:
            try:
                # Open a connection to the HB04
                if self.hid.open(self.vid, self.pid):

                    Logger.info("HB04: Connected to HID device %04X:%04X" % (self.vid, self.pid))

                    # setup LCD with current settings
                    self.setwcs(self.app.wpos)
                    self.setmcs(self.app.mpos[0:3])
                    self.setovr(self.f_ovr, self.s_ovr)
                    self.setfs(self.app.frr, self.app.sr)
                    self.setmul(self.mul)
                    self.update_lcd()

                    # get notified when these change
                    self.app.bind(wpos=self.update_wpos)
                    self.app.bind(mpos=self.update_mpos)
                    self.app.bind(fro=self.update_fro)

                    # Infinite loop to read data from the HB04
                    while not self.quit:
                        data = self.hid.recv(timeout=1000)
                        if data is None:
                            continue

                        size = len(data)
                        if size == 0:
                            # timeout
                            if self.app.is_connected:
                                if self.f_ovr != self.app.fro:
                                    self.app.comms.write("M220 S{}\n".format(self.f_ovr))
                                # if self.s_ovr != self.app.sr:
                                #     self.app.comms.write("M221 S{}\n".format(self.s_ovr));
                                self.refresh_lcd()
                            continue

                        if data[0] != 0x04:
                            Logger.error("HB04: Not an HB04 HID packet")
                            continue

                        btn_1 = data[1]
                        btn_2 = data[2]
                        wheel_mode = data[3]
                        wheel = self.twos_comp(data[4], 8)
                        xor_day = data[5]
                        Logger.debug("HB04: btn_1: {}, btn_2: {}, mode: {}, wheel: {}".format(btn_1, btn_2, self.alut[wheel_mode], wheel))

                        # handle move multiply buttons
                        if btn_1 == BUT_STEP:
                            self.mul += 1
                            if self.mul > 10:
                                self.mul = 1
                            self.setmul(self.mul)
                            self.update_lcd()
                            continue

                        if btn_1 == BUT_MPG:
                            self.mul -= 1
                            if self.mul < 1:
                                self.mul = 10
                            self.setmul(self.mul)
                            self.update_lcd()
                            continue

                        if not self.app.is_connected:
                            continue

                        if btn_1 == BUT_STOP and self.app.status != 'Alarm':
                            self.app.comms.write('\x18')
                            continue

                        if btn_1 == BUT_RESET and self.app.status == 'Alarm':
                            self.app.comms.write('$X\n')
                            continue

                        # don't do jogging etc if printing unless we are suspended
                        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
                            continue

                        if wheel_mode == 0:
                            # when OFF all other buttons are ignored
                            continue

                        axis = self.alut[wheel_mode]

                        # handle other fixed and macro buttons
                        if btn_1 != 0 and self.handle_button(btn_1, axis):
                            continue

                        if wheel != 0:
                            if axis == 'F':
                                # adjust feed override
                                self.f_ovr += wheel
                                if self.f_ovr < 10:
                                    self.f_ovr = 10
                                self.setovr(self.f_ovr, self.s_ovr)
                                self.update_lcd()
                                continue
                            if axis == 'S':
                                # adjust S override, laser power? (TODO maybe this is tool speed?)
                                self.s_ovr += wheel
                                if self.s_ovr < 1:
                                    self.s_ovr = 1
                                self.setovr(self.f_ovr, self.s_ovr)
                                self.update_lcd()
                                continue

                            # must be one of XYZA so send jogging command
                            # velocity_mode:
                            # step= -1 if wheel < 0 else 1
                            # s = -wheel if wheel < 0 else wheel
                            # if s > 5: s == 5 # seems the max realistic we get
                            # speed= s/5.0 # scale where 5 is max speed
                            step = wheel  # speed of wheel will move more increments rather than increase feed rate
                            dist = 0.001 * step * self.mullut[self.mul]
                            speed = 1.0
                            self.app.comms.write("$J {}{} F{}\n".format(axis, dist, speed))
                            # print("$J {}{} F{}\n".format(axis, dist, speed))

                    # Close the HB04 connection
                    self.hid.close()

                    Logger.info("HB04: Disconnected from HID device")

                else:
                    Logger.debug("HB04: Failed to open HID device %04X:%04X" % (self.vid, self.pid))

            except Exception:
                Logger.error("HB04: Exception - {}".format(traceback.format_exc()))
                if self.hid.opened:
                    self.hid.close()

            self.app.unbind(wpos=self.update_wpos)
            self.app.unbind(mpos=self.update_mpos)
            self.app.unbind(fro=self.update_fro)
            if not self.quit:
                # retry connection in 5 seconds unless we were asked to quit
                time.sleep(5)

    # converts a 16 bit value to little endian bytes suitable for HB04 protocol
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

    def setwcs(self, a):
        self._setv(3, a)

    def setmcs(self, a):
        self._setv(15, a)

    def setovr(self, f, s):
        (l, h) = self.to_le(int(round(f)))
        self.lock.acquire()
        self.lcd_data[27] = l
        self.lcd_data[28] = h
        (l, h) = self.to_le(int(round(s)))
        self.lcd_data[29] = l
        self.lcd_data[30] = h
        self.lock.release()

    def setfs(self, f, s):
        (l, h) = self.to_le(int(round(f)))
        self.lock.acquire()
        self.lcd_data[31] = l
        self.lcd_data[32] = h
        (l, h) = self.to_le(int(round(s)))
        self.lcd_data[33] = l
        self.lcd_data[34] = h
        self.lock.release()

    def setmul(self, m):
        self.lock.acquire()
        self.lcd_data[35] = m
        self.lock.release()

    def setinch(self, b):
        self.lock.acquire()
        self.lcd_data[36] = 0x80 if b else 0x00
        self.lock.release()

    def update_lcd(self):
        self.lock.acquire()
        n = self.hid.write(self.lcd_data)
        self.lock.release()
        # print("Sent {} out of {}".format(n, len(lcd_data)))

    def refresh_lcd(self):
        self.setfs(self.app.frr, self.app.sr)
        if self.app.status == "Run":
            self.setmul(self.mul | 0x60)
        elif self.app.status == "Home":
            self.setmul(self.mul | 0x50)
        elif self.app.status == "Alarm":
            self.setmul(self.mul | 0x20)
        else:
            self.setmul(self.mul)

        self.setinch(self.app.is_inch)
        self.update_lcd()

    def update_wpos(self, i, v):
        self.setwcs(v)
        self.update_lcd()

    def update_mpos(self, i, v):
        self.setmcs(v[0:3])
        self.update_lcd()

    def update_fro(self, i, v):
        self.f_ovr = v
        self.setovr(self.f_ovr, self.s_ovr)
