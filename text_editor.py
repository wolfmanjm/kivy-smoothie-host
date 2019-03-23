
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen

Builder.load_string('''
<TextEditor>:
    te: te
    BoxLayout:
        canvas:
            Color:
                rgba: 0.3, 0.3, 0.3, 1
            Rectangle:
                size: self.size
                pos: self.pos
        te: te
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
                on_press: te.readonly= False
            Button:
                text: 'Save'
                on_press: root.save()

        TextInput:
            id: te
            readonly: True
            text: ""
''')

class TextEditor(Screen):
    def open(self, fn):
        with open(fn) as f:
            self.te.text= f.read()
        self.te.cursor= (0,0)

    def close(self):
        self.te.text= ""
        self.manager.current = 'main'

    def save(self):
        print(self.te.text)
