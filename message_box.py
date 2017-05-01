from kivy.properties import StringProperty, ObjectProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.app import App

Builder.load_string('''
<-MessageBox>:
    GridLayout:
        cols: 1
        padding: '12dp'
        pos_hint: {'center': (0.5, 0.5)}
        size_hint_x: 0.66
        size_hint_y: None
        height: self.minimum_height

        canvas:
            Color:
                rgba: root.background_color[:3] + [root.background_color[-1] * root._anim_alpha]
            Rectangle:
                size: root._window.size if root._window else (0, 0)

            Color:
                rgb: 1, 1, 1
            BorderImage:
                source: root.background
                border: root.border
                pos: self.pos
                size: self.size

        Label:
            text: root.text
            size_hint_y: None
            height: self.texture_size[1] + dp(16)
            text_size: self.width - dp(16), None
            halign: 'center'

        BoxLayout:
            size_hint_y: None
            height: sp(48)

            Button:
                text: root.cancel_text
                on_press: root.cancel()
            Button:
                text: root.ok_text
                on_press: root.ok()
''')

class MessageBox(Popup):
    text = StringProperty('')
    cb = ObjectProperty()

    ok_text = StringProperty('OK')
    cancel_text = StringProperty('Cancel')

    __events__ = ('on_ok', 'on_cancel')

    def ok(self):
        self.dispatch('on_ok')
        self.dismiss()

    def cancel(self):
        self.dispatch('on_cancel')
        self.dismiss()

    def on_ok(self):
        if self.cb:
            self.cb(True)

    def on_cancel(self):
        if self.cb:
            self.cb(False)
