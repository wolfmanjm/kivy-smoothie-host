# implements interface  for the HB04 USB pendant

from easyhid import Enumeration
from kivy.logger import Logger
from kivy.app import App

import threading
import traceback
import math
import configparser
import time
import ctypes as ctypes

hb04 = None


def start(args=""):
    global hb04
    # print("start with args: {}".format(args))
    pid, vid = args.split(':')
    hb04 = WHB04B(int(pid, 16), int(vid, 16))
    hb04.start()
    return True


def stop():
    global hb04
    hb04.stop()


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
        return n


# button definitions
BUT_NONE = 0
BUT_RESET = 1
BUT_STOP = 2
BUT_START = 3
BUT_STEP = 15
BUT_CONT = 14
BUT_MACRO1 = 4
BUT_MACRO2 = 5
BUT_MACRO3 = 6
BUT_MACRO4 = 7
BUT_MACRO5 = 8
BUT_MACRO6 = 9
BUT_MACRO7 = 10
BUT_MACRO8 = 11
BUT_MACRO9 = 13
BUT_MACRO10 = 16

# Fn pressed (btn_1)
BUT_FN = 12
# btn_2
BUT_FEEDP = 4
BUT_FEEDM = 5
BUT_SPINP = 6
BUT_SPINM = 7
BUT_HOME = 8
BUT_SAFEZ = 9
BUT_ORIGIN = 10
BUT_SPINDLE = 11
BUT_PROBEZ = 13


class Whb04b_struct(ctypes.Structure):
    buff_old = 'buff_old'
    _fields_ = [   # /* header of our packet */
                   ("header", ctypes.c_uint16, ),
                   ("seed", ctypes.c_uint8),
                   ("flags", ctypes.c_uint8),
                   # /* work pos */
                   ("x_wc_int", ctypes.c_uint16),
                   ("x_wc_frac", ctypes.c_uint16),
                   ("y_wc_int", ctypes.c_uint16),
                   ("y_wc_frac", ctypes.c_uint16),
                   ("z_wc_int", ctypes.c_uint16),
                   ("z_wc_frac", ctypes.c_uint16),
                   # /* speed */
                   ("feedrate", ctypes.c_uint16),
                   ("sspeed", ctypes.c_uint16),
                   ("padding", ctypes.c_uint8 * 4)]


