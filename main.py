import kivy

from kivy.app import App
from kivy.lang import Builder

from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.uix.behaviors.button import ButtonBehavior

from kivy.properties import NumericProperty, StringProperty, ObjectProperty, ListProperty, BooleanProperty
from kivy.vector import Vector
from kivy.clock import Clock, mainthread
from kivy.factory import Factory
from kivy.logger import Logger
from kivy.core.window import Window

from comms import Comms
from message_box import MessageBox
from selection_box import SelectionBox
from file_dialog import FileDialog

import queue
import math
import os
import sys

Window.softinput_mode = 'below_target'

Builder.load_string('''
#:include jogrose.kv
#:include kbd.kv
#:include extruder.kv
# <Widget>:
#     # set default font size
#     font_size: dp(12)
<MainWindow>:
    orientation: 'vertical'
    ActionBar:
        pos_hint: {'top':1}
        ActionView:
            use_separator: True
            ActionPrevious:
                title: 'Smoothie Host'
                with_previous: False
            ActionOverflow:

            ActionToggleButton:
                id: connect_button
                text: 'Connect'
                on_press: root.connect()
            ActionButton:
                id: print_but
                disabled: not root.is_connected
                text: 'Print' # also 'Pause'/'Resume'
                on_press: root.start_print()
            ActionButton:
                disabled: not root.is_printing
                text: 'Abort'
                on_press: root.abort_print()

            ActionButton:
                text: 'Console'
                important: True
                group: 'winds'
                on_press: page_layout.page= 0
            ActionButton:
                text: 'Jog'
                important: True
                group: 'winds'
                on_press: page_layout.page= 1
            ActionButton:
                text: 'Extruder'
                important: True
                group: 'winds'
                on_press: page_layout.page= 2

            ActionGroup:
                text: 'System'
                mode: 'spinner'
                ActionButton:
                    text: 'Select Port'
                    disabled: root.is_connected
                    on_press: root.change_port()
                ActionButton:
                    text: 'Quit'
                    on_press: root.ask_exit()
                ActionButton:
                    text: 'Shutdown'
                    on_press: root.ask_shutdown()


    BoxLayout:
        orientation: 'horizontal'

        # Left panel
        BoxLayout:
            orientation: 'vertical'
            ScrollView:
                scroll_y: 0
                Label:
                    id: log_window
                    size_hint_y: None
                    height: self.texture_size[1]
                    text_size: self.width, None
            BoxLayout:
                orientation: 'horizontal'
                size_hint_y: None
                size: status.texture_size
                canvas.before:
                    Color:
                        rgba: 1,1,1,1
                    Rectangle:
                        pos: self.pos
                        size: self.size
                Label:
                    id: status
                    text: root.status
                    color: 0,0,0,1
                Label:
                    id: wcs
                    text: 'X: {} Y: {} Z: {}'.format(*root.wcs)
                    color: 0,0,0,1
                Label:
                    id: eta
                    text: 'ETA: {}'.format(root.eta)
                    color: 0,0,0,1

        # Right panel
        PageLayout:
            id: page_layout
            border: 30
            swipe_threshold: .25
            KbdWidget:
                id: kbd_widget

            JogRoseWidget:
                id: jog_rose
                disabled: root.is_printing

            ExtruderWidget:
                id: extruder
''')

