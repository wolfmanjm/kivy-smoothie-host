import kivy

from kivy.app import App
from kivy.logger import Logger
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import mainthread

import configparser
from functools import partial
import os

SPINDLE_INI_FILE = "spindle.ini"


class SpindleHandler():
    def __init__(self, **kwargs):
        super(SpindleHandler, self).__init__(**kwargs)
        self.app = App.get_running_app()

        self.rpm = []
        self.pwm = []
        self.enabled = False
        self.translate = ""
        self.belt_tbl = []
        self.last_ratio = 1.0
        self.last_belt = None

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

            # read spindle pulley ratio in belt 1 to belt 10 position
            for section in config.sections():
                if section.startswith('belt '):
                    belt = section[5:]
                    ratio = config.getfloat(section, "ratio")
                    high = config.getfloat(section, "rpm_high")
                    low = config.getfloat(section, "rpm_low")
                    self.belt_tbl.append({'position': belt, 'ratio': ratio, 'high': high, 'low': low})

            # print(self.belt_tbl)

        except Exception as err:
            Logger.warning(f'SpindleHandler: WARNING - exception parsing config file: {err}')
            if self.app is not None:
                self.app.main_window.async_display(f"ERROR in spindle.ini: {err}")

            return False

        return True

    def lookup(self, srpm):
        ''' look up the spindle RPM in the table and return the interpolated PWM '''
        idx = 0
        mrpm = srpm
        belt = 0

        # take into consideration the ratio to get the motor RPM, ratio is from motor to pulley
        if self.belt_tbl:
            for b in self.belt_tbl:
                # find rpm range
                if srpm >= b['low'] and srpm <= b['high']:
                    self.last_ratio = b['ratio']
                    mrpm = srpm / self.last_ratio  # convert to Motor RPM from Spindle RPM
                    belt = b['position']
                    break

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
        if self.app is not None:
            self.app.main_window.async_display(f"Spindle RPM of {srpm} is motor RPM of {mrpm:1.2f} which is PWM of {pwm:1.4f}")

        # returns the pwm to use and the belt position (0 means no belt change is needed)
        if self.last_belt is None:
            self.last_belt = belt
        elif self.last_belt == belt:
            belt = 0
        else:
            self.last_belt = belt

        return (pwm, belt)

    def reverse_lookup(self, pwm):
        ''' look up the PWM in the table and return the interpolated RPM, presumes lookup was used previously '''
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
        return mrpm * self.last_ratio

    def get_max_rpm(self):
        return self.rpm[-1]

    @mainthread
    def change_belt(self, cb=None):
        label1 = Label(text=f"to belt {self.last_belt}")
        btn1 = Button(text="OK", size_hint_y=None, height=48)
        Boxed_layout = BoxLayout(orientation="vertical")
        Boxed_layout.add_widget(label1)
        Boxed_layout.add_widget(btn1)

        pop = Popup(title="Change Belt", content=Boxed_layout, size_hint=(.5, None), height=Boxed_layout.height + 140, auto_dismiss=False)

        btn1.bind(on_release=partial(self.belt_changed, pop, cb))

        pop.open()

    @mainthread
    def belt_changed(self, popup, cb, button):
        popup.dismiss()
        if cb is None:
            self.app.comms.release_m0()
        else:
            cb()


# test it
if __name__ == "__main__":
    sh = SpindleHandler()

    if not sh.load():
        print("Failed to load")

    else:
        print(f"translate M3 to {sh.translate}")

        print("lookup RPM to PWM")
        for r in [0, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 12000]:
            print(f"{r}: {sh.lookup(r)}")

        # print("lookup PWM to RPM")
        # for r in [6.5, 8.55, 1, 9, 6.95, 7.45, 7.55, 7.50, 7.551666, 7.98]:
        #     print(f"{r}: {sh.reverse_lookup(r):1.2f}")
