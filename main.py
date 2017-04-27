import kivy

from kivy.app import App

from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, ObjectProperty
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors.button import ButtonBehavior
from kivy.vector import Vector
from kivy.clock import Clock, mainthread
#from kivy.garden.gauge import Gauge
from kivy.factory import Factory
from kivy.logger import Logger
from kivy.core.window import Window
from comms import Comms


comms= None
Window.softinput_mode = 'pan'

Builder.load_string('''
#:include jogrose.kv
#:include kbd.kv
#:include extruder.kv

<MainWindow>:
    orientation: 'horizontal'

    # Left panel
    BoxLayout:
        orientation: 'vertical'
        padding: 5, 5
        ScrollView:
            Label:
                id: log_window
                size_hint_y: None
                height: self.texture_size[1]
                text_size: self.width, None
        BoxLayout:
            orientation: 'horizontal'
            Button:
                id: connect_button
                size_hint_y: None
                size: 20, 40
                text: 'Connect'
                on_press: root.connect()
            Button:
                size_hint_y: None
                size: 20, 40
                text: 'Quit'
                on_press: exit()

    # Right panel
    PageLayout:
        id: page_layout
        size_hint: 1.0, 1.0
        border: 30
        KbdWidget:
            id: kbd_widget

        JogRoseWidget:
            id: jog_rose

        ExtruderWidget:
            id: extruder

        Button:
            text: 'macro page place holder'
            background_color: 0,1,0,1

        Button:
            text: 'play file page place holder'
            background_color: 0,1,1,1

        Button:
            text: 'DRO place holder'
            background_color: 1,1,0,1

''')

class ExtruderWidget(BoxLayout):
    def set_temp(self, type, temp):
        ''' called when the target temp is changed '''
        Logger.info('Extruder: ' + type + ' temp set to: ' + temp)
        if type == 'bed':
            comms.write('M140 S{0}\n'.format(str(temp)))
        elif type == 'hotend':
            comms.write('M104 S{0}\n'.format(str(temp)))

    def update_temp(self, type, temp):
        ''' called to update the temperature display'''
        if type == 'bed':
            self.ids.bed_dg.value= 60
            #self.ids.bed_temp.text = str(temp)
        elif type == 'hotend':
            self.ids.hotend_dg.value= 185
            #self.ids.hotend_temp.text = str(temp)
        else:
            Logger.error('Extruder: unknown temp type - ' + type)

    def extrude(self):
        ''' called when the extrude button is pressed '''
        Logger.info('Extruder: extrude {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        comms.write('G91 G0 E{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

    def reverse(self):
        ''' called when the reverse button is pressed '''
        Logger.info('Extruder: reverse {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        comms.write('G91 G0 E-{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

class CircularButton(ButtonBehavior, Widget):
    text= StringProperty()
    def collide_point(self, x, y):
        return Vector(x, y).distance(self.center) <= self.width / 2

class ArrowButton(ButtonBehavior, Widget):
    text= StringProperty()
    angle= NumericProperty()
    # def collide_point(self, x, y):
    #     bmin= Vector(self.center) - Vector(25, 25)
    #     bmax= Vector(self.center) + Vector(25, 25)
    #     return Vector.in_bbox((x, y), bmin, bmax)

class JogRoseWidget(BoxLayout):
    def handle_action(self, axis, v):
        x10= self.x10_cb.active
        if x10:
            v *= 10
        if axis == 'O':
            Logger.debug("JogRoseWidget: G0 X0 Y0")
            comms.write('G0 X0 Y0\n')
        elif axis == 'H':
            Logger.debug("JogRoseWidget: G28")
            comms.write('G28\n')
        else:
            Logger.debug("JogRoseWidget: Jog " + axis + ' ' + str(v))
            comms.write(axis + ' ' + str(v) + '\n')

class KbdWidget(GridLayout):

    def _add_to_log(self, s):
        app= App.get_running_app()
        app.root.add_to_log(s)

    def do_action(self, key):
        Logger.debug("KbdWidget: Key " + key)
        if key == 'Send':
            Logger.debug("KbdWidget: Sending " + self.display.text)
            self._add_to_log('<< ' + self.display.text + '\n')
            comms.write(self.display.text + '\n')
            self.display.text = ''
        elif key == 'BS':
            self.display.text = self.display.text[:-1]
        else:
            self.display.text += key

    def handle_input(self, s):
        self._add_to_log('<< ' + s + '\n')
        comms.write(s + '\n')
        self.display.text = ''

class MainWindow(BoxLayout):
    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)
        self.is_connected= False
        #     Clock.schedule_once(self.my_callback, 5)

    # def my_callback(self, dt):
    #     Logger.debug("switch page")
    #     self.ids.page_layout.page= 2

    def add_to_log(self, s):
        ''' Add lines to the log window, which is trimmed to the last 200 lines '''
        max_lines= 200
        self.ids.log_window.text += s
        n= self.ids.log_window.text.count('\n')
        # we use some hysterysis here so we don't truncate every line added over max_lines
        if n > max_lines+10: # TODO needs to be configurable
            # truncate string to last max_lines
            l= self.ids.log_window.text.splitlines(keepends=True)
            self.ids.log_window.text = ''.join(l[-max_lines:])

    def connect(self):
        if self.is_connected:
            Logger.debug("MainWindow: Disconnecting...")
            self.add_to_log("Disconnecting...\n")
            comms.disconnect()
        else:
            Logger.debug("MainWindow: Connecting...")
            self.add_to_log("Connecting...\n")
            comms.connect('/dev/ttyACM1')

    @mainthread
    def display(self, data):
        self.add_to_log(data)

    @mainthread
    def connected(self):
        Logger.debug("MainWindow: Connected...")
        self.is_connected= True
        self.ids.connect_button.text= "Disconnect"

    @mainthread
    def disconnected(self):
        Logger.debug("MainWindow: Disconnected...")
        self.is_connected= False
        self.ids.connect_button.text= "Connect"

    def error_message(self, str):
        self.display('! ' + str + '\n')

class SmoothieHost(App):
    #Factory.register('Comms', cls=Comms)
    def on_stop(self):
        # The Kivy event loop is about to stop, stop the async main loop
        comms.stop(); # stop the aysnc loop

    def build(self):
        global comms
        comms= Comms(self)
        return MainWindow()

if __name__ == "__main__":
    SmoothieHost().run()



