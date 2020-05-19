
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen

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
            height: dp(40)
            padding: dp(8)
            spacing: dp(16)
            Button:
                text: 'Back'
                on_press: root.close()

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
    def populate(self):
        with open('gcodes.txt') as f:
            for line in f:
                c = line.split(' | ')
                if len(c) < 2:
                    continue
                g = c[0].strip()
                d = c[1].strip()
                self.rv.data.append({'gcode': g, 'desc': d})

    def close(self):
        self.rv.data = []
        self.manager.current = 'main'
