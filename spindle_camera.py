from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
import time

Builder.load_string('''
<SpindleCamera>:
    on_enter: camera.play = True
    on_leave: camera.play = False
    BoxLayout:
        orientation: 'horizontal'

        camera: camera
        Camera:
            canvas.after:
                Color:
                    rgb: 1, 0, 0
                Line:
                    points: [self.center_x, 0, self.center_x, self.height]
                    width: 1
                    cap: 'none'
                    joint: 'none'
                Line:
                    points: [0, self.center_y, self.width, self.center_y]
                    width: 1
                    cap: 'none'
                    joint: 'none'
                Line:
                    circle:
                        (self.center_x, self.center_y, 20)
            id: camera
            resolution: (640, 480)
            play: False
        BoxLayout:
            size_hint: 0.15, None
            orientation: 'vertical'
            Button:
                text: 'Zero'
                size_hint_y: None
                height: 40
                on_press: root.setzero()
            Button:
                text: 'Capture'
                size_hint_y: None
                height: 40
                on_press: root.capture()
            Button:
                text: 'Back'
                size_hint_y: None
                height: 40
                on_press: root.manager.current = 'main'
''')


class SpindleCamera(Screen):
    def __init__(self, **kwargs):
        super(SpindleCamera, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.nfingers = 0

    def setzero(self):
        self.app.comms.write('G10 L20 P0 X0 Y0\n')

    def capture(self):
        camera = self.ids['camera']
        timestr = time.strftime("%Y%m%d_%H%M%S")
        camera.export_to_png("IMG_{}.png".format(timestr))

    def on_touch_down(self, touch):
        if self.ids.camera.collide_point(touch.x, touch.y):
            # if within the camera window
            touch.grab(self)
            self.nfingers += 1
            touch.ud["n"] = self.nfingers
            return True

        return super(SpindleCamera, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False

        if self.nfingers >= 2 and self.nfingers < 4 and touch.ud["n"] == 1:
            # we only track the first finger that touched
            n = self.nfingers
            m = 5 if n == 2 else 50
            # 0.00125 seems to be the smallest move
            dx = touch.dsx
            dy = touch.dsy

            self.app.comms.write("$J X{} Y{}\n".format(dx * m, dy * m))

        elif self.nfingers == 4 and touch.ud["n"] == 1:
            # we move Z to focus
            dy = touch.dsy
            self.app.comms.write("$J Z{}\n".format(dy))

        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.nfingers -= 1
            return True

        return super(SpindleCamera, self).on_touch_up(touch)


if __name__ == '__main__':
    import sys
    Builder.load_string('''
<StartScreen>:
    BoxLayout:
        Button:
            id: play_but
            text: 'Play'
            on_press: app.play()
            size_hint_y: None
            height: 40
        Button:
            text: 'Exit'
            on_press: app.stop()
            size_hint_y: None
            height: 40
''')

    class StartScreen(Screen):
        pass

    class TestCamera(App):
        comms = sys.stdout

        def build(self):
            # Window.size = (800, 480)
            self.sc = SpindleCamera(name='spindle camera')
            self.scr = StartScreen(name='main')
            self.sm = ScreenManager()
            self.sm.add_widget(self.scr)
            self.sm.add_widget(self.sc)

            return self.sm

        def play(self):
            self.sm.current = 'spindle camera'

    TestCamera().run()