class WHB04B():
    lcd_data = Whb04b_struct()

    mcs_mode = False
    reset_mode = False

    lock = threading.RLock()
    # button look up table
    butlut = {
        BUT_MACRO1: 'macro1',
        BUT_MACRO2: 'macro2',
        BUT_MACRO3: 'macro3',
        BUT_MACRO4: 'macro4',
        BUT_MACRO5: 'macro5',
        BUT_MACRO6: 'macro6',
        BUT_MACRO7: 'macro7',
        BUT_MACRO8: 'macro8',
        BUT_MACRO9: 'macro9',
        BUT_MACRO10: 'macro10',
    }

    axislut = {6: 'off', 17: 'X', 18: 'Y', 19: 'Z', 20: 'A', 21: 'B', 22: 'C'}
    steplut = {13: 0.001, 14: 0.01, 15: 0.1, 16: 1.0, 26: 1.0, 27: 1.0}
    contlut = {13: 2, 14: 5, 15: 10, 16: 30, 26: 60, 27: 100}
    macrobut = {}
    f_ovr = 100
    s_ovr = 100
    f_inc = 10
    s_inc = 10
    safe_z = 10
    continuous_mode = False
    mpg_mode = False

    def __init__(self, vid, pid):
        # WHB04B vendor ID and product ID
        self.vid = vid
        self.pid = pid
        self.hid = WHB04BHID()
        self.lcd_data.header = 0xFDFE
        self.lcd_data.seed = 0xFE

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
            self.f_inc = config.getint("defaults", "feed_inc", fallback=10)
            self.s_inc = config.getint("defaults", "speed_inc", fallback=10)
            self.safe_z = config.getint("defaults", "safe_z", fallback=20)

        except Exception as err:
            Logger.warning('WHB04B: WARNING - exception parsing config file: {}'.format(err))

    def handle_button(self, btn1, btn2, axis):
        Logger.debug('WHB04B: handle_button: {}, {}, {}'.format(btn1, btn2, axis))
        handled = False
        # mode switching
        if btn1 == BUT_STEP:
            self.continuous_mode = False
            self.mpg_mode = False
            handled = True
        elif btn1 == BUT_CONT:
            self.continuous_mode = True
            self.mpg_mode = False
            handled = True
        elif btn1 == BUT_FN and btn2 == BUT_CONT:
            self.mpg_mode = True
            self.continuous_mode = False
            handled = True
        elif btn1 == BUT_FN and btn2 == BUT_MACRO10:
            self.mcs_mode = not self.mcs_mode
            self._setv(self.app.mpos[0:3] if self.mcs_mode else self.app.wpos)
            handled = True
        elif btn1 == BUT_START:
            # if already running then it will pause
            self.app.main_window.start_last_file()
            return True
        elif btn1 == BUT_STOP and self.app.status != 'Alarm':
            self.app.comms.write('\x18')
            handled = True
        elif btn1 == BUT_RESET and self.app.status == 'Alarm':
            self.app.comms.write('$X\n')
            handled = True

        if handled:
            self.update_lcd()
            return True

        if btn1 != BUT_FN:
            if btn1 in self.butlut:
                # macro button
                name = self.butlut[btn1]

                if(name in self.macrobut):
                    # use defined macro
                    cmd = self.macrobut[name]
                    if "{axis}" in cmd:
                        cmd = cmd.replace("{axis}", axis)
                    elif "set-axis-half" == cmd:
                        cmd = "G10 L20 P0 {}{}".format(axis, self.app.wpos[ord(axis) - ord('X')] / 2.0)
                    elif "find-center" == cmd:
                        self.app.tool_scripts.find_center()
                        cmd = None

                    if cmd:
                        self.app.comms.write("{}\n".format(cmd))
                    return True

        else:
            btn = btn2
            # buttons that have hard coded functions when Fn button is down
            cmd = None
            if btn == BUT_HOME:
                cmd = "$H"
            elif btn == BUT_ORIGIN:
                cmd = "G90 G0 X0 Y0"
            elif btn == BUT_PROBEZ:
                cmd = "G38.3 Z-25"
            elif btn == BUT_SAFEZ:
                cmd = "G91 G0 Z{} G90".format(self.safe_z)
            elif btn == BUT_SPINDLE:
                cmd = "M5" if self.app.is_spindle_on else "M3"
            elif btn == BUT_FEEDP or btn == BUT_FEEDM:
                inc = self.f_inc if btn == BUT_FEEDP else -self.f_inc
                self.f_ovr += inc
                if self.f_ovr < 1:
                    self.f_ovr = 1
                self.setovr(self.f_ovr, self.s_ovr)
                self.update_lcd()
                return True
            elif btn == BUT_SPINP or btn == BUT_SPINM:
                inc = self.s_inc if btn == BUT_SPINP else -self.s_inc
                self.s_ovr += inc
                if self.s_ovr < 1:
                    self.s_ovr = 1
                self.setovr(self.f_ovr, self.s_ovr)
                self.update_lcd()
                return True

            if cmd:
                self.app.comms.write("{}\n".format(cmd))
                return True

        return False

    def _run(self):
        self.app = App.get_running_app()
        self.load_macros()
        contdir = None

        while not self.quit:
            try:
                # Open a connection to the WHB04B
                if self.hid.open(self.vid, self.pid):

                    Logger.info("WHB04B: Connected to HID device %04X:%04X" % (self.vid, self.pid))

                    # setup LCD with current settings
                    self._setv(self.app.wpos)
                    self.setovr(self.f_ovr, self.s_ovr)
                    self.update_lcd()

                    # get notified when these change
                    self.app.bind(wpos=self.update_wpos)
                    self.app.bind(mpos=self.update_mpos)
                    self.app.bind(fro=self.update_fro)

                    data_old = -1
                    # Infinite loop to read data from the WHB04B
                    while not self.quit:
                        data = self.hid.recv(timeout=1000)
                        if data is None:
                            continue

                        size = len(data)
                        if size < 8:
                            Logger.error("WHB04B: Incorrect packet size")
                            continue

                        if data[0] != 0x04:
                            Logger.error("WHB04B: Not an WHB04B HID packet")
                            continue

                        if self.app.is_connected:
                            if self.f_ovr != self.app.fro:
                                self.app.comms.write("M220 S{}\n".format(self.f_ovr))
                            # if self.s_ovr != self.app.sr:
                            #     self.app.comms.write("M221 S{}\n".format(self.s_ovr));
                            if self.reset_mode:
                                self.reset_mode = False
                                self.refresh_lcd()

                        else:
                            self.reset_mode = True
                            self.refresh_lcd()
                            continue

                        btn_1 = data[2]
                        btn_2 = data[3]
                        inc = data[4]
                        axis = data[5]
                        wheel = self.twos_comp(data[6], 8)

                        # check if we are in continuous mode
                        if self.continuous_mode:
                            if contdir is not None:
                                # if we are moving
                                if btn_1 == BUT_CONT:
                                    # still down so just update lcd
                                    self.refresh_lcd()
                                    continue
                                else:
                                    # released so stop continuous mode
                                    self.app.comms.write('\x19')  # control Y
                                    self.continuous_mode = False
                                    contdir = None
                            elif btn_1 != BUT_CONT:
                                self.continuous_mode = False

                        if inc in self.steplut:
                            delta = self.steplut[inc]
                        else:
                            delta = 0
                            # Lead mode
                            continue

                        axis = self.axislut[axis]

                        if axis == 'off':
                            # when OFF all other buttons are ignored and no screen updates
                            continue

                        # handle other fixed and macro buttons
                        # won't handle again until they are released
                        if btn_1 + btn_2 != data_old:
                            data_old = btn_1 + btn_2
                            if btn_1 != 0:
                                self.handle_button(btn_1, btn_2, axis)

                        # don't do jogging etc if printing unless we are suspended
                        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
                            self.refresh_lcd()
                            continue

                        if wheel != 0:
                            if self.continuous_mode:
                                # first turn of wheel sets the direction,
                                # it goes until Cont button is released
                                # $J -c {axis}1 S{delta/100}
                                self.app.comms.write("$J -c {}{} S{}\n".format(axis, wheel, self.contlut[inc] / 100.0))
                                contdir = wheel

                            else:
                                if self.mpg_mode:
                                    # MPG mode
                                    step = -1 if wheel < 0 else 1
                                    s = abs(wheel)
                                    if s > 16:
                                        s = 16  # seems the max realistic we get
                                    speed = s / 16.0  # scale where 16 is max speed
                                    dist = step * self.contlut[inc] / 100.0  # Max 1mm movement
                                    self.app.comms.write("$J {}{} S{}\n".format(axis, dist, speed))

                                elif delta != 0:
                                    # step mode
                                    # speed of wheel will move more increments rather than increase
                                    # feed rate this seems to work best
                                    dist = delta * wheel
                                    speed = 1.0
                                    self.app.comms.write("$J {}{} S{}\n".format(axis, dist, speed))
                                # print("$J {}{} S{}\n".format(axis, dist, speed))

                        self.refresh_lcd()

                    # Close the HB04 connection
                    self.hid.close()

                    Logger.info("WHB04B: Disconnected from HID device")

                else:
                    Logger.debug("WHB04B: Failed to open HID device %04X:%04X" % (self.vid, self.pid))

            except Exception:
                Logger.error("WHB04B: Exception - {}".format(traceback.format_exc()))
                if self.hid.opened:
                    self.hid.close()

            self.app.unbind(wpos=self.update_wpos)
            self.app.unbind(mpos=self.update_mpos)
            self.app.unbind(fro=self.update_fro)
            if not self.quit:
                # retry connection in 5 seconds unless we were asked to quit
                time.sleep(5)

    def _setv(self, a):
        self.lock.acquire()
        x = round(a[0], 4)
        y = round(a[1], 4)
        z = round(a[2], 4)
        self.lcd_data.x_wc_int = int(abs(x))
        self.lcd_data.y_wc_int = int(abs(y))
        self.lcd_data.z_wc_int = int(abs(z))
        self.lcd_data.x_wc_frac = int(round((abs(x) % 1) * 10000, -1))
        self.lcd_data.y_wc_frac = int(round((abs(y) % 1) * 10000, -1))
        self.lcd_data.z_wc_frac = int(round((abs(z) % 1) * 10000, -1))
        if x < 0:
            self.lcd_data.x_wc_frac = self.lcd_data.x_wc_frac | 0x8000
        if y < 0:
            self.lcd_data.y_wc_frac = self.lcd_data.y_wc_frac | 0x8000
        if z < 0:
            self.lcd_data.z_wc_frac = self.lcd_data.z_wc_frac | 0x8000
        self.lock.release()

    def setovr(self, f, s):
        self.lock.acquire()
        self.lcd_data.feedrate = int(f)
        self.lcd_data.sspeed = int(s)
        self.lock.release()

    def update_lcd(self):
        self.lock.acquire()
        flags = 0
        if self.reset_mode:
            flags = 64
        elif self.mpg_mode:
            flags = 2  # MPG mode
        elif self.continuous_mode:
            flags = 0  # Cont mode
        else:
            flags = 1  # Step mode

        flags = flags | (0x80 if self.mcs_mode else 0x00)

        self.lcd_data.flags = flags

        buff = ctypes.cast(ctypes.byref(self.lcd_data), ctypes.POINTER(ctypes.c_char * ctypes.sizeof(self.lcd_data)))
        if buff.contents.raw != self.lcd_data.buff_old:
            self.lcd_data.buff_old = buff.contents.raw
            n = self.hid.write(self.lcd_data.buff_old)
        self.lock.release()

    def refresh_lcd(self):
        if not self.app.is_connected or self.app.status == "Alarm":
            self.reset_mode = True

        self.update_lcd()

    def update_wpos(self, i, v):
        if not self.mcs_mode:
            self._setv(v)
            self.update_lcd()

    def update_mpos(self, i, v):
        if self.mcs_mode:
            self._setv(v[0:3])
            self.update_lcd()

    def update_fro(self, i, v):
        self.f_ovr = v
        self.setovr(self.f_ovr, self.s_ovr)
