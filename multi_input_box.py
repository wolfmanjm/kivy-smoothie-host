from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

Builder.load_string('''
<-MultiInputBox>:
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

        GridLayout:
            id: gl
            cols: 2
            padding: '12dp'
            size_hint_y: None
            height: dp(45)*len(root.inputs)

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

class MultiInputBox(Popup):
    inputs = ListProperty()
    cb = ObjectProperty()
    values= ListProperty()

    ok_text = StringProperty('OK')
    cancel_text = StringProperty('Cancel')
    wl= []

    __events__ = ('on_ok', 'on_cancel')

    def init(self):
        for b in self.inputs:
            self.ids.gl.add_widget(Label(text= b, halign= 'right'))
            tw= TextInput(multiline= False)
            self.ids.gl.add_widget(tw)
            self.wl.append(tw)

        self.open()

    def on_open(self):
        if self.wl:
            self.wl[0].focus= True

    def ok(self):
        for r in self.wl:
            self.values.append(r.text)

        self.dispatch('on_ok')
        self.dismiss()

    def cancel(self):
        self.dispatch('on_cancel')
        self.dismiss()

    def on_ok(self):
        if self.cb:
            self.cb(self)

    def on_cancel(self):
        pass
