from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.properties import NumericProperty, ReferenceListProperty
from kivy.vector import Vector

Builder.load_string('''
<Hat>:
    canvas.before:
        Color:
            rgb: [0.4, 0.4, 0.4]
        Ellipse:
            pos: [self.center[0] - self.height / 2, self.center[1] - self.height / 2]
            size: self.height, self.height
    size_hint: None, None
    size: 64, 64
    Image:
        id: pad
        source: "img/4-direction-48.png"
        size_hint: None, None
        size: 48, 48
        pos_hint: {'center_x': 0.5, 'center_y': 0.5}
''')


class Hat(FloatLayout):
    pad_x = NumericProperty(0.0)
    pad_y = NumericProperty(0.0)
    pad = ReferenceListProperty(pad_x, pad_y)

    def __init__(self, *args, **kwargs):
        self.register_event_type('on_release')
        self.register_event_type('on_press')
        super(Hat, self).__init__(*args, **kwargs)

    def on_touch_down(self, touch):
        if self.collide_point(touch.x, touch.y):
            touch.grab(self)
            self.dispatch('on_press')
            self.first = True
            self.last_px = self.last_py = 0
            return True
        return super(Hat, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            return self.move_pad(touch)
        return super(Hat, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.center_pad()
            self.pad = [0, 0]
            self.dispatch('on_release')
            return True

        return super(Hat, self).on_touch_up(touch)

    def collide_point(self, x, y):
        return Vector(x, y).distance(self.center) <= self.width / 2

    def center_pad(self):
        self.ids.pad.pos_hint = {'center_x': 0.5, 'center_y': 0.5}

    def move_pad(self, touch):
        dx = touch.pos[0] - touch.opos[0]
        dy = touch.pos[1] - touch.opos[1]

        # print("move: {} - {}".format(dx, dy))
        if abs(dx) >= 4 or abs(dy) >= 4:
            if abs(dx) > abs(dy):
                yp = 0.5
                py = 0
                if dx < 0:
                    xp = 0.3
                    px = -1
                else:
                    xp = 0.7
                    px = 1
            else:
                px = 0
                xp = 0.5
                if dy < 0:
                    py = -1
                    yp = 0.3
                else:
                    py = 1
                    yp = 0.7

            if px != self.last_px or py != self.last_py:
                if not self.first:
                    self.pad = [0, 0]
                else:
                    self.first = False

                self.pad = [px, py]
                self.last_px = px
                self.last_py = py

            self.ids.pad.pos_hint = {'center_x': xp, 'center_y': yp}

        return True

    def on_release(self):
        pass

    def on_press(self):
        pass


if __name__ == '__main__':
    from kivy.uix.boxlayout import BoxLayout
    Builder.load_string('''
<MainView>:
    hat: hat
    Label:
        text: "hello"
    Hat:
        id: hat
        on_release: print("Released")
        on_press: print("Pressed")
''')

    class MainView(BoxLayout):
        def on_kv_post(self, args):
            self.hat.bind(pad=self.on_pad)

        def on_pad(self, w, value):
            print("on pad: {}".format(value))

    from kivy.base import runTouchApp
    runTouchApp(MainView())
