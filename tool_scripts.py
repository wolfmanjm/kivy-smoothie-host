import kivy

from kivy.logger import Logger
from kivy.app import App
import threading

class ToolScripts():
    """ Handle some builtin convenience scripts """

    def __init__(self, **kwargs):
        super(ToolScripts, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def find_center(self):
        """ Finds the center of a circle """
        # needs to be run in a thread
        t= threading.Thread(target=self._find_center_thread, daemon=True)
        t.start()

    def _probe(self, axis, dirn):
        self.app.comms.write("G38.3 {}{}\n".format(axis, dirn))

        # wait for it to complete
        if not self.app.comms.okcnt.wait(120):
            raise Exception("probe timed out")

        r= self.app.last_probe
        if not r["status"]:
            raise Exception("probe failed")

        print(r)

        # return result
        return r


    def _find_center_thread(self):
        self.app.main_window.async_display("Starting find center....")

        self.app.comms.okcnt= threading.Event()
        try:

            # get current position
            wp= self.app.wpos

            # probe right
            r1= self._probe("X", 100)
            # move back to start
            self.app.comms.write("G0 X{}\n".format(wp[0]))

            # probe left
            r2= self._probe("X", -100)

            diam= r1[0] - r2[0]

            # center in X
            self.app.comms.write("G91 G0 X{} G90\n".format(diam/2.0))

            # probe back
            r1= self._probe("Y", +100)

            # to speed things up a bit get back to approx center
            self.app.comms.write("G91 G0 Y{} G90\n".format(-diam/2.0))

            # probe front
            r2= self._probe("Y", -100)

            diam= r1[1] - r2[1]

            # center in Y
            self.app.comms.write("G91 G0 Y{} G90\n".format(diam/2.0))

            # tell us the appprox diameter
            self.app.main_window.async_display("Diameter is {}, less the tool diameter".format(diam))

        except Exception as msg:
            Logger.error("Tools: find_center: Got exception: {}".format(msg))
            self.app.main_window.async_display("find center failed: {}".format(msg))

        else:
            self.app.main_window.async_display("find center completed")

        finally:
            self.app.okcnt= None

