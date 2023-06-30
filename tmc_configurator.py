from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread, Clock
from kivy.properties import NumericProperty, BooleanProperty
from kivy.logger import Logger

Builder.load_string('''
<TMCConfigurator>:
    on_enter: self.start()
    BoxLayout:
        disabled: not app.is_connected or app.main_window.is_printing
        canvas:
            Color:
                rgba: 0.3, 0.3, 0.3, 1
            Rectangle:
                size: self.size
                pos: self.pos
        orientation: 'vertical'

        TabbedPanel:
            id: modes
            do_default_tab: False
            tab_pos: 'top_left'
            tab_width: dp(160)
            on_current_tab: root.tab_changed()

            TabbedPanelItem:
                id: sc_tab
                text: 'SpreadCycle'
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
                        orientation: 'vertical'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: 'Hyst start'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: str(int(s3.value))
                        Slider:
                            id: s3
                            orientation: 'vertical'
                            min: 1
                            max: 8
                            value: root.hysteresis_start
                            on_value: root.set_hysteresis_start(self.value)
                    BoxLayout:
                        orientation: 'vertical'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: 'Hyst end'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: str(int(s4.value))
                        Slider:
                            id: s4
                            orientation: 'vertical'
                            min: -3
                            max: 12
                            value: root.hysteresis_end
                            on_value: root.set_hysteresis_end(self.value)
                    BoxLayout:
                        orientation: 'vertical'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: 'Hyst dec'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: str(int(s5.value))
                        Slider:
                            id: s5
                            orientation: 'vertical'
                            min: 0
                            max: 3
                            value: root.hysteresis_dec
                            on_value: root.set_hysteresis_dec(self.value)

            TabbedPanelItem:
                id: cot_tab
                text: 'ConstantOffTime'
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
                            text: str(int(s15.value))
                        Slider: # constant off time
                            id: s15
                            orientation: 'vertical'
                            min: 2
                            max: 15
                            value: root.cotc_constant_off_time
                            on_value: root.set_cotc_constant_off_time(self.value)
                    BoxLayout:
                        orientation: 'vertical'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: 'Blank Time'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: str(int(s6.value))
                        Slider: # blank time
                            id: s6
                            orientation: 'vertical'
                            min: 24
                            max: 54
                            value: root.cotc_blank_time
                            on_value: root.set_cotc_blank_time(self.value)

                    BoxLayout:
                        orientation: 'vertical'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: 'Fast Decay Time'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: str(int(s7.value))
                        Slider:
                            id: s7
                            orientation: 'vertical'
                            min: 0
                            max: 15
                            value: root.fast_decay_time
                            on_value: root.set_fast_decay_time(self.value)
                    BoxLayout:
                        orientation: 'vertical'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: 'Sine Wave Offset'
                        Label:
                            size_hint_y: None
                            height: 40
                            text: str(int(s8.value))
                        Slider:
                            id: s8
                            orientation: 'vertical'
                            min: -3
                            max: 12
                            value: root.sine_wave_offset
                            on_value: root.set_sine_wave_offset(self.value)
                    BoxLayout:
                        orientation: 'vertical'
                        ToggleButton:
                            size_hint_y: None
                            height: dp(60)
                            text: 'Use Current Comparator'
                            state: 'down' if root.use_current_comparator else 'normal'
                            on_state: root.set_use_current_comparator(self.state == 'down')

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
            ToggleButton:
                text: 'Step interpoln'
                state: 'down' if root.step_interpolation else 'normal'
                on_state: root.set_step_interpolation(self.state == 'down')
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
                    group: 'enb'
                    on_active: root.set_enabled('X', self.active)
                Label:
                    text: 'Y'
                CheckBox:
                    id: eny
                    active: True
                    group: 'enb'
                    on_active: root.set_enabled('Y', self.active)
                Label:
                    text: 'Z'
                CheckBox:
                    id: enz
                    active: True
                    group: 'enb'
                    on_active: root.set_enabled('Z', self.active)
                Label:
                    text: 'A'
                CheckBox:
                    id: ena
                    active: True
                    group: 'enb'
                    on_active: root.set_enabled('A', self.active)

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(60)
            padding: dp(8)
            spacing: dp(16)
            ToggleButton:
                text: 'Run'
                state: 'normal'
                on_state: root.set_run(self.state == 'down')

            Button:
                text: 'Save'
                on_press: root.save_settings()
            Button:
                text: 'Reset'
                on_press: root.reset_settings()
            Button:
                text: 'Back'
                on_press: root.close()

        Label:
            id: messages
            size_hint_y: None
            height: 40
            text: 'status'
''')


