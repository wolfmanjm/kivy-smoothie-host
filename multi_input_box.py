from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.core.window import Window

Builder.load_string('''
<MultiInputBox>:
    id: optionPopup
    size_hint : (None,None)
    width : min(0.95 * self.window.width, dp(500))
    height: dp(content.height) + dp(80)
    title: "Option Title"
    pos_hint: {'top': 1} if app.is_desktop == 0 else {'top': 0.5}
    BoxLayout:
        id: content
        size_hint : (1,None)
        orientation: 'vertical'
        spacing: '5dp'
        height: dp(content.minimum_height)
        GridLayout:
            id: contentButtons
            cols: 2
            padding: '12dp'
            size_hint : (1,None)
            height : dp(self.minimum_height)
            spacing: '0dp'

        BoxLayout:
            size_hint_y: None
            height: sp(48)

            Button:
                text: root.cancel_text
                on_press: root._dismiss()
            Button:
                text: root.ok_text
                on_press: root._ok()
''')

class MultiInputBox(Popup):
    ok_text = StringProperty('OK')
    cancel_text = StringProperty('Cancel')

    def __init__(self,**kwargs):
        self.window= Window
        super(MultiInputBox,self).__init__(**kwargs)
        self.content = self.ids["content"]
        self.contentButtons = self.ids["contentButtons"]
        self.wl= []

    def _dismiss(self):
        self.dismiss()

    def open(self):
        super(MultiInputBox,self).open()

    def _ok(self):
        if self.optionCallBack is not None:
            opts= {}
            for x in self.wl:
                opts[x[0]]= x[1].text
            self.optionCallBack(opts)
        self.dismiss()

    def on_open(self):
        if self.wl:
            self.wl[0][1].focus= True

    def setOptions(self, options, callBack):
        self.optionCallBack = callBack
        self.contentButtons.clear_widgets()
        self.wl= []
        for name in options:
            self.contentButtons.add_widget(Label(text= name, size_hint_y=None, height='30dp', halign= 'right'))
            tw= TextInput(multiline= False)
            self.contentButtons.add_widget(tw)
            self.wl.append((name, tw))
