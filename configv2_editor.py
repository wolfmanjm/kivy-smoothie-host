from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.config import ConfigParser
from kivy.uix.settings import SettingsWithNoMenu
from kivy.uix.label import Label
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager, Screen

from multi_input_box import MultiInputBox

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
                text: 'Back'
                on_press: root.close()
            Button:
                size: 100, 40
                size_hint: None, None
                text: 'New Entry'
                on_press: root.new_entry();

        BoxLayout:
            id: placeholder
''')


class ConfigV2Editor(Screen):
    jsondata = []
    current_section = None
    config = None
    configdata = []
    msp = None

    def _add_line(self, line):
        ll = line.lstrip().rstrip()
        if not ll.startswith("#") and ll != "":
            if ll == "ok":
                # finished
                try:
                    self.config.read_string('\n'.join(self.configdata))
                except Exception as e:
                    Logger.error("ConfigV2Editor: Error parsing the config file: {}".format(e))
                    self.app.main_window.async_display("Error parsing config file, see log")
                    self.close()
                    return

                self.app.comms.redirect_incoming(None)
                self.configdata = []
                self._build()

            else:
                self.configdata.append(ll)

    def new_entry(self):
        o = MultiInputBox(title='Add new entry')
        o.setOptions(['section', 'key', 'value'], self._new_entry)
        o.open()

    def _new_entry(self, opts):
        if opts and opts['section'] and opts['key'] and opts['value']:
            self.app.comms.write("config-set \"{}\" {} {}\n".format(opts['section'], opts['key'], opts['value']))

    def open(self):
        self.app = App.get_running_app()
        self.ids.placeholder.add_widget(Label(text='Loading....'))
        self.manager.current = 'config_editor'
        self.config = ConfigParser.get_configparser('Smoothie Config')
        if self.config is None:
            self.config = ConfigParser(name='Smoothie Config')
        else:
            for section in self.config.sections():
                self.config.remove_section(section)

        # get config, parse and populate
        self.app.comms.redirect_incoming(self._add_line)
        # issue command
        self.app.comms.write('cat /sd/config.ini\n')
        self.app.comms.write('\n')  # get an ok to indicate end of cat

    @mainthread
    def _show(self):
        ss = self.ids.placeholder
        ss.clear_widgets()

        ss.add_widget(self.msp)
        self.jsondata = []

    def _build(self):
        for section in self.config.sections():
            self.current_section = section
            self.jsondata.append({"type": "title", "title": self.current_section})

            for (key, v) in self.config.items(section):
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

        self.msp = MySettingsPanel()
        self.msp.add_json_panel('Smoothie Config', self.config, data=json.dumps(self.jsondata))
        self._show()

    def close(self):
        self.app.comms.redirect_incoming(None)
        self.ids.placeholder.clear_widgets()
        if self.msp:
            self.msp.on_close()
            self.msp = None
        self.jsondata = []
        self.config = None
        self.manager.current = 'main'


class MySettingsPanel(SettingsWithNoMenu):
    def on_close(self):
        pass

    def on_config_change(self, config, section, key, value):
        app = App.get_running_app()
        app.comms.write('config-set "{}" {} {}\n'.format(section, key, value))
