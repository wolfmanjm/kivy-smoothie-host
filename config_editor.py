from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from multi_input_box import MultiInputBox


kv = """
<Row@BoxLayout>:
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
        on_text_validate: root.parent.parent.parent.save_change(root.k, self.text)
<ConfigEditor>:
    canvas:
        Color:
            rgba: 0.3, 0.3, 0.3, 1
        Rectangle:
            size: self.size
            pos: self.pos
    rv: rv
    orientation: 'vertical'
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: dp(8)
        spacing: dp(16)
        Button:
            text: 'Quit'
            on_press: app.stop()
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

    RecycleView:
        id: rv
        scroll_type: ['bars', 'content']
        scroll_wheel_distance: dp(114)
        bar_width: dp(10)
        viewclass: 'Row'
        RecycleBoxLayout:
            default_size: None, dp(32)
            default_size_hint: 1, None
            size_hint_y: None
            height: self.minimum_height
            orientation: 'vertical'
            spacing: dp(2)
"""

Builder.load_string(kv)


class ConfigEditor(BoxLayout):

    def populate(self):
        app= App.get_running_app()
        # capture response and populate
        l= []
        f= asyncio.Future()
        app.comms._reroute_incoming_data_to= lambda x: l.append(x) if not x.beginswith('ok') else f.set_result(None)
        # issue command
        app.comms.write('cat /sd/config\n')
        app.comms.write('\n') # get an ok to indicate end of cat
        # wait for it to complete
        # add a long timeout in case it fails and we don't want to wait for ever
        try:
            yield from asyncio.wait_for(f, 10)
        except asyncio.TimeoutError:
            self.log.warning("Comms: Timeout waiting for config")
            l= []

        for line in l:
            if line.lstrip().startswith("#"): continue
            t= line.split()
            if len(t) >= 2:
                self.rv.data.append({'k': t[0], 'v': t[1]})

        app.comms._reroute_incoming_data_to= None

    def insert(self, value):
        self.rv.data.insert(0, {'k': value, 'v': ''})

    def new_switch(self):
        o = MultiInputBox(title='Add Switch')
        o.setOptions(['Name', 'On Command', 'Off Command', 'pin'], self._new_switch)
        o.open()

    def _new_switch(self, opts):
        if opts and opts['Name']:
            sw= "switch.{}".format(opts['Name'])
            self.rv.data.insert(0, {'k': "{}.input_off_command".format(sw), 'v': opts['Off Command']})
            self.rv.data.insert(0, {'k': "{}.input_on_command".format(sw), 'v': opts['On Command']})
            self.rv.data.insert(0, {'k': "{}.output_pin".format(sw), 'v': opts['pin']})
            self.rv.data.insert(0, {'k': "{}.enable".format(sw), 'v': 'true'})
            for i in range(4):
                self.save_change(self.rv.data[i]['k'], self.rv.data[i]['v'])

    def save_change(self, k, v):
        print("config-set sd {} {}".format(k, v))
