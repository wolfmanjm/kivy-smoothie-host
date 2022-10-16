from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.config import ConfigParser
from kivy.uix.settings import SettingsWithNoMenu
from kivy.uix.label import Label
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager, Screen

from multi_input_box import MultiInputBox

from functools import partial
import json
import configparser
import threading

Builder.load_string('''
<ConfigV2Editor>:
    placeholder: placeholder
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
                text: 'New Entry'
                on_press: root.new_entry();
            Button:
                text: 'New Output Switch'
                on_press: root.new_switch(True);
            Button:
                text: 'New Input Switch'
                on_press: root.new_switch(False);
            Button:
                text: 'Back'
                on_press: root.close()

        BoxLayout:
            id: placeholder
            orientation: 'vertical'
''')


class ConfigV2Editor(Screen):
    jsondata = []
    current_section = None
    config = None
    configdata = []
    msp = None
    force_close = False
    start = False
    progress = None
    count = 0

    def new_entry(self):
        o = MultiInputBox(title='Add new entry')
        o.setOptions(['section', 'key', 'value'], self._new_entry)
        o.open()

    def _new_entry(self, opts):
        if opts and opts['section'] and opts['key'] and opts['value']:
            self.app.comms.write("config-set \"{}\" {} {}\n".format(opts['section'], opts['key'], opts['value']))

    def new_switch(self, flg):
        o = MultiInputBox(title='Add {} Switch'.format('Output' if flg else 'Input'))
        if flg:
            o.setOptions(['Name', 'On Command', 'Off Command', 'Pin'], partial(self._new_switch, flg))
        else:
            o.setOptions(['Name', 'Command', 'Pin'], partial(self._new_switch, flg))

        o.open()

    def _new_switch(self, flg, opts):
        if opts and opts['Name']:
            sw = opts['Name']
            self.app.comms.write("config-set switch {}.enable = true\n".format(sw))
            if flg:
                for k, v in {'Off Command': 'input_off_command', 'On Command': 'input_on_command', 'Pin': 'output_pin'}.items():
                    self.app.comms.write("config-set switch {}.{} = {}\n".format(sw, v, opts[k]))
            else:
                for k, v in {'Command': 'output_on_command', 'Pin': 'input_pin'}.items():
                    self.app.comms.write("config-set switch {}.{} = {}\n".format(sw, v, opts[k]))

    def _add_line(self, line):
        if not self.start:
            return

        ll = line.lstrip().rstrip()
        self.count += 1
        if self.count > 10:
            self._update_progress(ll)
            self.count = 0

        if not ll.startswith("#") and ll != "":
            if ll == "ok":
                # finished
                self.start = False
                self._update_progress("Processing config....")

                # run the build in a thread as it is so slow
                Logger.debug("ConfigV2Editor: starting build")
                t = threading.Thread(target=self._build, daemon=True)
                t.start()

            else:
                self.configdata.append(ll)

    def open(self):
        self.force_close = False
        self.start = False
        self.app = App.get_running_app()
        self.ids.placeholder.add_widget(Label(text='Loading.... This may take a while!'))
        self.progress = Label(text="Current line....")
        self.ids.placeholder.add_widget(self.progress)

        self.manager.current = 'config_editor'
        self.config = ConfigParser.get_configparser('Smoothie Config')
        if self.config is None:
            self.config = ConfigParser(name='Smoothie Config')
        else:
            for section in self.config.sections():
                self.config.remove_section(section)

        # get config, parse and populate
        self.start = False
        self.app.comms.redirect_incoming(self._add_line)

        # wait for any outstanding queries
        Clock.schedule_once(self._send_command, 1)

    def _send_command(self, dt):
        # issue command
        Logger.debug("ConfigV2Editor: fetching config.ini")
        self.start = True
        self.app.comms.write('cat /sd/config.ini\n')
        self.app.comms.write('\n')  # get an ok to indicate end of cat

    def _build(self):
        self.app.comms.redirect_incoming(None)

        try:
            self.config.read_string('\n'.join(self.configdata))

        except Exception as e:
            Logger.error("ConfigV2Editor: Error parsing the config file: {}".format(e))
            self.app.main_window.async_display("Error parsing config file, see log")
            self.close()
            return

            self.configdata = []

        for section in self.config.sections():
            self._update_progress(section)
            self.current_section = section
            self.jsondata.append({"type": "title", "title": self.current_section})

            for (key, v) in self.config.items(section):
                if self.force_close:
                    return

                o = v.find('#')
                if o > 0:
                    # convert comment into desc and strip from value
                    comment = v[o + 1:]
                    v = v[0:o].rstrip()
                    self.config.set(section, key, v)
                else:
                    comment = ""

                if v in ['true', 'false']:
                    tt = {"type": 'bool', 'values': ['false', 'true'], "title": key, "desc": comment, "section": section, "key": key}
                else:
                    tt = {"type": 'string', "title": key, "desc": comment, "section": self.current_section, "key": key}
                self.jsondata.append(tt)

        self._done()

    @mainthread
    def _update_progress(self, sec):
        if self.progress is not None:
            self.progress.text = sec
            self.progress.texture_update()

    @mainthread
    def _done(self):
        self.msp = MySettingsPanel()
        self.msp.add_json_panel('Smoothie Config', self.config, data=json.dumps(self.jsondata))
        ss = self.ids.placeholder
        ss.clear_widgets()
        ss.add_widget(self.msp)
        self.jsondata = []
        self.progress = None

    @mainthread
    def close(self):
        self.force_close = True
        self.app.comms.redirect_incoming(None)
        self.ids.placeholder.clear_widgets()
        if self.msp:
            self.msp.on_close()
            self.msp = None
        self.jsondata = []
        self.configdata = []
        self.config = None
        self.progress = None
        self.manager.current = 'main'


class MySettingsPanel(SettingsWithNoMenu):
    def __init__(self, *args, **kwargs):
        super(MySettingsPanel, self).__init__(*args, **kwargs)
        # if App.get_running_app().is_desktop <= 1:
        #     # For RPI gets the instance of the ContentPanel which is a ScrollView
        #     # and sets the friction attr in the effects
        #     # This may only work with an panel of type SettingsWithNoMenu
        #     self.interface.effect_y.friction = 1.0

    def on_close(self):
        pass

    def on_config_change(self, config, section, key, value):
        app = App.get_running_app()
        app.comms.write('config-set "{}" {} "{}"\n'.format(section, key, value))
