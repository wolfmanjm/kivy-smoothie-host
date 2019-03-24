from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread

from multi_input_box import MultiInputBox

Builder.load_string('''
<CERow@BoxLayout>:
    canvas.before:
        Color:
            rgba: 0.5, 0.5, 0.5, 1
        Rectangle:
            size: self.size
            pos: self.pos
    k: ''
    v: ''
    Label:
        text: root.k
        text_size: self.size
        size_hint_y: None
        height: sp(32)
        halign: 'left'
    TextInput:
        text: root.v
        size_hint_y: None
        height: sp(32)
        multiline: False
        on_text_validate: root.parent.parent.parent.parent.save_change(root.k, self.text)

<ConfigEditor>:
    rv: rv
    BoxLayout:
        canvas:
            Color:
                rgba: 0.3, 0.3, 0.3, 1
            Rectangle:
                size: self.size
                pos: self.pos
        orientation: 'vertical'
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(8)
            spacing: dp(16)
            Button:
                text: 'Back'
                on_press: root.close()
            Button:
                text: 'New Switch'
                on_press: root.new_switch()

            BoxLayout:
                spacing: dp(8)
                Button:
                    text: 'Enter new key'
                    on_press: root.insert(new_item_input.text)
                TextInput:
                    id: new_item_input
                    size_hint_x: 0.6
                    hint_text: 'value'
                    padding: dp(10), dp(10), 0, 0
                    multiline: False
                    on_text_validate: root.insert(self.text)

        RecycleView:
            id: rv
            scroll_type: ['bars', 'content']
            scroll_wheel_distance: dp(114)
            bar_width: dp(10)
            viewclass: 'CERow'
            RecycleBoxLayout:
                default_size: None, dp(32)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                spacing: dp(2)
''')

class ConfigEditor(Screen):

    @mainthread
    def _add_line(self, line):
        if not line.lstrip().startswith("#"):
            t= line.split()
            if len(t) >= 2:
                self.rv.data.append({'k': t[0], 'v': t[1]})
            elif t[0] == 'ok':
                self.app.comms.redirect_incoming(None)
                # add dummy lines at end so we can edit the last few lines without keyboard covering them
                for i in range(10):
                    self.rv.data.append({'k': '', 'v': ''})

    def populate(self):
        self.rv.data= []
        self.app= App.get_running_app()
        # get config, parse and populate
        self.app.comms.redirect_incoming(self._add_line)
        # issue command
        self.app.comms.write('cat /sd/config\n')
        self.app.comms.write('\n') # get an ok to indicate end of cat

    def insert(self, value):
        self.rv.data.insert(0, {'k': value, 'v': ''})

    def new_switch(self):
        o = MultiInputBox(title='Add Switch')
        o.setOptions(['Name', 'On Command', 'Off Command', 'Pin'], self._new_switch)
        o.open()

    def _new_switch(self, opts):
        if opts and opts['Name']:
            sw= "switch.{}".format(opts['Name'])
            self.rv.data.insert(0, {'k': "{}.input_off_command".format(sw), 'v': opts['Off Command']})
            self.rv.data.insert(0, {'k': "{}.input_on_command".format(sw), 'v': opts['On Command']})
            self.rv.data.insert(0, {'k': "{}.output_pin".format(sw), 'v': opts['Pin']})
            self.rv.data.insert(0, {'k': "{}.enable".format(sw), 'v': 'true'})
            for i in range(4):
                self.save_change(self.rv.data[i]['k'], self.rv.data[i]['v'])

    def save_change(self, k, v):
        if k == '': return # ignore the dummy lines
        self.app.comms.write("config-set sd {} {}\n".format(k, v))

    def close(self):
        self.app.comms.redirect_incoming(None)
        self.rv.data= []
        self.manager.current = 'main'
