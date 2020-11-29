
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.logger import Logger

Builder.load_string('''
<GCHRow@BoxLayout>:
    canvas.before:
        Color:
            rgba: 0.5, 0.5, 0.5, 1
        Rectangle:
            size: self.size
            pos: self.pos
    gcode: ''
    desc: ''
    Label:
        text: root.gcode
        size_hint_x: None
        width: self.texture_size[0] + dp(16)
        font_name: "data/fonts/RobotoMono-Regular.ttf"
    Label:
        text: root.desc
        text_size: self.size

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
                text: 'Back'
                on_press: root.close()
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

        RecycleView:
            id: rv
            scroll_type: ['bars', 'content']
            scroll_wheel_distance: dp(114)
            bar_width: dp(10)
            viewclass: 'GCHRow'
            RecycleBoxLayout:
                default_size: None, dp(20)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                spacing: dp(2)
''')


class GcodeHelp(Screen):
    def populate(self, type):
        self.rv.data = []
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
                        self.rv.data.append({'gcode': g, 'desc': d})
        except Exception:
            Logger.error("GcodeHelp: Can't open {}".format(fn))

    def close(self):
        self.rv.data = []
        self.manager.current = 'main'
