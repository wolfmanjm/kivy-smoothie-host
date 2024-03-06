from kivy.properties import StringProperty, ObjectProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.app import App

Builder.load_string('''
<ConfirmBox>:
    size_hint: .5, None
    height: sp(content.height) + sp(140)
    auto_dismiss: False
    title: "Are you sure?"
    title_align: 'center'
    title_size: '20sp'
    BoxLayout:
        orientation: 'vertical'
        Label:
            text: root.text
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


class ConfirmBox(Popup):
    """ Same as Message box except callback is not called if the negative button is selected """
    text = StringProperty('')
    cb = ObjectProperty()

    ok_text = StringProperty('Yes')
    cancel_text = StringProperty('No')

    def ok(self):
        if self.cb:
            self.cb()
        self.dismiss()

    def cancel(self):
        self.dismiss()