class ExtruderWidget(BoxLayout):
    def __init__(self, **kwargs):
        super(ExtruderWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_bed_temp= self.app.config.getint('Extruder', 'last_bed_temp')
        self.last_hotend_temp= self.app.config.getint('Extruder', 'last_hotend_temp')

    def switch_active(self, instance, type, on, value):
        if on:
            if value == 'select':
                MessageBox(text='Select a temperature first!').open()
                instance.active= False
            else:
                self.set_temp(type, value)
                # save temp whenever we turn it on (not saved if it is changed while already on)
                if float(value) > 0:
                    self.set_last_temp(type, value)


        else:
            self.set_temp(type, '0')

    def adjust_temp(self, type, value):
        if type == 'bed':
            self.ids.set_bed_temp.text= '{}'.format(int(self.last_bed_temp) + int(value))
            if self.ids.bed_switch.active:
                # update temp
                self.set_temp(type, self.ids.set_bed_temp.text)
        else:
            self.ids.set_hotend_temp.text= '{}'.format(self.last_hotend_temp + int(value))
            if self.ids.hotend_switch.active:
                # update temp
                self.set_temp(type, self.ids.set_hotend_temp.text)

    def set_last_temp(self, type, value):
        if type == 'bed':
            self.last_bed_temp= int(value)
        else:
            self.last_hotend_temp= int(value)

        self.app.config.set('Extruder', 'last_{}_temp'.format(type), value)
        self.app.config.write()

    def set_temp(self, type, temp):
        ''' called when the target temp is changed '''
        if type == 'bed':
            self.app.comms.write('M140 S{0}\n'.format(str(temp)))
        elif type == 'hotend':
            self.app.comms.write('M104 S{0}\n'.format(str(temp)))

    def update_temp(self, type, temp, setpoint):
        ''' called to update the temperature display'''
        if type == 'bed':
            if temp:
                self.ids.bed_dg.value= temp
            if not math.isnan(setpoint):
                self.ids.set_bed_temp.text= str(setpoint)
                self.ids.bed_dg.setpoint_value= setpoint if setpoint > 0 else float('nan')

        elif type == 'hotend':
            if temp:
                self.ids.hotend_dg.value= temp
            if not math.isnan(setpoint):
                self.ids.set_hotend_temp.text= str(setpoint)
                self.ids.hotend_dg.setpoint_value= setpoint if setpoint > 0 else float('nan')

        else:
            Logger.error('Extruder: unknown temp type - ' + type)

    def extrude(self):
        ''' called when the extrude button is pressed '''
        Logger.debug('Extruder: extrude {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        self.app.comms.write('G91 G0 E{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

    def reverse(self):
        ''' called when the reverse button is pressed '''
        Logger.debug('Extruder: reverse {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        self.app.comms.write('G91 G0 E-{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

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
    def __init__(self, **kwargs):
        super(JogRoseWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def handle_action(self, axis, v):
        x10= self.x10_cb.active
        if x10:
            v *= 10
        if axis == 'O':
            self.app.comms.write('G0 X0 Y0\n')
        elif axis == 'H':
            self.app.comms.write('G28\n')
        else:
            self.app.comms.write('G91 G0 {}{} G90\n'.format(axis, v))

class KbdWidget(GridLayout):
    def __init__(self, **kwargs):
        super(KbdWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def _add_line_to_log(self, s):
        self.app.root.add_line_to_log(s)

    def do_action(self, key):
        if key == 'Send':
            #Logger.debug("KbdWidget: Sending {}".format(self.display.text))
            self._add_line_to_log('<< {}'.format(self.display.text))
            self.app.comms.write('{}\n'.format(self.display.text))
            self.display.text = ''
        elif key == 'BS':
            self.display.text = self.display.text[:-1]
        else:
            self.display.text += key

    def handle_input(self, s):
        self._add_line_to_log('<< {}'.format(s))
        self.app.comms.write('{}\n'.format(s))
        self.display.text = ''

class MainWindow(BoxLayout):
    status= StringProperty('Idle')
    wcs= ListProperty([0,0,0])
    eta= StringProperty('--:--')
    is_printing= BooleanProperty(False)
    is_connected= BooleanProperty(False)

    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self._trigger = Clock.create_trigger(self.async_get_display_data)
        self._q= queue.Queue()
        self._log= []
        self.config= self.app.config
        self.last_path= self.config.get('General', 'last_gcode_path')
        self.paused= False

        #print('font size: {}'.format(self.ids.log_window.font_size))
        Clock.schedule_once(self.my_callback, 2) # hack to overcome the page layout not laying out initially

    def my_callback(self, dt):
        self.ids.page_layout.page= 1 # switch to jog screen

    def add_line_to_log(self, s):
        ''' Add lines to the log window, which is trimmed to the last 200 lines '''
        max_lines= 200 # TODO needs to be configurable
        self._log.append(s)
        # we use some hysterysis here so we don't truncate every line added over max_lines
        n= len(self._log) - max_lines # how many lines over our max
        if n > 10:
            # truncate log to last max_lines, we delete the oldest 10 or so lines
            del self._log[0:n]

        self.ids.log_window.text= '\n'.join(self._log)

    def connect(self):
        if self.is_connected:
            self.add_line_to_log("Disconnecting...")
            self.app.comms.disconnect()
        else:
            port= self.config.get('General', 'serial_port') if not self.app.use_com_port else self.app.use_com_port
            self.add_line_to_log("Connecting to {}...".format(port))
            self.app.comms.connect(port)

    def display(self, data):
        self.add_line_to_log(data)

    # we have to do this as @mainthread was getting stuff out of order
    def async_display(self, data):
        ''' called from external thread to display incoming data '''
        # puts the data onto queue and triggers an event to read it in the Kivy thread
        self._q.put(data)
        self._trigger()

    def async_get_display_data(self, *largs):
        ''' fetches data from the Queue and displays it, triggered by incoming data '''
        while not self._q.empty():
            # we need this loop until q is empty as trigger only triggers once per frame
            data= self._q.get(False)
            self.display(data)

    @mainthread
    def connected(self):
        Logger.debug("MainWindow: Connected...")
        self.is_connected= True
        self.ids.connect_button.state= 'down'
        self.ids.connect_button.text= "Disconnect"
        self.ids.print_but.text= 'Print'
        self.paused= False
        self.is_printing= False

    @mainthread
    def disconnected(self):
        Logger.debug("MainWindow: Disconnected...")
        self.is_connected= False
        self.is_printing= False
        self.ids.connect_button.state= 'normal'
        self.ids.connect_button.text= "Connect"

    @mainthread
    def update_temps(self, he, hesp, be, besp):
        if he:
            self.ids.extruder.update_temp('hotend', he, hesp)
        if be:
            self.ids.extruder.update_temp('bed', be, besp)

    @mainthread
    def update_status(self, stat, mpos, wpos):
        self.status= stat
        self.wcs= wpos

    @mainthread
    def stream_finished(self, ok):
        ''' called when streaming gcode has finished, ok is True if it completed '''
        self.ids.print_but.text= 'Print'
        self.is_printing= False
        self.display('>>> printing finished {}'.format('ok' if ok else 'abnormally'))


    @mainthread
    def alarm_state(self, s):
        ''' called when smoothie is in Alarm state and it is sent a gcode '''
        if not '!!' in s:
            self.add_line_to_log("! Alarm state: {}".format(s))

    def ask_exit(self):
        # are you sure?
        mb = MessageBox(text='Exit - Are you Sure?', cb= lambda b: self._do_exit(b))
        mb.open()

    def _do_exit(self, ok):
        if ok:
            self.app.comms.stop()
            exit()

    def ask_shutdown(self):
        # are you sure?
        mb = MessageBox(text='Shutdown - Are you Sure?', cb= lambda b: self._do_shutdown(b))
        mb.open()

    def _do_shutdown(self, ok):
        if ok:
            #sys.system('sudo halt -p')
            self.do_exit(True)

    def change_port(self):
        l= self.app.comms.get_ports()
        ports= []
        for p in l:
            ports.append(p.device)

        sb = SelectionBox(text='Select port to open', values= ports, cb= lambda b: self._change_port(b))
        sb.open()

    def _change_port(self, s):
        if s:
            Logger.info('MainWindow: Selected port {}'.format(s))
            self.config.set('General', 'serial_port', s)

    def abort_print(self):
        # are you sure?
        mb = MessageBox(text='Abort - Are you Sure?', cb= lambda b: self._abort_print(b))
        mb.open()

    def _abort_print(self, ok):
        if ok:
            self.app.comms.stream_pause(False, True)

    def start_print(self):
        if self.is_printing:
            if not self.paused:
                self.paused= True
                self.app.comms.stream_pause(True)
                self.ids.print_but.text= 'Resume'
            else:
                self.paused= False
                self.app.comms.stream_pause(False)
                self.ids.print_but.text= 'Pause'
        else:
            # get file to print
            f= FileDialog(self._start_print)
            f.open(self.last_path)

    def _start_print(self, file_path, directory):
        # start comms thread to stream the file
        # set comms.ping_pong to False for fast stream mode
        Logger.info('MainWindow: printing file: {}'.format(file_path))
        self.display('>>> started printing file: {}'.format(file_path))

        self.app.comms.stream_gcode(file_path)
        if directory != self.last_path:
            self.last_path= directory
            self.config.set('General', 'last_gcode_path', directory)

        self.config.set('General', 'last_print_file', file_path)
        self.config.write()

        self.ids.print_but.text= 'Pause'
        self.is_printing= True
        self.paused= False

class SmoothieHost(App):
    #Factory.register('Comms', cls=Comms)
    def __init__(self, **kwargs):
        super(SmoothieHost, self).__init__(**kwargs)
        self.comms= Comms(self)
        if len(sys.argv) > 1:
            # override com port
            self.use_com_port= sys.argv[1]
        else:
            self.use_com_port= None

    def build_config(self, config):
        config.setdefaults('General', {
            'last_gcode_path': os.path.expanduser("~"),
            'last_print_file': '',
            'serial_port': '/dev/ttyACM0'
        })
        config.setdefaults('Extruder', {
            'last_bed_temp': '',
            'last_hotend_temp': ''
        })

    def on_stop(self):
        # The Kivy event loop is about to stop, stop the async main loop
        self.comms.stop(); # stop the aysnc loop

    def build(self):
        return MainWindow()


SmoothieHost().run()



