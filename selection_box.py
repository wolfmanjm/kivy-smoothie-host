from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup

Builder.load_string('''
<-SelectionBox>:
    BoxLayout:
        orientation: 'vertical'
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

        Spinner:
            id: selection
            size_hint_y: None
            height: sp(48)
            #is_open: True
            text: root.values[0]
            values: root.values

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

class SelectionBox(Popup):
    text = StringProperty('')
    values = ListProperty([])
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
            s= self.ids.selection.text
            self.cb(s)

    def on_cancel(self):
        if self.cb:
            self.cb(None)