class TMCConfigurator(Screen):
    default_sc_settings = [5, 54, 5, 0, 0]
    constant_off_time = NumericProperty(default_sc_settings[0])
    blank_time = NumericProperty(default_sc_settings[1])
    hysteresis_start = NumericProperty(default_sc_settings[2])
    hysteresis_end = NumericProperty(default_sc_settings[3])
    hysteresis_dec = NumericProperty(default_sc_settings[4])

    # ConstantOffTimeChopper
    default_cot_settings = [7, 54, 13, 12, 1]
    cotc_constant_off_time = NumericProperty(default_cot_settings[0])
    cotc_blank_time = NumericProperty(default_cot_settings[1])
    fast_decay_time = NumericProperty(default_cot_settings[2])
    sine_wave_offset = NumericProperty(default_cot_settings[3])
    use_current_comparator = BooleanProperty(default_cot_settings[4] == 1)

    pfd = BooleanProperty(True)
    rot = BooleanProperty(False)
    step_interpolation = BooleanProperty(True)

    move_timer = None
    direction = False
    waiting = False
    switch_requested = True

    enabled_list = {'X': True, 'Y': False, 'Z': False, 'A': False}
    motor_lut = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}
    current_motor = 0

    def start(self):
        if App.get_running_app().is_connected:
            # get current settings for selected motor
            self.get_chop_register()
        else:
            App.get_running_app().main_window.display("Must be connected to use TMC Configurator")
            self.close()

    def tab_changed(self):
        name = self.ids.modes.current_tab.text
        print("tab changed to {} - {}".format(name, self.switch_requested))
        if self.switch_requested:
            # reset to default settings relevant for mode
            if name == 'SpreadCycle':
                self.set_default_settings(True)
            else:
                self.set_default_settings(False)

        else:
            self.switch_requested = True

    def set_enabled(self, axis, flg):
        # print("enabled: {} {}".format(axis, flg))
        self.enabled_list[axis] = flg
        if flg:
            self.current_motor = self.motor_lut[axis]
            self.get_chop_register()

        self.enable_motors()

    def enable_motors(self):
        enabled = ""
        args = ""
        for a in self.enabled_list:
            if not self.enabled_list[a]:
                args += "{}0 ".format(a)
            else:
                enabled += "{} ".format(a)

        self.send_command('M17')  # turn them all on
        if args:
            self.send_command('M18 {}'.format(args))  # disable selected ones

        self.set_message("Enabled motor(s) {}".format(enabled))

    def are_all_enabled(self):
        ok = True
        for a in self.enabled_list:
            if not self.enabled_list[a]:
                ok = False

        return ok

    # SpreadCycleChopper

    def set_constant_off_time(self, v):
        self.constant_off_time = v
        self.send_M911_command('S1 U{}'.format(self.constant_off_time))

    def set_blank_time(self, v):
        self.blank_time = v
        self.send_M911_command('S1 V{}'.format(self.blank_time))

    def set_hysteresis_start(self, v):
        self.hysteresis_start = v
        self.send_M911_command('S1 W{}'.format(self.hysteresis_start))

    def set_hysteresis_end(self, v):
        self.hysteresis_end = v
        self.send_M911_command('S1 X{}'.format(self.hysteresis_end))

    def set_hysteresis_dec(self, v):
        self.hysteresis_dec = v
        self.send_M911_command('S1 Y{}'.format(self.hysteresis_dec))

    # ConstantOffTimeChopper

    def set_cotc_constant_off_time(self, v):
        self.cotc_constant_off_time = v
        self.send_M911_command('S0 U{}'.format(self.cotc_constant_off_time))

    def set_cotc_blank_time(self, v):
        self.cotc_blank_time = v
        self.send_M911_command('S0 V{}'.format(self.cotc_blank_time))

    def set_fast_decay_time(self, v):
        self.fast_decay_time = v
        self.send_M911_command('S0 W{}'.format(self.fast_decay_time))

    def set_sine_wave_offset(self, v):
        self.sine_wave_offset = v
        self.send_M911_command('S0 X{}'.format(self.sine_wave_offset))

    def set_use_current_comparator(self, v):
        self.use_current_comparator = v
        self.send_M911_command('S0 Y{}'.format("1" if self.use_current_comparator else "0"))

    # other settings

    def set_pfd(self, v):
        self.pfd = v
        self.send_M911_command('S6 Z{}'.format("1" if self.pfd else "0"))

    def set_rot(self, v):
        self.rot = v
        self.send_M911_command('S2 Z{}'.format("1" if self.rot else "0"))

    def set_step_interpolation(self, v):
        self.step_interpolation = v
        self.send_M911_command('S4 Z{}'.format("1" if self.step_interpolation else "0"))

    def _move_motors(self, arg):
        d = '-10' if self.direction else '10'
        self.direction = not self.direction

        for a in self.enabled_list:
            if self.enabled_list[a]:
                self.send_command("M120 G91 G1 {}{} F100 M121".format(a, d))

    def set_run(self, v):
        if v:
            # run selected motors up and down
            self._move_motors(None)
            self.move_timer = Clock.schedule_interval(self._move_motors, 7)

        else:
            # stop motors
            if self.move_timer:
                self.move_timer.cancel()
                self.move_timer = None

    def set_default_settings(self, scflg):
        if scflg:
            self.set_constant_off_time(self.default_sc_settings[0])
            self.set_blank_time(self.default_sc_settings[1])
            self.set_hysteresis_start(self.default_sc_settings[2])
            self.set_hysteresis_end(self.default_sc_settings[3])
            self.set_hysteresis_dec(self.default_sc_settings[4])

        else:
            self.set_cotc_constant_off_time(self.default_cot_settings[0])
            self.set_cotc_blank_time(self.default_cot_settings[1])
            self.set_fast_decay_time(self.default_cot_settings[2])
            self.set_sine_wave_offset(self.default_cot_settings[3])
            self.set_use_current_comparator(self.default_cot_settings[4] == 1)

        self.set_pfd(True)
        self.set_rot(False)

    def reset_settings(self):
        self.set_default_settings(True)
        self.switch_to_cot_tab(False)

    def save_settings(self):
        self.send_command('M911 P{}'.format(self.current_motor))

    def close(self):
        self.manager.current = 'main'

    def send_M911_command(self, cmd):
        if self.are_all_enabled():
            self.send_command('M911.3 {}'.format(cmd))
        else:
            for a in self.enabled_list:
                if self.enabled_list[a]:
                    self.send_command('M911.3 {} P{}'.format(cmd, self.motor_lut[a]))

    def send_command(self, args):
        App.get_running_app().comms.write('{}\n'.format(args))
        self.set_message("Sent: {}".format(args))

    def set_message(self, v):
        self.ids.messages.text = v

    @mainthread
    def switch_to_cot_tab(self, arg):
        ct = self.ids.modes.current_tab.text
        if arg and ct != 'ConstantOffTime':
            self.switch_requested = False
            self.ids.modes.switch_to(self.ids.cot_tab)
        elif not arg and ct != 'SpreadCycle':
            self.switch_requested = False
            self.ids.modes.switch_to(self.ids.sc_tab)

    def _response(self, line):
        if not self.waiting:
            # Not sent command yet, anything we get is probably a query response
            return

        ll = line.lstrip().rstrip()
        if ll == "ok":
            App.get_running_app().comms.redirect_incoming(None)
            return

        ll = ll.split(',')

        if len(ll) < 7:
            Logger.warning("TMCConfigurator: WARNING - unexpected response size {}".format(len(ll)))

        elif ll[0] not in ['X', 'Y', 'Z', 'A']:
            Logger.warning("TMCConfigurator: Warning - unexpected response: {}".format(ll))

        elif self.motor_lut[ll[0]] != self.current_motor:
            Logger.error("TMCConfigurator: Error - unexpected axis {}".format(ll[0]))
            self.set_message("Error - unexpected axis in response {}".format(ll[0]))

        elif ll[1] == "1":
            self.switch_to_cot_tab(True)
            self.cotc_constant_off_time = int(ll[2])
            self.cotc_blank_time = int(ll[3])
            self.fast_decay_time = int(ll[4])
            self.sine_wave_offset = int(ll[5])
            self.use_current_comparator = True if ll[6] == '1' else False
            self.set_message("Loaded settings for motor {} in Constant Off Time Mode".format(self.current_motor))

        elif ll[1] == "0":
            self.switch_to_cot_tab(False)
            self.constant_off_time = int(ll[2])
            self.blank_time = int(ll[3])
            self.hysteresis_start = int(ll[4])
            self.hysteresis_end = int(ll[5])
            self.hysteresis_dec = int(ll[6])
            self.set_message("Loaded settings for motor {} in Spread Cycle Mode".format(self.current_motor))

        else:
            Logger.error("TMCConfigurator: Should not get here!!!!")

    def _get_chop_register(self, arg):
        self.waiting = True
        self.send_command("M911.1 P{}".format(self.current_motor))

    def get_chop_register(self):
        # retrieve the current setting for selected motor
        self.waiting = False
        App.get_running_app().comms.redirect_incoming(self._response)
        # wait for any outstanding queries
        Clock.schedule_once(self._get_chop_register, 0.5)
        self.set_message("Getting settings for motor {} ...".format(self.current_motor))
