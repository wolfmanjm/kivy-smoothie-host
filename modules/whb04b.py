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
    mpglut = {0x0d: 2, 0x0e: 5, 0x0f: 10, 0x10: 30, 0x1a: 60, 0x1b: 100, 0x1c: 0}             # combined button for set mpg %  #or 0x1c = lead and after set con ??? 
    conlut = {0x0d: 1, 0x0e: 2, 0x0f: 3, 0x10: 4, 0x1a: 5, 0x1b: 6, 0x1c: 0}                  # lead mode look up table for set con % but don't really know what is for in reality
    status = 0x40                                                                             # start with lead mode
    axis_mode = 0x06                                                                          # start with reset/off status
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
        elif btn == BUT_FEEDP:
            # adjust feed override
            self.f_ovr += 10
            if self.f_ovr > 400:
                self.f_ovr = 100
            self.setovr(self.f_ovr, self.s_ovr)
            self.update_lcd()
        elif btn == BUT_FEEDM:
            # adjust feed override
            self.f_ovr -= 10
            if self.f_ovr < 10:
                self.f_ovr = 10
            self.setovr(self.f_ovr, self.s_ovr)
            self.update_lcd()
        elif btn == BUT_SPINDLEP:
            # adjust S override, (TODO  this is tool speed or laser power)
            self.s_ovr += 10
            if self.s_ovr > 200:
                self.s_ovr = 10
            self.setovr(self.f_ovr, self.s_ovr)
            self.update_lcd()
        elif btn == BUT_SPINDLEM:
            # adjust S override, (TODO  this is tool speed or laser power)
            self.s_ovr -= 10
            if self.s_ovr < 10:
                self.s_ovr = 10
            self.setovr(self.f_ovr, self.s_ovr)
            self.update_lcd()
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


                        # setup LCD with current settings 
#                    if axis_mode > 0x10 and axis_mode < 0x14:
#                    self.setwcs(self.app.wpos)
#                    if axis_mode > 0x13 and axis_mode < 0x17:
#                    self.setmcs(self.app.mpos[3:6])          # TODO clear unused axis value from ABC  
#                    self.setovr(self.f_ovr, self.s_ovr)  
#                    self.setstatus(self.status)
#                    self.update_lcd()

                    self.clear_lcd()
                    
                    # refresh var when these change but do not update LCD here
#                    self.app.bind(mpos=self.update_mpos)      # TODO clear unused axis value from ABC
                    self.app.bind(wpos=self.update_wpos)
                    self.app.bind(fro=self.update_fro)



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
                                # if self.s_ovr != self.app.sr:
                                #     self.app.comms.write("M221 S{}".format(self.s_ovr));
                                #     self.app.comms.write("M221 S{}".format(self.s_ovr))      # ; is i think sintaxe error
                                self.update_lcd()
                            continue

                        if data[0] != 0x04:
                            Logger.error("WHB04B: Not an WHB04B HID packet")
                            continue

                        seed = data[1]
                        btn_1 = data[2]
                        btn_2 = data[3]
                        speed_mode = data[4]
                        axis_mode = data[5]
                        wheel = self.twos_comp(data[6], 8)
                        checksum = data[7]
                        
                        # only select rotary mode buttons
                        if axis_mode != 6 and self.status > 2:
                            self.status = 0                             #Refresh all after rotary knob set off
                            self.setstatus(self.status)                            
#                            if axis_mode > 0x10 and axis_mode < 0x14:
                            self.setwcs(self.app.wpos)
#                            if axis_mode > 0x13 and axis_mode < 0x17:
#                               self.setmcs(self.app.mpos[3:6])          # TODO clear unused axis value from ABC
                            self.setovr(self.f_ovr, self.s_ovr)     
                            self.update_lcd()
                            #continue
                            
                        if speed_mode == 0x1c and axis_mode != 6 and self.status < 2:
                            self.status = 0               #mode lead = move locked and after keep out from lead this mode are CON
                            self.setstatus(self.status)   #mode CON because we are out of lead and not in mpg or step or reset
                            self.update_lcd()
                            #continue                     #Lead is not a momentary push button do not loop here !
                            
                        if btn_1 == BUT_STEP:
                            self.status = 1
                            self.setstatus(self.status)
                            self.update_lcd()
                            continue

                        if btn_1 == BUT_MPG:
                            self.status = 2
                            self.setstatus(self.status)
                            self.update_lcd()
                            continue

                        if self.status == 0:
                           Logger.debug("whb04b: seed: {}, btn_1: {}, btn_2: {}, speed CON: {}, axis: {}, wheel: {}, checksum: {}".format(seed, btn_1, btn_2, self.conlut[speed_mode], self.axislut[axis_mode], wheel, checksum))
                        if self.status == 1:
                           Logger.debug("whb04b: seed: {}, btn_1: {}, btn_2: {}, speed STEP: {}, axis: {}, wheel: {}, checksum: {}".format(seed, btn_1, btn_2, self.steplut[speed_mode], self.axislut[axis_mode], wheel, checksum))
                        if self.status == 2:
                           Logger.debug("whb04b: seed: {}, btn_1: {}, btn_2: {}, speed MPG: {}, axis: {}, wheel: {}, checksum: {}".format(seed, btn_1, btn_2, self.mpglut[speed_mode], self.axislut[axis_mode], wheel, checksum))

                        if not self.app.is_connected:
                            continue

                        if btn_1 == BUT_STOP and self.app.status != 'Alarm':
                            self.app.comms.write('\x18')
                            continue

                        if btn_1 == BUT_RESET and self.app.status == 'Alarm':
                            self.app.comms.write('$X\n')
                            continue

