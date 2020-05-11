from kivy.properties import StringProperty, ObjectProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.app import App

Builder.load_string('''
<MessageBox>:
    size_hint: .5, None
    height: dp(content.height) + dp(80)
    auto_dismiss: False
    title: root.text
    title_align: 'center'
    title_size: '20sp'
    BoxLayout:
        id: content
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

    def ok(self):
        if self.cb:
            self.cb(True)
        self.dismiss()

    def cancel(self):
        if self.cb:
            self.cb(False)
        self.dismiss()
