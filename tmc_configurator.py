from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread
from kivy.properties import NumericProperty

'''
    M911.3 S1 [Unnn Vnnn Wnnn Xnnn Ynnn] - setSpreadCycleChopper
              U=constant_off_time, V=blank_time, W=hysteresis_start, X=hysteresis_end, Y=hysteresis_decrement
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

    def set_constant_off_time(self, v):
        self.constant_off_time = int(v)
        App.get_running_app().comms.write('M911.3 S1 U{}\n'.format(self.constant_off_time))

    def set_blank_time(self, v):
        self.blank_time = int(v)
        App.get_running_app().comms.write('M911.3 S1 V{}\n'.format(self.blank_time))

    def save_settings(self):
        # self.app.comms.write("config-set sd {} {}\n".format(k, v))
        pass

    def close(self):
        self.manager.current = 'main'
