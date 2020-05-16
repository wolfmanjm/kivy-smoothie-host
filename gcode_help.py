from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty

Builder.load_string('''
<ScrollableLabel>:
    scroll_type: ['bars', 'content']
    scroll_wheel_distance: dp(114)
    bar_width: dp(10)
    Label:
        size_hint_y: None
        height: self.texture_size[1]
        text_size: self.width, None
        text: root.text
        font_name: "data/fonts/RobotoMono-Regular.ttf"

<GcodeHelp>:
    sl: sl
    BoxLayout:
        orientation: 'vertical'
        Button:
            size_hint: None, None
            size: 100, 40
            text: 'Back'
            on_press: root.close()
        ScrollableLabel:
            id: sl
''')


class ScrollableLabel(ScrollView):
    text = StringProperty('')


class GcodeHelp(Screen):
    def populate(self):
        a = []
        with open('gcodes.txt') as f:
            for line in f:
                c = line.split(' | ')
                if len(c) < 2:
                    continue
                g = c[0].strip()
                d = c[1].strip()
                n = 8 - len(g)
                s = ' ' * n
                a.append("{}{}{}".format(g, s, d))
        self.ids.sl.text = "\n".join(a)

    def close(self):
        self.ids.sl.text = ''
        self.manager.current = 'main'
