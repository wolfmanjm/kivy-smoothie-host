from kivy.properties import StringProperty, ObjectProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.app import App
from kivy.core.text import Label as CoreLabel

Builder.load_string('''
<NoticeBox>:
    size_hint: .5, None
    height: sp(48+140)
    auto_dismiss: False
    title: root.text
    title_align: 'center'
    title_size: '20sp'

    BoxLayout:
        orientation: 'vertical'
        Label:
            text: root.additional_text
        Button:
            size_hint_y: None
            height: sp(48)
            text: root.ok_text
            on_press: root.ok()
''')


class NoticeBox(Popup):
    text = StringProperty('')
    cb = ObjectProperty()
    message = StringProperty('')
    ok_text = StringProperty('OK')
    additional_text = StringProperty('')

    def ok(self):
        if self.cb:
            self.cb(True)
        self.dismiss()
