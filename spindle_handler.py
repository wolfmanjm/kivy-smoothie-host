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

    def lookup(self, srpm):
        ''' look up the RPM in the table and return the interpolated PWM '''
        idx = 0
        # take into consideration the ratio to get the motor RPM, ratio is from motor to pulley
        mrpm = srpm / self.ratio  # convert to Motor RPM from Spindle RPM

        for ri in self.rpm:
            if ri > mrpm:
                break
            idx += 1

        # return minimum or maximum if necessary
        pwm = None
        if idx == 0:
            pwm = self.pwm[0]
        if idx >= len(self.pwm):
            pwm = self.pwm[-1]

        if pwm is None:
            # interpolate the value
            p1 = self.pwm[idx - 1]
            p2 = self.pwm[idx]
            r1 = self.rpm[idx - 1]
            r2 = self.rpm[idx]

            pwm = p1 + (p2 - p1) * ((mrpm - r1) / (r2 - r1))

        Logger.debug(f"SpindleHandler: Spindle RPM of {srpm} is motor RPM of {mrpm:1.2f} which is PWM of {pwm:1.4f}")

        # FIXME for debugging remove when done
        app = App.get_running_app()
        if app is not None:
            app.main_window.async_display(f"Spindle RPM of {srpm} is motor RPM of {mrpm:1.2f} which is PWM of {pwm:1.4f}")
        return pwm

    def reverse_lookup(self, pwm):
        ''' look up the PWM in the table and return the interpolated RPM '''
        idx = 0
        for ri in self.pwm:
            if ri > pwm:
                break
            idx += 1

        # return minimum or maximum if necessary
        if idx == 0:
            mrpm = self.rpm[0]

        elif idx >= len(self.rpm):
            mrpm = self.rpm[-1]

        else:
            # interpolate the value
            p1 = self.rpm[idx - 1]
            p2 = self.rpm[idx]
            r1 = self.pwm[idx - 1]
            r2 = self.pwm[idx]

            mrpm = p1 + (p2 - p1) * ((pwm - r1) / (r2 - r1))

        # take into consideration the ratio to get the spindle RPM, ratio is from motor to pulley
        return mrpm * self.ratio

    def get_max_rpm(self):
        return self.rpm[-1]


# test it
if __name__ == "__main__":
    sh = SpindleHandler()

    if not sh.load():
        print("Failed to load")

    else:
        print(f"translate M3 to {sh.translate}")
        print(f"ratio = {sh.ratio}")

        print("lookup RPM to PWM")
        for r in [0, 6000, 6010, 10000, 1, 100, 200, 500, 1000, 150, 510, 550, 590, 750, 900, 999, -1]:
            print(f"{r}: {sh.lookup(r)}")

        print("lookup PWM to RPM")
        for r in [6.5, 8.55, 1, 9, 6.95, 7.45, 7.55, 7.50, 7.551666, 7.98]:
            print(f"{r}: {sh.reverse_lookup(r):1.2f}")
