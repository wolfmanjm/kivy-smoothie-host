from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread, Clock
from kivy.properties import NumericProperty, BooleanProperty
from kivy.logger import Logger

'''
    M911.3 S1 [Unnn Vnnn Wnnn Xnnn Ynnn] - setSpreadCycleChopper
              U=constant_off_time, V=blank_time, W=hysteresis_start, X=hysteresis_end, Y=hysteresis_decrement
                2...15               0..54         1...8               -3..12            0..3

 * constant_off_time: The off time setting controls the minimum chopper frequency.
 * For most applications an off time within the range of 5μs to 20μs will fit.
 *      2...15: off time setting
 *
 * blank_time: Selects the comparator blank time. This time needs to safely cover the switching event and the
 * duration of the ringing on the sense resistor. For
 *      0: min. setting 3: max. setting
 *
 * fast_decay_time_setting: Fast decay time setting. With CHM=1, these bits control the portion of fast decay for each chopper cycle.
 *      0: slow decay only
 *      1...15: duration of fast decay phase
 *
 * sine_wave_offset: Sine wave offset. With CHM=1, these bits control the sine wave offset.
 * A positive offset corrects for zero crossing error.
 *      -3..-1: negative offset 0: no offset 1...12: positive offset
 *
 * use_current_comparator: Selects usage of the current comparator for termination of the fast decay cycle.
 * If current comparator is enabled, it terminates the fast decay cycle in case the current
 * reaches a higher negative value than the actual positive value.
 *      1: enable comparator termination of fast decay cycle
 *      0: end by time only

 void TMC26X::setConstantOffTimeChopper(int8_t constant_off_time, int8_t blank_time, int8_t fast_decay_time_setting, int8_t sine_wave_offset, uint8_t use_current_comparator)

 setConstantOffTimeChopper(GET('U'), GET('V'), GET('W'), GET('X'), GET('Y'));
 setConstantOffTimeChopper(7, 54, 13, 12, 1);

    TODO
        maybe allow setting of ConstantOffTimeChopper
'''


Builder.load_string('''
<TMCConfigurator>:
    on_enter: self.start()
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
    default_settings = [5, 54, 5, 0, 0]
    constant_off_time = NumericProperty(default_settings[0])
    blank_time = NumericProperty(default_settings[1])
    hysteresis_start = NumericProperty(default_settings[2])
    hysteresis_end = NumericProperty(default_settings[3])
    hysteresis_dec = NumericProperty(default_settings[4])

    pfd = BooleanProperty(True)
    rot = BooleanProperty(False)

    move_timer = None
    direction = False

    enabled_list = {'X': True, 'Y': False, 'Z': False, 'A': False}
    motor_lut = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}
    current_motor = 0

    def start(self):
        # get current settings for selected motor
        self.get_chop_register()

    def set_enabled(self, axis, flg):
        # print("enabled: {} {}".format(axis, flg))
        self.enabled_list[axis] = flg
        if flg:
            self.current_motor = self.motor_lut[axis]
            self.start()

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

    def set_pfd(self, v):
        self.pfd = v
        self.send_M911_command('S6 Z{}'.format("1" if self.pfd else "0"))

    def set_rot(self, v):
        self.rot = v
        self.send_M911_command('S2 Z{}'.format("1" if self.rot else "0"))

    def _move_motors(self, arg):
        d = '-10' if self.direction else '10'
        self.direction = not self.direction

        for a in self.enabled_list:
            if self.enabled_list[a]:
                self.send_command("M120 G91 G0 {}{} F100 M121".format(a, d))

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

    def reset_settings(self):
        self.set_constant_off_time(self.default_settings[0])
        self.set_blank_time(self.default_settings[1])
        self.set_hysteresis_start(self.default_settings[2])
        self.set_hysteresis_end(self.default_settings[3])
        self.set_hysteresis_dec(self.default_settings[4])
        self.set_pfd(True)
        self.set_rot(False)

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

    def set_message(self, v):
        self.ids.messages.text = v

    def _response(self, line):
        ll = line.lstrip().rstrip()
        if ll == "ok":
            App.get_running_app().comms.redirect_incoming(None)
            return

        ll = ll.split(',')

        if len(ll) < 7:
            Logger.error("TMCConfigurator: Error - unexpected response size {}".format(len(ll)))
            self.set_message("Error - unexpected response size {}".format(len(ll)))

        elif self.motor_lut[ll[0]] != self.current_motor:
            Logger.error("TMCConfigurator: Error - unexpected axis {}".format(ll[0]))
            self.set_message("Error - unexpected axis in response {}".format(ll[0]))

        elif ll[1] != "0":
            Logger.error("TMCConfigurator: Error - Not in spreadcycle mode")
            self.set_message("Error - Not in spreadcycle mode")

        else:
            # unpack the results
            self.constant_off_time = int(ll[2])
            self.blank_time = int(ll[3])
            self.hysteresis_start = int(ll[4])
            self.hysteresis_end = int(ll[5])
            self.hysteresis_dec = int(ll[6])
            self.set_message("Loaded settings for motor {}".format(self.current_motor))

    def _get_chop_register(self, arg):
        self.send_command("M911.1 P{}".format(self.current_motor))

    def get_chop_register(self):
        # retrieve the current setting for selected motor
        App.get_running_app().comms.redirect_incoming(self._response)
        # wait for any outstanding queries
        Clock.schedule_once(self._get_chop_register, 1)
        self.set_message("Getting settings for motor {} ...".format(self.current_motor))
