from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.config import ConfigParser
from kivy.uix.settings import Settings
from kivy.uix.label import Label
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import NumericProperty, BooleanProperty, ListProperty, ObjectProperty

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

<InterfaceWithScrollableSidebar>:
    orientation: 'horizontal'
    menu: menu
    content: content
    MyMenuSidebar:
        id: menu
    ContentPanel:
        id: content
        current_uid: menu.selected_uid

<MyMenuSidebar>:
    size_hint_x: None
    width: '200dp'
    buttons_layout: menu
    ScrollView:
        GridLayout:
            size_hint_y: None
            height: self.minimum_height
            pos: root.pos
            cols: 1
            id: menu
            padding: 5

            canvas.after:
                Color:
                    rgb: .2, .2, .2
                Rectangle:
                    pos: self.right - 1, self.y
                    size: 1, self.height
''')


class ConfigV2Editor(Screen):
    sections = None
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

        sections = []
        for section in self.config.sections():
            self._update_progress(section)
            subkeys = {}

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

                if '.' in key:
                    (subkey, k) = key.split('.')
                    x = (k, key, v, comment)

                else:
                    subkey = " "
                    x = (key, key, v, comment)

                if subkey in subkeys:
                    subkeys[subkey].append(x)
                else:
                    subkeys[subkey] = [x]

            jsondata = []
            for t, l in subkeys.items():
                if t != " ":
                    jsondata.append({"type": "title", "title": t})

                for i in l:
                    tit, key, v, comment = i
                    if v in ['true', 'false']:
                        tt = {"type": 'bool', 'values': ['false', 'true'], "title": tit, "desc": comment, "section": section, "key": key}
                    else:
                        tt = {"type": 'string', "title": tit, "desc": comment, "section": section, "key": key}
                    jsondata.append(tt)
            sections.append((section, json.dumps(jsondata)))

        self.sections = sections
        self._done()

    @mainthread
    def _update_progress(self, sec):
        if self.progress is not None:
            self.progress.text = sec
            self.progress.texture_update()

    @mainthread
    def _done(self):
        self._update_progress("Creating Settings Panel....")

        self.msp = MySettingsPanel()
        for s in self.sections:
            self.msp.add_json_panel(s[0], self.config, data=s[1])

        ss = self.ids.placeholder
        ss.clear_widgets()
        ss.add_widget(self.msp)
        self.sections = None
        self.progress = None

    @mainthread
    def close(self):
        self.manager.current = 'main'
        self.force_close = True
        self.app.comms.redirect_incoming(None)
        self.ids.placeholder.clear_widgets()
        if self.msp:
            self.msp.on_close()

        self.sections = None
        self.configdata = []
        self.config = None
        self.progress = None


class MyMenuSidebar(FloatLayout):
    selected_uid = NumericProperty(0)
    buttons_layout = ObjectProperty(None)
    close_button = ObjectProperty(None)

    def add_item(self, name, uid):
        label = SettingSidebarLabel(text=name, uid=uid, menu=self)
        if len(self.buttons_layout.children) == 0:
            label.selected = True
        if self.buttons_layout is not None:
            self.buttons_layout.add_widget(label)

    def on_selected_uid(self, *args):
        for button in self.buttons_layout.children:
            if button.uid != self.selected_uid:
                button.selected = False


class SettingSidebarLabel(Label):
    selected = BooleanProperty(False)
    uid = NumericProperty(0)
    menu = ObjectProperty(None)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return
        self.selected = True
        self.menu.selected_uid = self.uid


class InterfaceWithScrollableSidebar(BoxLayout):
    menu = ObjectProperty()
    content = ObjectProperty()

    def __init__(self, *args, **kwargs):
        super(InterfaceWithScrollableSidebar, self).__init__(*args, **kwargs)

    def add_panel(self, panel, name, uid):
        self.menu.add_item(name, uid)
        self.content.add_panel(panel, name, uid)


class MySettingsPanel(Settings):
    def __init__(self, *args, **kwargs):
        self.interface_cls = InterfaceWithScrollableSidebar
        super(MySettingsPanel, self).__init__(*args, **kwargs)
        # if App.get_running_app().is_desktop <= 1:
        #     # For RPI gets the instance of the ContentPanel which is a ScrollView
        #     # and sets the friction attr in the effects
        #     # This may only work with an panel of type SettingsWithNoMenu
        #     self.interface.effect_y.friction = 1.0

    def on_close(self):
        print("Closing MySettingsPanel")

    def on_config_change(self, config, section, key, value):
        app = App.get_running_app()
        app.comms.write('config-set "{}" {} "{}"\n'.format(section, key, value))
