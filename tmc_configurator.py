from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread
from kivy.properties import NumericProperty, BooleanProperty

'''
    M911.3 S1 [Unnn Vnnn Wnnn Xnnn Ynnn] - setSpreadCycleChopper
              U=constant_off_time, V=blank_time, W=hysteresis_start, X=hysteresis_end, Y=hysteresis_decrement

    TODO
        select motor or all motors
        dump registers for inclusion in config (or set config)
        add hysteresis sliders for setSpreadCycleChopper
        maybe allow setting of ConstantOffTimeChopper
'''


Builder.load_string('''
<TMCConfigurator>:
    BoxLayout:
        canvas:
            Color:
                rgba: 0.3, 0.3, 0.3, 1
            Rectangle:
                size: self.size
                pos: self.pos
        orientation: 'vertical'
        BoxLayout:
            orientation: 'horizontal'
            BoxLayout:
                orientation: 'vertical'
                Label:
                    size_hint_y: None
                    height: 40
                    text: 'Constant Off Time'
                Label:
                    size_hint_y: None
                    height: 40
                    text: str(int(s1.value))
                Slider: # constant off time
                    id: s1
                    orientation: 'vertical'
                    min: 2
                    max: 15
                    value: root.constant_off_time
                    on_value: root.set_constant_off_time(self.value)
            BoxLayout:
                orientation: 'vertical'
                Label:
                    size_hint_y: None
                    height: 40
                    text: 'Blank Time'
                Label:
                    size_hint_y: None
                    height: 40
                    text: str(int(s2.value))
                Slider: # blank time
                    id: s2
                    orientation: 'vertical'
                    min: 24
                    max: 54
                    value: root.blank_time
                    on_value: root.set_blank_time(self.value)

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(60)
            padding: dp(8)
            spacing: dp(16)
            ToggleButton:
                text: 'PFD'
                state: 'down' if root.pfd else 'normal'
                on_state: root.set_pfd(self.state == 'down')
            ToggleButton:
                text: 'RoT'
                state: 'down' if root.rot else 'normal'
                on_state: root.set_rot(self.state == 'down')
            Button:
                text: 'Enable Motors'
                on_press: root.enable_motors()
            GridLayout:
                rows: 2
                Label:
                    text: 'X'
                CheckBox:
                    id: enx
                    active: True
                    on_active: root.set_enabled('X', self.active)
                Label:
                    text: 'Y'
                CheckBox:
                    id: eny
                    active: True
                    on_active: root.set_enabled('Y', self.active)
                Label:
                    text: 'Z'
                CheckBox:
                    id: enz
                    active: True
                    on_active: root.set_enabled('Z', self.active)
                Label:
                    text: 'A'
                CheckBox:
                    id: ena
                    active: True
                    on_active: root.set_enabled('A', self.active)

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(60)
            padding: dp(8)
            spacing: dp(16)
            Button:
                text: 'Save'
                on_press: root.save_settings()
            Button:
                text: 'Back'
                on_press: root.close()
''')


class TMCConfigurator(Screen):
    constant_off_time = NumericProperty(5)
    blank_time = NumericProperty(54)
    pfd = BooleanProperty(True)
    rot = BooleanProperty(False)
    enabled_list = {'X': True, 'Y': True, 'Z': True, 'A': True}
    motor_lut = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}

    def set_enabled(self, axis, flg):
        # print("enabled: {} {}".format(axis, flg))
        self.enabled_list[axis] = flg

    def enable_motors(self):
        args = ""
        for a in self.enabled_list:
            if not self.enabled_list[a]:
                args += "{}0 ".format(a)

        self.send_command('M17')  # turn them all on
        if args:
            self.send_command('M18 {}'.format(args))  # disable selected ones

    def are_all_enabled(self):
        ok = True
        for a in self.enabled_list:
            if not self.enabled_list[a]:
                ok = False

        return ok

    def set_constant_off_time(self, v):
        self.constant_off_time = int(v)
        if self.are_all_enabled():
            self.send_command('M911.3 S1 U{}'.format(self.constant_off_time))
        else:
            for a in self.enabled_list:
                if self.enabled_list[a]:
                    self.send_command('M911.3 P{} S1 U{}'.format(self.motor_lut[a], self.constant_off_time))

    def set_blank_time(self, v):
        self.blank_time = int(v)
        if self.are_all_enabled():
            self.send_command('M911.3 S1 V{}'.format(self.blank_time))
        else:
            for a in self.enabled_list:
                if self.enabled_list[a]:
                    self.send_command('M911.3 P{} S1 V{}'.format(self.motor_lut[a], self.blank_time))

    def set_pfd(self, v):
        self.pfd = v
        if self.are_all_enabled():
            self.send_command('M911.3 S6 Z{}'.format("1" if self.pfd else "0"))
        else:
            for a in self.enabled_list:
                if self.enabled_list[a]:
                    self.send_command('M911.3 P{} S6 Z{}'.format(self.motor_lut[a], "1" if self.pfd else "0"))

    def set_rot(self, v):
        self.rot = v
        if self.are_all_enabled():
            self.send_command('M911.3 S2 Z{}'.format("1" if self.rot else "0"))
        else:
            for a in self.enabled_list:
                if self.enabled_list[a]:
                    self.send_command('M911.3 P{} S2 Z{}'.format(self.motor_lut[a], "1" if self.rot else "0"))

    def save_settings(self):
        # self.app.comms.write("config-set sd {} {}\n".format(k, v))
        pass

    def close(self):
        self.manager.current = 'main'

    def send_command(self, args):
        App.get_running_app().comms.write('{}\n'.format(args))
