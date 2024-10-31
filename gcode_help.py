
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.logger import Logger
from kivy.properties import NumericProperty
import kivy.core.text

Builder.load_string('''
<GCHRow@Label>:
    canvas.before:
        Color:
            rgba: 0.5, 0.5, 0.5, 1
        Rectangle:
            size: self.size
            pos: self.pos
    text_size: self.size
    padding_x: dp(4)

<GcodeHelp>:
    rv: rv
    on_enter: root.populate('G')
    BoxLayout:
        canvas:
            Color:
                rgba: 0.3, 0.3, 0.3, 1
            Rectangle:
                size: self.size
                pos: self.pos
        rv: rv
        orientation: 'vertical'
        BoxLayout:
            size_hint_y: None
            height: 40
            Button:
                text: 'GCodes'
                on_press: root.populate('G')
            Button:
                text: 'MCodes'
                on_press: root.populate('M')
            Button:
                text: 'Commands'
                on_press: root.populate(' ')
            Button:
                text: '$Codes'
                on_press: root.populate('$')
            Button:
                text: 'Pins'
                on_press: root.populate('P')
            Button:
                text: 'Fnc'
                on_press: root.populate('F')
            Button:
                text: 'Back'
                on_press: root.close()

        RecycleView:
            id: rv
            scroll_type: ['bars', 'content']
            scroll_wheel_distance: dp(114)
            bar_width: dp(10)
            viewclass: 'GCHRow'
            RecycleGridLayout:
                cols: 2
                cols_minimum: {0: root.max_width, 1: 1280}
                default_size: None, dp(20)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(2)
''')


class GcodeHelp(Screen):
    max_width = NumericProperty(0)

    def _get_str_pixel_width(self, string, **kwargs):
        return kivy.core.text.Label(**kwargs).get_extents(string)[0]

    def populate(self, type):
        self.rv.data = []
        self.max_width = 0
        fn = '{}/gcodes.txt'.format(App.get_running_app().running_directory)
        try:
            with open(fn) as f:
                for line in f:
                    if line[0] == type or (type == ' ' and line[0].islower()):
                        c = line.split(' | ')
                        if len(c) < 2:
                            continue
                        g = c[0].strip()
                        d = c[1].strip()
                        w = self._get_str_pixel_width(g, font_name="data/fonts/RobotoMono-Regular.ttf", font_size=14) + kivy.metrics.dp(8)
                        if w > self.max_width:
                            self.max_width = w

                        self.rv.data.append({'text': g, 'font_name': "data/fonts/RobotoMono-Regular.ttf", 'font_size': 14})
                        self.rv.data.append({'text': d, 'font_name': "data/fonts/Roboto-Regular.ttf", 'font_size': 14})

        except Exception:
            Logger.error("GcodeHelp: Can't open {}".format(fn))

    def close(self):
        self.rv.data = []
        self.manager.current = 'main'
