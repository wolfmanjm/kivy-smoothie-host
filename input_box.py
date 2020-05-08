from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.core.window import Window

Builder.load_string('''
<InputBox>:
    size_hint : (None,None)
    width : min(0.95 * self.window.width, dp(500))
    height: dp(content.height) + dp(80)
    title: root.text
    pos_hint: {'top': 1} if app.is_desktop == 0 else {'center_y': 0.5}
    auto_dismiss: False

    BoxLayout:
        id: content
        orientation: 'vertical'
        padding: '12dp'
        size_hint: (1, None)
        height: dp(content.minimum_height)
        spacing: '5dp'

        TextInput:
            id: input
            size_hint_y: None
            height: sp(32)
            text: root.value
            multiline: False
            use_bubble: False
            use_handles: False

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


class InputBox(Popup):
    text = StringProperty('')
    value = StringProperty('')
    cb = ObjectProperty()

    ok_text = StringProperty('OK')
    cancel_text = StringProperty('Cancel')

    def __init__(self, **kwargs):
        self.window = Window
        super(InputBox, self).__init__(**kwargs)
        self.content = self.ids["content"]

    def on_open(self):
        self.ids.input.focus = True

    def ok(self):
        if self.cb:
            s = self.ids.input.text
            self.cb(s)
        self.dismiss()

    def cancel(self):
        if self.cb:
            self.cb(None)
        self.dismiss()