#                        if btn_1 == BUT_RESET and self.app.is_connected == 0:
#                            self.is_connected= True                            # like to make possible to connect/disconnect 
#                            continue

                        if axis_mode == 0x06:
                            # when OFF all other buttons are ignored 0x40 display RESET on the pendant but not work fine
                           self.status = 0x40
                           self.clear_lcd()  
                           continue
                             
                        # dont do jogging etc if printing unless we are suspended
                        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
                            continue
                                                   
                        axis = self.axislut[axis_mode]
                        f_over = self.f_ovr
                        s_over = self.s_ovr

                        # handle other fixed and macro buttons
                        if btn_1 != 0 and btn_1 != BUT_FN and self.handle_button(btn_1, axis):
                            continue

                        # handle other fixed and macro buttons
                        if btn_2 != 0 and btn_1 == BUT_FN and self.handle_buttonfn(btn_2, axis):
                            continue

                        if wheel != 0:

                            # must be one of XYZABC so send jogging command
                            # velocity_mode:
                            # step= -1 if wheel < 0 else 1
                            # s = -wheel if wheel < 0 else wheel
                            # if s > 5: s == 5 # seems the max realistic we get
                            # speed= s/5.0 # scale where 5 is max speed
                            step = wheel  # speed of wheel will move more increments rather than increase feed rate
                            if self.status == 2:
                                dist = 0.001 * step * self.mpglut[speed_mode]    #mode mpg
                            if self.status == 1:
                               dist = self.steplut[speed_mode] * step             #mode step
                            if self.status == 0 and speed_mode == 0x1c:
                               Logger.info("LEAD MODE move locked\n")
                               dist = 0                                        #mode lead = move locked
                            if self.status == 0 and speed_mode != 0x1c:
                               dist = 0.001 * step * self.conlut[speed_mode]     #mode continu ??? maybee don't really know what is for in reality
                            
                            self.setwcs(self.app.wpos)
                            self.update_lcd()
                               
                            if dist != 0:                                       
                               speed = 1.0                                     #final check if mode lead = move skiped
                               
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
                        
            self.app.unbind(wpos=self.update_wpos)      # TODO clear unused axis value from ABC
            self.app.unbind(mpos=self.update_mpos)      # TODO clear unused axis value from ABC
            self.app.unbind(fro=self.update_fro)
            
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
         # from linuxcnc a check for WCS/MCS Coordinate is possible for show X1 in place of X
         # something like this can work but need to create and set var absolueMCS = 1 and need to swap MCS/WCS for XYZ
         # no need for ABC allways from Mpos ['<Idle|MPos:1.1200,-1.0000,-1.0000,12.9881|WPos:1.1200,-1.0000,-1.0000|F:1000.0,10.0>\n'
         #if absolueMCS = 1:
         # TODO create MASK ?xxxxxxx
         #   self.status = 0x80
         #elif  absolueMCS = 0:
         # TODO create MASK ?xxxxxxx
         #     self.status = 0x00 
         #self.setstatus(self.status)    
        self.lock.acquire()
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
        Logger.debug("Sent {} out of {}".format(n, len(self.lcd_data)))
        Logger.debug("LCD {}".format(self.lcd_data))
        
    def clear_lcd(self):
        self.lock.acquire()
        self.lcd_data[3] = self.status
#        self.lcd_data[4:19] == 0x00
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
        Logger.debug("Sent {} out of {}".format(n, len(self.lcd_data)))
        Logger.debug("LCD {}".format(self.lcd_data))

    def update_wpos(self, i, v):
        self.setwcs(v)
#        self.update_lcd()

    def update_mpos(self, i, v):
        self.setmcs(v[3:6])
#        self.update_lcd()

    def update_fro(self, i, v):
#        self.s_ovr = i
        self.f_ovr = v
        self.setovr(self.f_ovr, self.s_ovr)
