from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.uix.behaviors import ToggleButtonBehavior, ButtonBehavior
from kivy.properties import ListProperty, BooleanProperty
import time

Builder.load_string('''
<IButton@IconButton>:
    canvas.before:
        Color:
            rgb: [0.4, 0.4, 0.4] if self.state == 'normal' else [0.5, 0, 0]
        Ellipse:
            pos: [self.center[0] - 2 - self.height / 2, self.center[1] - 2 - self.height / 2]
            size: self.height+4, self.height+4
    size_hint_y: None
    height: 40

<ITogButton@IconToggleButton>:
    canvas.before:
        Color:
            rgb: [0.4, 0.4, 0.4] if self.state == 'normal' else [0.5, 0, 0]
        Ellipse:
            pos: [self.center[0] - 2 - self.height / 2, self.center[1] - 2 - self.height / 2]
            size: self.height+4, self.height+4
    size_hint_y: None
    height: 40

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
            spacing: 8
            ITogButton:
                source: "img/cross-mouse.png"
                on_state: root.jog = self.state == 'down'
            ITogButton:
                source: "img/invert_jog.png"
                on_state: root.invert_jog = self.state == 'down'
            IButton:
                source: "img/set_zero.png"
                on_press: root.setzero()
            IButton:
                source: "img/screenshot.png"
                on_press: root.capture()
            IButton:
                source: "img/back.png"
                on_press: root.manager.current = 'main'
''')


class IconToggleButton(ToggleButtonBehavior, Image):
    pass


class IconButton(ButtonBehavior, Image):
    pass


class SpindleCamera(Screen):
    invert_jog = BooleanProperty(False)
    jog = BooleanProperty(False)

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
        print(self.jog, self.invert_jog)
        if self.jog and self.ids.camera.collide_point(touch.x, touch.y):
            # if within the camera window
            touch.grab(self)
            self.nfingers += 1
            touch.ud["n"] = self.nfingers
            return True

        return super(SpindleCamera, self).on_touch_down(touch)

    def on_touch_move(self, touch):

        if touch.grab_current is not self:
            return False

        if self.nfingers >= 1 and self.nfingers < 4 and touch.ud["n"] == 1:
            # we only track the first finger that touched
            n = self.nfingers
            m = 0.001 * 10**(n - 1)  # 1 finger moves 0.001, 2 moves 0.01, 3 moves .1
            dx = 0
            dy = 0
            if abs(touch.dx) > 0:
                dx *= touch.dx
            if abs(touch.dy) > 0:
                dy *= touch.dy

            if dx != 0 or dy != 0:
                if self.invert_jog:
                    dx = -dx
                    dy = -dy
                self.app.comms.write("$J X{} Y{}\n".format(dx, dy))

        elif self.nfingers == 4 and touch.ud["n"] == 1:
            # we move Z to focus
            dy = touch.dy
            if dy != 0:
                self.app.comms.write("$J Z{}\n".format(0.01 * dy))

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
