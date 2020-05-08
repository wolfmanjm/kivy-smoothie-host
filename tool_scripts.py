import kivy

from kivy.logger import Logger
from kivy.app import App

import traceback
import asyncio


class ToolScripts():
    """ Handle some builtin convenience scripts """

    def __init__(self, **kwargs):
        super(ToolScripts, self).__init__(**kwargs)
        self.app = App.get_running_app()

    # public methods
    def find_center(self):
        """ Finds the center of a circle """
        # needs to be run asyncronously
        asyncio.ensure_future(self._find_center())

    # private methods
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

        self.app.comms.write("G38.3 {}\n".format(cmd))

        # wait for it to complete
        # TODO may need a timeout
        self.app.comms.okcnt.wait()
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
            self.app.comms.okcnt.wait()
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
            self.app.comms.okcnt.wait()
            self.app.comms.okcnt.clear()
            if self.app.main_window.status == 'Alarm':
                raise Exception("ALARM detected")

    async def _find_center(self):
        self.app.main_window.async_display("Starting find center....")

        self.app.comms.okcnt = asyncio.Event()
        self.app.comms.okcnt.clear()

        try:
            # get current position
            wpx = self.app.wpos[0]
            wpy = self.app.wpos[1]

            # probe right
            r1 = self._probe(x=100)

            # move back to starting x
            self._moveto(x=wpx)

            # probe left
            r2 = self._probe(x=-100)

            diam = r1['X'] - r2['X']

            # center in X
            self._moveby(x=diam / 2.0)

            # probe back
            r1 = self._probe(y=100)

            # move back to starting y
            self._moveto(y=wpy)

            # probe front
            r2 = self._probe(y=-100)

            diam = r1['Y'] - r2['Y']

            # center in Y
            self._moveby(y=diam / 2.0)

            # tell us the approx diameter
            self.app.main_window.async_display(
                "Diameter is {}, plus the tool diameter".format(diam))

        except Exception as msg:
            # Logger.info("Tools: Exception - {}".format(traceback.format_exc()))
            Logger.error("Tools: find_center: Got exception: {}".format(msg))
            self.app.main_window.async_display("find center failed: {}".format(msg))

        else:
            self.app.main_window.async_display("find center completed")

        finally:
            self.app.comms.okcnt = None
