
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen

Builder.load_string('''
<Row@BoxLayout>:
    value: ''
    TextInput:
        text: root.value
        multiline: False
        readonly: Falsef

<TextEditor>:
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
            height: dp(60)
            padding: dp(8)
            spacing: dp(16)
            Button:
                text: 'Close'
                on_press: root.close()
            Button:
                text: 'Edit'
                on_press: root.set_edit()
            Button:
                text: 'Save'
                on_press: root.save()

        RecycleView:
            id: rv
            scroll_type: ['bars', 'content']
            scroll_wheel_distance: dp(114)
            bar_width: dp(10)
            viewclass: 'Row'
            RecycleBoxLayout:
                default_size: None, dp(32)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
''')

class TextEditor(Screen):
    def open(self, fn):
        with open(fn) as f:
            for line in f:
                self.rv.data.append({'value': line.rstrip()})

    def close(self):
        self.rv.data= []
        self.manager.current = 'main'

    def save(self):
        for l in self.rv.data:
            print(l)

    def set_edit(self):
        pass
