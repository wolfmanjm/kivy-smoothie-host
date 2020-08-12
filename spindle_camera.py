from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.uix.behaviors import ToggleButtonBehavior, ButtonBehavior
from kivy.properties import ListProperty, BooleanProperty, NumericProperty
import time

Builder.load_string('''
<IButton@IconButton>:
    canvas.before:
        Color:
            rgb: [0.4, 0.4, 0.4] if self.state == 'normal' else [0.5, 0, 0]
        Ellipse:
            pos: [self.center[0] - self.height / 2, self.center[1] - self.height / 2]
            size: self.height, self.height
    size_hint_y: None
    height: 40

<ITogButton@IconToggleButton>:
    canvas.before:
        Color:
            rgb: [0.4, 0.4, 0.4] if self.state == 'normal' else [0.5, 0, 0]
        Ellipse:
            pos: [self.center[0] - self.height / 2, self.center[1] - self.height / 2]
            size: self.height, self.height
    size_hint_y: None
    height: 40

<SpindleCamera>:
    on_enter: camera.play = True
    on_leave: camera.play = False
    FloatLayout:
        BoxLayout:
            orientation: 'horizontal'

            Camera:
                # size_hint: None, None
                # size: 640, 480
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
                            (self.center_x, self.center_y, root.circle_size)
                id: camera
                resolution: (640, 480)
                play: False
            BoxLayout:
                size_hint: None, 1.0
                width: 44
                orientation: 'vertical'
                spacing: 8
                padding: 4
                Label:
                    text: "Circle"
                    size_hint_y: None
                    size: self.texture_size[0], self.texture_size[1]
                Slider:
                    orientation: 'vertical'
                    min: 1
                    max: 240
                    value: root.circle_size
                    on_value: root.circle_size = self.value

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
        Label:
            text: '' if app.wpos == None else "{:1.3f},{:1.3f}".format(app.wpos[0], app.wpos[1])
            size_hint: None, None
            size: self.texture_size
            pos_hint: {'top': 1.0, 'right': 0.5}
''')


class IconToggleButton(ToggleButtonBehavior, Image):
    pass


class IconButton(ButtonBehavior, Image):
    pass


class SpindleCamera(Screen):
    invert_jog = BooleanProperty(False)
    jog = BooleanProperty(False)
    circle_size = NumericProperty(10)

    def __init__(self, **kwargs):
        super(SpindleCamera, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.nfingers = 0
        self.z_jog = False

    def setzero(self):
        self.app.comms.write('G10 L20 P0 X0 Y0\n')

    def capture(self):
        camera = self.ids['camera']
        timestr = time.strftime("%Y%m%d_%H%M%S")
        camera.export_to_png("IMG_{}.png".format(timestr))

    def on_touch_down(self, touch):
        if self.jog and self.ids.camera.collide_point(touch.x, touch.y):
            # if within the camera window
            touch.grab(self)
            self.nfingers += 1
            touch.ud["n"] = self.nfingers
            if self.nfingers == 4:
                self.z_jog = True
            return True

        return super(SpindleCamera, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super(SpindleCamera, self).on_touch_move(touch)

        if self.nfingers >= 1 and not self.z_jog and touch.ud["n"] == 1:
            # we only track the first finger that touched
            n = self.nfingers
            m = 0.001 * 10**(n - 1)  # 1 finger moves 0.001, 2 moves 0.01, 3 moves .1
            dx = 0
            dy = 0
            if abs(touch.dx) > 0:
                dx = m * touch.dx
            if abs(touch.dy) > 0:
                dy = m * touch.dy

            if dx != 0 or dy != 0:
                if self.invert_jog:
                    dx = -dx
                    dy = -dy
                self.app.comms.write("$J X{} Y{}\n".format(dx, dy))

        elif self.z_jog and touch.ud["n"] == 1:
            # we move Z to focus
            dy = touch.dy
            if dy != 0:
                self.app.comms.write("$J Z{}\n".format(0.01 * dy))

        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.nfingers -= 1
            if self.nfingers == 0:
                self.z_jog = False

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
<ExitScreen>:
    on_enter: app.stop()
''')

    class StartScreen(Screen):
        pass

    class ExitScreen(Screen):
        pass

    class TestCamera(App):
        comms = sys.stdout
        wpos = None

        def __init__(self, **kwargs):
            super(TestCamera, self).__init__(**kwargs)
            self.test = False
            self.running = False

            if len(sys.argv) > 1:
                if sys.argv[1] == 'd':
                    self.test = True

        def build(self):
            # Window.size = (800, 480)
            self.sm = ScreenManager()
            self.sc = SpindleCamera(name='spindle camera')
            self.sm.add_widget(self.sc)

            if not self.test:
                self.ecr = ExitScreen(name='main')
                self.sm.add_widget(self.ecr)
                self.sm.current = 'spindle camera'

            else:
                self.scr = StartScreen(name='main')
                self.sm.add_widget(self.scr)
                self.sm.current = 'main'

            return self.sm

        def play(self):
            self.sm.current = 'spindle camera'

    TestCamera().run()
