import kivy

from kivy.logger import Logger
from kivy.app import App
import threading
import traceback
import datetime
from functools import partial


class ToolScripts():
    """ Handle some builtin convenience scripts """

    def __init__(self, **kwargs):
        super(ToolScripts, self).__init__(**kwargs)
        self.app = App.get_running_app()

    # public methods
    def find_center(self):
        """ Finds the center of a circle """
        # needs to be run in a thread
        if self.app.is_connected:
            t = threading.Thread(target=self._find_center_thread, daemon=True)
            t.start()
        else:
            self.app.main_window.async_display("Not connected")

    def set_datetime(self, *args):
        """ sets the date/time on a V2 """
        if self.app.is_connected:
            dt = datetime.datetime.now()
            # date YYMMDDhhmmss
            cmd = f"date {dt.year-2000:02d}{dt.month:02d}{dt.day:02d}{dt.hour:02d}{dt.minute:02d}{dt.second:02d}\n"
            self.app.main_window.async_display(f"setting {cmd}")
            self.app.comms.write(cmd)
        else:
            self.app.main_window.async_display("Must be connected to set datetime")

    def set_rpm(self, rpm):
        """ set the RPM for a PWM driven switch spindle """
        if self.app.spindle_handler is not None:
            (pwm, belt) = self.app.spindle_handler.lookup(rpm)
            if belt:
                # wait for the continue dialog to be dismissed after belt changed
                self.app.spindle_handler.change_belt(partial(self._belt_changed, pwm))

            else:
                self.app.comms.write(f"M3 S{pwm:1.4f}\n")

            # FIXME for DEBUG
            self.app.main_window.async_display(f"Spindle RPM of {rpm} is PWM {pwm:1.4f} belt {belt}")

        else:
            self.app.comms.write(f"M3 S{rpm}\n")

    # private methods
    def _belt_changed(self, pwm):
        self.app.comms.write(f"M3 S{pwm:1.4f}\n")

    def _wait(self, tmo=120):
        self.app.comms.write("M400\n")
        if not self.app.comms.okcnt.wait(tmo):
            raise Exception("wait (M400) timed out")

        self.app.comms.okcnt.clear()

    def _probe(self, x=None, y=None, z=None):
        cmd = ""
        if x:
            cmd += "X{} ".format(x)

        if y:
            cmd += "Y{} ".format(y)

        if z:
            cmd += "Z{}".format(z)

        if not cmd:
            raise Exception("need to specify an axis to probe")

        self.app.comms.write(f"G38.2 {cmd}\n")

        # wait for it to complete
        if not self.app.comms.okcnt.wait(120):
            raise Exception("probe timed out")

        self.app.comms.okcnt.clear()

        r = self.app.last_probe
        if not r["status"]:
            raise Exception("probe failed")

        # return result
        return r

    def _moveby(self, x=None, y=None, z=None):
        cmd = ""
        if x:
            cmd += "X{} ".format(x)

        if y:
            cmd += "Y{} ".format(y)

        if z:
            cmd += "Z{}".format(z)

        if cmd:
            self.app.comms.write("G91 G0 {} G90\n".format(cmd))
            # wait for it to complete
            if not self.app.comms.okcnt.wait(120):
                raise Exception("moveby timed out")

            self.app.comms.okcnt.clear()
            if self.app.main_window.status == 'Alarm':
                raise Exception("ALARM detected")

    def _moveto(self, x=None, y=None, z=None):
        cmd = ""
        if x:
            cmd += "X{} ".format(x)

        if y:
            cmd += "Y{} ".format(y)

        if z:
            cmd += "Z{}".format(z)

        if cmd:
            self.app.comms.write("G90 G0 {}\n".format(cmd))
            # wait for it to complete
            if not self.app.comms.okcnt.wait(120):
                raise Exception("moveto timed out")

            self.app.comms.okcnt.clear()
            if self.app.main_window.status == 'Alarm':
                raise Exception("ALARM detected")

    def _find_center_thread(self):
        self.app.main_window.async_display("Starting find center....")

        self.app.comms.okcnt = threading.Event()
        try:

            # get current position
            wpx = self.app.wpos[0]
            wpy = self.app.wpos[1]

            # probe right
            r1 = self._probe(x=30)

            # move back to starting x
            self._moveto(x=wpx)
            self._wait()

            # probe left
            r2 = self._probe(x=-30)

            diam = r1['X'] - r2['X']

            # center in X
            self._moveby(x=diam / 2.0)
            self._wait()

            # probe back
            r1 = self._probe(y=30)

            # move back to starting y
            self._moveto(y=wpy)
            self._wait()

            # probe front
            r2 = self._probe(y=-30)

            diam = r1['Y'] - r2['Y']

            # center in Y
            self._moveby(y=diam / 2.0)
            self._wait()

            # tell us the approx diameter
            self.app.main_window.async_display(
                "Diameter is {}, plus the tool diameter".format(diam))

        except Exception as msg:
            Logger.info("Tools: Exception - {}".format(traceback.format_exc()))
            # Logger.error("Tools: find_center: Got exception: {}".format(msg))
            self.app.main_window.async_display("find center failed: {}".format(msg))

        else:
            self.app.main_window.async_display("find center completed")

        finally:
            self.app.okcnt = None
