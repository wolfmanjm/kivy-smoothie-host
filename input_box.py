from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.core.window import Window

Builder.load_string('''
<InputBox>:
    size_hint : (None,None)
    width : min(0.95 * self.window.width, dp(500))
    height: dp(content.height) + dp(80)
    title: "Option Title"
    pos_hint: {'top': 1} if app.is_desktop == 0 else {'center_y': 0.5}

    BoxLayout:
        id: content
        orientation: 'vertical'
        padding: '12dp'
        size_hint: (1, None)
        height: dp(content.minimum_height)
        spacing: '5dp'

        Label:
            text: root.text
            size_hint_y: None
            height: self.texture_size[1] + dp(16)
            text_size: self.width - dp(16), None
            halign: 'center'

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
    __events__ = ('on_ok', 'on_cancel')

    def __init__(self, **kwargs):
        self.window = Window
        super(InputBox, self).__init__(**kwargs)
        self.content = self.ids["content"]

    def on_open(self):
        self.ids.input.focus = True

    def ok(self):
        self.dispatch('on_ok')
        self.dismiss()

    def cancel(self):
        self.dispatch('on_cancel')
        self.dismiss()

    def on_ok(self):
        if self.cb:
            s = self.ids.input.text
            self.cb(s)

    def on_cancel(self):
        if self.cb:
            self.cb(None)
