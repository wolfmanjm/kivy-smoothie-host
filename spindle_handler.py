import kivy

from kivy.app import App
from kivy.logger import Logger

import configparser
from functools import partial
import os

SPINDLE_INI_FILE = "spindle.ini"


class SpindleHandler():
    def __init__(self, **kwargs):
        super(SpindleHandler, self).__init__(**kwargs)
        # self.app = App.get_running_app()

        self.rpm = []
        self.pwm = []
        self.enabled = False
        self.translate = ""
        self.ratio = 1.0

    def load(self):
        if not (os.path.isfile(SPINDLE_INI_FILE) and os.access(SPINDLE_INI_FILE, os.R_OK)):
            Logger.info("SpindleHandler: no spindle.ini to load")
            return False

        try:
            config = configparser.ConfigParser()
            config.read(SPINDLE_INI_FILE)

            # See if enabled
            self.enabled = config.getboolean("setup", "enabled", fallback=False)
            if not self.enabled:
                return False

            # read translation M code
            self.translate = config.get("setup", "translate", fallback="")

            # read spindle pulley ratio
            self.ratio = config.getfloat("setup", "ratio", fallback=1.0)

            # read calibration data, must be is ascending RPM order
            last_rpm = 0
            for (key, v) in config.items('calibration'):
                r = float(key)
                p = float(v)
                if last_rpm > r:
                    # must be ascending order
                    raise Exception(f'RPM values must be in ascending order: {last_rpm} - {r}')

                last_rpm = r
                self.rpm.append(r)
                self.pwm.append(p)

        except Exception as err:
            Logger.warning('SpindleHandler: WARNING - exception parsing config file: {}'.format(err))
            return False

        return True

    def lookup(self, r):
        ''' look up the RPM in the table and return the interpolated PWM '''
        idx = 0
        # take into consideration the ratio to get the motor RPM, ration is from motor to pulley
        r = r / self.ratio  # convert to Motor RPM from Spindle RPM

        for ri in self.rpm:
            if ri > r:
                break
            idx += 1

        # return minimum or maximum if necessary
        if idx == 0:
            return self.pwm[0]
        if idx >= len(self.pwm):
            return self.pwm[-1]

        # interpolate the value
        p1 = self.pwm[idx - 1]
        p2 = self.pwm[idx]
        r1 = self.rpm[idx - 1]
        r2 = self.rpm[idx]

        p = p1 + (p2 - p1) * ((r - r1) / (r2 - r1))

        return p


# test it
if __name__ == "__main__":
    sh = SpindleHandler()

    if not sh.load():
        print("Failed to load")

    else:
        print(f"translate M3 to {sh.translate}")
        print(f"ratio = {sh.ratio}")

        for r in [0, 6000, 6010, 1, 100, 200, 500, 1000, 150, 510, 550, 590, 750, 900, 999, -1]:
            print(f"{r}: {sh.lookup(r)}")


