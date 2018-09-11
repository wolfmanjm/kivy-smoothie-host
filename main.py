import kivy

from kivy.app import App
from kivy.lang import Builder

from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.uix.behaviors.button import ButtonBehavior
from kivy.uix.tabbedpanel import TabbedPanel

from kivy.properties import NumericProperty, StringProperty, ObjectProperty, ListProperty, BooleanProperty
from kivy.vector import Vector
from kivy.clock import Clock, mainthread
from kivy.factory import Factory
from kivy.logger import Logger
from kivy.core.window import Window
from kivy.config import ConfigParser

from mpg_knob import Knob

from comms import Comms
from message_box import MessageBox
from input_box import InputBox
from selection_box import SelectionBox
from file_dialog import FileDialog
from viewer import GcodeViewerScreen
from web_server import ProgressServer
from camera_screen import CameraScreen

import subprocess
import traceback
import queue
import math
import os
import sys
import datetime
import configparser
from functools import partial

Window.softinput_mode = 'below_target'

class NumericInput(TextInput):
    """Text input that shows a numeric keypad"""
    def __init__(self, **kwargs):
        super(NumericInput, self).__init__(**kwargs)

    def on_focus(self, i, v):
        if v:
            self._last= self.text
            self.text= ""
            self.show_keyboard()
            if self.keyboard.widget:
                self.keyboard.widget.layout= "numeric.json"
                self.m_keyboard= self.keyboard.widget
        else:
            if self.text == "": self.text= self._last
            self.hide_keyboard()
            self.m_keyboard.layout= "qwerty"


    def on_parent(self, widget, parent):
        self.keyboard_mode= 'managed'

class DROWidget(RelativeLayout):
    """DROWidget Shows realtime information in a DRO style"""
    curwcs= StringProperty('')
    def __init__(self, **kwargs):
        super(DROWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def enter_wpos(self, axis, v):
        i= ord(axis) - ord('x')
        try:
            # needed becuase the filter does not allow -ive numbers WTF!!!
            f= float(v.strip())
        except:
            Logger.warning("DROWidget: invalid float input: {}".format(v))
            # set the display back to what it was, this looks odd but it forces the display to update
            self.app.wpos[i] = self.app.wpos[i]
            return

        Logger.debug("DROWidget: Set axis {} wpos to {}".format(axis, f))
        self.app.comms.write('G10 L20 P0 {}{}\n'.format(axis.upper(), f))
        self.app.wpos[i] = f

    def select_wcs(self, v):
        self.app.comms.write('{}\n'.format(v))

    def reset_axis(self, a):
        self.app.comms.write('G92 {}0\n'.format(a))

    def update_buttons(self):
        self.app.comms.write("$G\n")

    def _on_curwcs(self):
        # foreach WCS button see if it is active or not
        for i in self.ids.wcs_buts.children:
            if i.text == self.curwcs:
                i.state= 'down'
            else:
                i.state= 'normal'


# user defined macros are configurable and stored in a configuration file called macros.ini
# format is:-
# button name = command to send
class MacrosWidget(StackLayout):
    """adds macro buttons"""
    def __init__(self, **kwargs):
        super(MacrosWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        # we do this so the kv defined buttons are loaded first
        Clock.schedule_once(self._load_user_buttons)
        self.toggle_buttons= {}

    def _handle_toggle(self, name, v):
        t= self.toggle_buttons.get(name, None)
        if t is None:
            Logger.error("MacrosWidget: no toggle button named: {}".format(name))
            return

        if t[4].state == 'normal':
            t[4].text= t[0]
            self.send(t[3]) # NOTE the button already toggled so the states are reversed
        else:
            t[4].text= t[1]
            self.send(t[2])

    def _load_user_buttons(self, *args):
        # load user defined macros
        try:
            config = configparser.ConfigParser()
            config.read('macros.ini')

            # add toggle button handling switch states
            for section in config.sections():
                if not section.startswith('toggle button'): continue
                name= config.get(section, 'name', fallback=None)
                lon= config.get(section, 'label on', fallback=None)
                loff= config.get(section, 'label off', fallback=None)
                cmd_on= config.get(section, 'command on', fallback=None)
                cmd_off= config.get(section, 'command off', fallback=None)
                if name is None or lon is None or loff is None or cmd_on is None or cmd_off is None:
                    Logger.error("MacrosWidget: config error - {} is invalid".format(section))
                    continue

                tbtn = Factory.MacroToggleButton()
                tbtn.text= lon
                self.toggle_buttons[name]= (lon, loff, cmd_on, cmd_off, tbtn)
                tbtn.bind(on_press= partial(self._handle_toggle, name))
                self.add_widget(tbtn)

            # add simple macro buttons
            for (key, v) in config.items('macro buttons'):
                btn = Factory.MacroButton()
                btn.text= key
                btn.bind(on_press= partial(self.send, v))
                self.add_widget(btn)
        except:
            Logger.warning('MacrosWidget: ERROR - exception parsing config file: {}'.format(traceback.format_exc()))

    def update_buttons(self):
        # check the state of the toggle macro buttons, called when we switch to the macro window
        for t in self.toggle_buttons:
            # sends this, the response will be caught by comms as switch xxx is yyy
            self.send("switch {}".format(t))

    @mainthread
    def switch_response(self, name, value):
        # check response and compare state with current state and toggle to match state if necessary
        t= self.toggle_buttons.get(name, None)
        if t is None:
            Logger.error("MacrosWidget: switch_response no toggle button named: {}".format(name))
            return

        if value == '0' and t[4].state != 'normal':
            t[4].state = 'normal'
            t[4].text = t[0]
        elif value == '1' and t[4].state == 'normal':
            t[4].state = 'down'
            t[4].text = t[1]

    def send(self, cmd, *args):
        self.app.comms.write('{}\n'.format(cmd))

class ExtruderWidget(BoxLayout):
    bed_dg= ObjectProperty()
    hotend_dg= ObjectProperty()
    last_bed_temp= NumericProperty()
    last_hotend_temp= NumericProperty()
    curtool= NumericProperty(-1)

    def __init__(self, **kwargs):
        super(ExtruderWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_bed_temp= self.app.config.getfloat('Extruder', 'last_bed_temp')
        self.last_hotend_temp= self.app.config.getfloat('Extruder', 'last_hotend_temp')
        self.temp_changed= False
        #self.bind(on_curtool=self._on_curtool)

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
        if value == 'select temp':
            return

        if type == 'bed':
            self.ids.set_bed_temp.text= '{:1.1f}'.format(self.last_bed_temp + float(value))
            if self.ids.bed_switch.active:
                # update temp
                self.set_temp(type, self.ids.set_bed_temp.text)
                self.temp_changed= True
        else:
            self.ids.set_hotend_temp.text= '{:1.1f}'.format(self.last_hotend_temp + float(value))
            if self.ids.hotend_switch.active:
                # update temp
                self.set_temp(type, self.ids.set_hotend_temp.text)
                self.temp_changed= True

    def set_last_temp(self, type, value):
        if type == 'bed':
            self.last_bed_temp= float(value)
        else:
            self.last_hotend_temp= float(value)

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
                self.bed_dg.value= temp
            if not math.isnan(setpoint) and not self.temp_changed:
                if setpoint > 0:
                    self.ids.set_bed_temp.text= str(setpoint)
                    self.bed_dg.setpoint_value= setpoint
                else:
                    self.bed_dg.setpoint_value= float('nan')
                    if self.bed_switch.active:
                        self.bed_switch.active= False

        elif type == 'hotend0' or type == 'hotend1':
            if (self.ids.tool_t0.state == 'down' and type == 'hotend0') or (self.ids.tool_t1.state == 'down' and type == 'hotend1'):
                if temp:
                    self.hotend_dg.value= temp
                if not math.isnan(setpoint) and not self.temp_changed:
                    if setpoint > 0:
                        self.ids.set_hotend_temp.text= str(setpoint)
                        self.hotend_dg.setpoint_value= setpoint
                    else:
                        self.hotend_dg.setpoint_value= float('nan')
                        if self.hotend_switch.active:
                            self.hotend_switch.active= False

        else:
            Logger.error('Extruder: unknown temp type - ' + type)

        self.temp_changed= False

    def set_tool(self, t):
        self.app.comms.write('T{}\n'.format(str(t)))

    def update_length(self):
        self.app.config.set('Extruder', 'length', self.ids.extrude_length.text)
        self.app.config.write()

    def update_speed(self):
        self.app.config.set('Extruder', 'speed', self.ids.extrude_speed.text)
        self.app.config.write()

    def extrude(self):
        ''' called when the extrude button is pressed '''
        Logger.debug('Extruder: extrude {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        self.app.comms.write('G91 G0 E{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

    def reverse(self):
        ''' called when the reverse button is pressed '''
        Logger.debug('Extruder: reverse {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        self.app.comms.write('G91 G0 E-{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

    def update_buttons(self):
        self.app.comms.write("$G\n")

    def _on_curtool(self):
        self.ids.tool_t0.state= 'down' if self.curtool == 0 else 'normal'
        self.ids.tool_t1.state= 'down' if self.curtool == 1 else 'normal'

class MPGWidget(RelativeLayout):
    """docstring for MPGWidget"""
    last_pos= NumericProperty(0)
    selected_axis= StringProperty('X')

    def __init__(self, **kwargs):
        super(MPGWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def handle_action(self):
        # if in non MPG mode then issue G0 in abs or rel depending on settings
        # if in MPG mode then issue step commands when they occur
        if not self.ids.mpg_mode_tb.state == 'down':
            # normal mode
            cmd1= 'G91 G0' if self.ids.abs_mode_tb.state == 'down' else 'G0'
            cmd2= 'G90' if self.ids.abs_mode_tb.state == 'down' else ''
            #print('{} {}{} {}'.format(cmd1, self.selected_axis, round(self.last_pos, 3), cmd2))
            self.app.comms.write('{} {}{} {}\n'.format(cmd1, self.selected_axis, round(self.last_pos, 3), cmd2))

    def handle_change(self, ticks):
        pos= self.last_pos + (ticks/100.0 if self.ids.fine_cb.active else ticks/10.0)
        axis= self.selected_axis
        #print('axis: {}, pos: {}'.format(axis, pos))
        #self.ids.pos_lab.text= '{:08.3f}'.format(pos)
        self.last_pos= pos
        # TODO disable if delta or corexy
        #MPG mode
        if self.ids.mpg_mode_tb.state == 'down':
            if self.ids.fine_cb.active:
                d= 1 if ticks < 0 else -1
            else:
                d= 16 if ticks < 0 else -16
            sps= abs(ticks) * 1600 # number of ticks moved changes steps/sec
            self.app.comms.write('test raw {} {} {}\n'.format(self.selected_axis.lower(), d, sps))

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
    xy_feedrate= StringProperty()
    abc_sel= StringProperty('Z')

    def __init__(self, **kwargs):
        super(JogRoseWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.xy_feedrate= self.app.config.get('Jog', 'xy_feedrate')

    def handle_action(self, axis, v):
        x10= self.ids.x10cb.active
        if x10:
            v *= 10
        if axis == 'O':
            self.app.comms.write('M120 G0 X0 Y0 F{} M121\n'.format(self.xy_feedrate))
        elif axis == 'H':
            if self.app.is_cnc:
                self.app.comms.write('$H\n')
            else:
                self.app.comms.write('G28\n')
        else:
            fr= self.xy_feedrate
            self.app.comms.write('M120 G91 G0 {}{} F{} M121\n'.format(axis, v, fr))

    def update_xy_feedrate(self):
        fr= self.ids.xy_feedrate.text
        self.app.config.set('Jog', 'xy_feedrate', fr)
        self.app.config.write()
        self.xy_feedrate= fr

    def motors_off(self):
        self.app.comms.write('M18\n')


class KbdWidget(GridLayout):
    def __init__(self, **kwargs):
        super(KbdWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_command= ""

    def _add_line_to_log(self, s):
        self.app.main_window.async_display(s)

    def do_action(self, key):
        if key == 'Send':
            #Logger.debug("KbdWidget: Sending {}".format(self.display.text))
            self._add_line_to_log('<< {}'.format(self.display.text))
            self.app.comms.write('{}\n'.format(self.display.text))
            self.last_command = self.display.text
            self.display.text = ''
        elif key == 'Repeat':
            self.display.text = self.last_command
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
    wpos= ListProperty([0,0,0])
    eta= StringProperty('--:--:--')
    is_printing= BooleanProperty(False)
    is_suspended= BooleanProperty(False)

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
        #Clock.schedule_once(self.my_callback, 2) # hack to overcome the page layout not laying out initially

    # def my_callback(self, dt):
    #     self.ids.carousel.index= 1 # switch to jog screen

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
        if self.app.is_connected:
            if self.is_printing:
                mb = MessageBox(text='Cannot Disconnect while printing - Abort first, then wait')
                mb.open()
            else:
                self._disconnect()

        else:
            port= self.config.get('General', 'serial_port') if not self.app.use_com_port else self.app.use_com_port
            self.add_line_to_log("Connecting to {}...".format(port))
            self.app.comms.connect(port)

    def _disconnect(self, b= True):
        if b:
            self.add_line_to_log("Disconnect...")
            self.app.comms.disconnect()

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
        self.add_line_to_log("...Connected")
        self.app.is_connected= True
        self.ids.connect_button.state= 'down'
        self.ids.connect_button.text= "Disconnect"
        self.ids.print_but.text= 'Print'
        self.paused= False
        self.is_printing= False

    @mainthread
    def disconnected(self):
        Logger.debug("MainWindow: Disconnected...")
        self.app.is_connected= False
        self.is_printing= False
        self.ids.connect_button.state= 'normal'
        self.ids.connect_button.text= "Connect"
        self.add_line_to_log("...Disconnected")

    @mainthread
    def update_status(self, stat, d):
        self.status= stat
        self.app.status= stat
        if 'WPos' in d:
            self.wpos= d['WPos']
            self.app.wpos= self.wpos

        if 'MPos' in d:
            self.app.mpos= d['MPos']

        if 'F' in d:
            self.app.fr= d['F'][0]

        if 'S' in d:
            self.app.sr= d['S'][0]

        if 'L' in d:
            self.app.lp= d['L'][0]

        if not self.app.is_cnc:
            # extract temperature readings
            if 'T' in d:
                self.ids.extruder.update_temp('hotend0', d['T'][0], d['T'][1])
            elif 'T1' in d:
                self.ids.extruder.update_temp('hotend1', d['T1'][0], d['T1'][1])

            if 'B' in d:
                self.ids.extruder.update_temp('bed', d['B'][0], d['B'][1])

    @mainthread
    def update_state(self, a):
        if not self.app.is_cnc:
            self.ids.extruder.curtool= int(a[9][1])
        self.ids.dro_widget.curwcs= a[1]

    @mainthread
    def alarm_state(self, s):
        ''' called when smoothie is in Alarm state and it is sent a gcode '''
        self.add_line_to_log("! Alarm state: {}".format(s))

        # if we were printing then we need to set the UI state to Paused
        if self.is_printing:
            self.action_paused(True) # sets the buttons state
            self.add_line_to_log("Streaming Paused, Abort or Continue as needed")

    def ask_exit(self):
        # are you sure?
        mb = MessageBox(text='Exit - Are you Sure?', cb= self._do_exit)
        mb.open()

    def _do_exit(self, ok):
        if ok:
            self.app.stop()

    def ask_shutdown(self):
        # are you sure?
        mb = MessageBox(text='Shutdown - Are you Sure?', cb=self._do_shutdown)
        mb.open()

    def _do_shutdown(self, ok):
        if ok:
            os.system('/sbin/shutdown -h now')
            self._do_exit(True)

    def change_port(self):
        l= self.app.comms.get_ports()
        ports= [self.config.get('General', 'serial_port')] # current port is first in list
        for p in l:
            ports.append('serial://{}'.format(p.device))

        ports.append('network...')

        sb = SelectionBox(text='Select port to open', values= ports, cb= self._change_port)
        sb.open()

    def _change_port(self, s):
        if s:
            Logger.info('MainWindow: Selected port {}'.format(s))

            if s.startswith('network'):
                mb = InputBox(text='Enter network address as "ipaddress[:port]"', cb=self._new_network_port)
                mb.open()

            else:
                self.config.set('General', 'serial_port', s)
                self.config.write()

    def _new_network_port(self, s):
        if s:
            self.config.set('General', 'serial_port', 'net://{}'.format(s))
            self.config.write()

    def abort_print(self):
        # are you sure?
        mb = MessageBox(text='Abort - Are you Sure?', cb= self._abort_print)
        mb.open()

    def _abort_print(self, ok):
        if ok:
            self.app.comms.stream_pause(False, True)

    @mainthread
    def action_paused(self, paused):
        # comms layer is telling us we paused or unpaused
        self.ids.print_but.text= 'Resume' if paused else 'Pause'
        self.paused= paused

    def start_print(self):
        if self.is_printing:
            if not self.paused:
                # we clicked the pause button
                self.app.comms.stream_pause(True)
            else:
                # we clicked the resume button
                if self.is_suspended:
                    # as we were suspended we need to resume the suspend first
                    # we let Smoothie tell us to resume from pause though
                    self.app.comms.write('M601\n')
                    self.is_suspended= False
                else:
                    self.app.comms.stream_pause(False)
        else:
            # get file to print
            f= FileDialog()
            f.open(self.last_path, cb= self._start_print)

    def _start_print(self, file_path, directory):
        # start comms thread to stream the file
        # set comms.ping_pong to False for fast stream mode
        Logger.info('MainWindow: printing file: {}'.format(file_path))

        try:
            self.nlines= Comms.file_len(file_path) # get number of lines so we can do progress and ETA
            Logger.debug('MainWindow: number of lines: {}'.format(self.nlines))
        except:
            Logger.warning('MainWindow: exception in file_len: {}'.format(traceback.format_exc()))
            self.nlines= None

        self.start_print_time= datetime.datetime.now()
        self.display('>>> Printing file: {}, {} lines'.format(file_path, self.nlines))

        if self.app.comms.stream_gcode(file_path, progress= lambda x: self.display_progress(x)):
            self.display('>>> Print started at: {}'.format(self.start_print_time.strftime('%x %X')))
        else:
            self.display('WARNING Unable to start print')
            return

        if directory != self.last_path:
            self.last_path= directory
            self.config.set('General', 'last_gcode_path', directory)

        self.app.gcode_file= file_path
        self.config.set('General', 'last_print_file', file_path)
        self.config.write()

        self.ids.print_but.text= 'Pause'
        self.is_printing= True
        self.paused= False

    def reprint(self):
        # are you sure?
        mb = MessageBox(text='Reprint {}?'.format(self.app.gcode_file), cb= self._reprint)
        mb.open()

    def _reprint(self, ok):
        if ok:
            self._start_print(self.app.gcode_file, self.last_path)

    @mainthread
    def stream_finished(self, ok):
        ''' called when streaming gcode has finished, ok is True if it completed '''
        self.ids.print_but.text= 'Print'
        self.is_printing= False
        now= datetime.datetime.now()
        self.display('>>> printing finished {}'.format('ok' if ok else 'abnormally'))
        self.display(">>> Print ended at : {}".format(now.strftime('%x %X')))
        et= datetime.timedelta(seconds= int((now-self.start_print_time).seconds))
        self.display(">>> Elapsed time: {}".format(et))
        self.eta= '--:--:--'

    @mainthread
    def display_progress(self, n):
        if self.nlines:
            now= datetime.datetime.now()
            d= (now-self.start_print_time).seconds
            if n > 10 and d > 10:
                # we have to wait a bit to get reasonable estimates
                lps= n/d
                eta= (self.nlines-n)/lps
            else:
                eta= 0

            #print("progress: {}/{} {:.1%} ETA {}".format(n, nlines, n/nlines, et))
            self.eta= '{} | {:.1%} | Z{:1.2f}'.format("Paused" if self.paused else datetime.timedelta(seconds=int(eta)), n/self.nlines, float(self.app.wpos[2]))

    def list_sdcard(self):
        if self.app.comms.list_sdcard(self._list_sdcard_results):
            # TODO open waiting dialog
            pass

    @mainthread
    def _list_sdcard_results(self, l):
        # dismiss waiting dialog
        fl= {}
        for f in l:
            f= '/sd/{}'.format(f)
            if f.endswith('/'):
                fl[f[:-1]]= {'size': 0, 'isdir': True}
            else:
                fl[f]= {'size': 0, 'isdir': False}

        # get file to print
        f= FileDialog()
        f.open(title= 'SD File to print', file_list= fl, cb= self._start_sd_print)

    def _start_sd_print(self, file_path, directory):
        Logger.info("MainWindow: SDcard print: {}".format(file_path))
        self.app.comms.write('play {}\n'.format(file_path))

    def show_viewer(self):
        if self.is_printing:
            self._show_viewer(self.app.gcode_file, self.last_path)
        else:
            # get file to view
            f= FileDialog()
            f.open(self.last_path, title= 'File to View', cb= self._show_viewer)

    def _show_viewer(self, file_path, directory):
        self.app.gcode_file= file_path
        self.app.sm.current= 'viewer'
        if directory != self.last_path:
            self.last_path= directory
            self.config.set('General', 'last_gcode_path', directory)
            self.app.config.write()

    def do_kill(self):
        if self.status == 'Alarm':
            self.app.comms.write('$X\n')
        else:
            # are you sure?
            mb = MessageBox(text='KILL - Are you Sure?', cb= self._do_kill)
            mb.open()

    def _do_kill(self, ok):
            if ok:
                self.app.comms.write('\x18')

    def do_update(self):
        try:
            p = subprocess.Popen(['git', 'pull'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result, err = p.communicate()
            if p.returncode != 0:
                self.add_line_to_log(">>> Update: Failed to run git pull")
            else:
                str= result.decode('utf-8').strip()
                self.add_line_to_log(">>> Update: {}".format(str))
                if not "up-to-date" in str:
                    self.add_line_to_log(">>> Update: Restart may be required")
        except:
            self.add_line_to_log(">>> Update: Error trying to update. See log")
            Logger.error('MainWindow: {}'.format(traceback.format_exc()))

    def show_camera_screen(self):
        self.app.sm.current= 'camera'

    @mainthread
    def tool_change_prompt(self, l):
        # Print is paused by gcode command M6, prompt for tool change
        self.display("ACTION NEEDED: Manual Tool Change: {}\nWait for machine to stop then you can jog around to change the tool. tap resume to continue".format(l))
        # we tell smoothie to suspend so we can save state and move the head around to change the tool
        # we need to issue resume M601 when we click the Resume button
        self.app.comms.write('M600\n')
        self.is_suspended= True

class TabbedCarousel(TabbedPanel):
    def on_index(self, instance, value):
        tab = instance.current_slide.tab
        if self.current_tab != tab:
            self.switch_to(tab)

    def switch_to(self, header):
        # hack needed as for some reason we get called with default tab even though we asked not to
        if not hasattr(header, 'slide'):
            return

        # we have to replace the functionality of the original switch_to
        self.current_tab.state = "normal"
        header.state = 'down'
        self._current_tab = header
        # set the carousel to load the appropriate slide
        # saved in the screen attribute of the tab head
        self.carousel.index = header.slide
        # we switched to a new screen in carousel check it
        if header.slide == 3: # macros screen
            self.macros.update_buttons()
        elif header.slide == 1: # DRO screen
            self.dro_widget.update_buttons()
        elif header.slide == 5: # extruder screen
            self.extruder.update_buttons()


class MainScreen(Screen):
    pass

class SmoothieHost(App):
    is_connected= BooleanProperty(False)
    status= StringProperty("Not Connected")
    wpos= ListProperty([0,0,0])
    mpos= ListProperty([0,0,0,0,0,0])
    fr= NumericProperty(0)
    sr= NumericProperty(0)
    lp= NumericProperty(0)
    is_desktop= BooleanProperty(False)
    is_cnc= BooleanProperty(False)
    tab_top= BooleanProperty(False)
    main_window= ObjectProperty()
    gcode_file= StringProperty()
    is_show_camera= BooleanProperty(False)
    manual_tool_change= BooleanProperty(False)

    #Factory.register('Comms', cls=Comms)
    def __init__(self, **kwargs):
        super(SmoothieHost, self).__init__(**kwargs)
        if len(sys.argv) > 1:
            # override com port
            self.use_com_port= sys.argv[1]
        else:
            self.use_com_port= None
        self.webserver= False
        self._blanked= False
        self.last_touch_time= 0

    def build_config(self, config):
        config.setdefaults('General', {
            'last_gcode_path': os.path.expanduser("~"),
            'last_print_file': '',
            'serial_port': 'serial:///dev/ttyACM0',
            'report_rate': '1',
            'blank_timeout': '0',
            'manual_tool_change' : 'false'
        })
        config.setdefaults('UI', {
            'desktop': 'false',
            'cnc': 'false',
            'tab_top': 'false'
        })

        config.setdefaults('Extruder', {
            'last_bed_temp': '60',
            'last_hotend_temp': '185',
            'length': '20',
            'speed': '300',
            'hotend_presets': '185 (PLA), 230 (ABS)',
            'bed_presets': '60 (PLA), 110 (ABS)'
        })
        config.setdefaults('Jog', {
            'xy_feedrate': '3000'
        })
        config.setdefaults('Web', {
            'webserver': 'false',
            'show_video': 'false',
            'camera_url': 'http://localhost:8080/?action=stream'
        })

    def build_settings(self, settings):
        jsondata = """
            [
                { "type": "title",
                  "title": "UI Settings" },

                { "type": "bool",
                  "title": "Desktop Layout",
                  "desc": "Turn on for a Desktop layout, otherwise it is RPI 7in touch screen layout",
                  "section": "UI",
                  "key": "desktop"
                },

                { "type": "bool",
                  "title": "CNC layout",
                  "desc": "Turn on for a CNC layout, otherwise it is a 3D printer Layout",
                  "section": "UI",
                  "key": "cnc"
                },

                { "type": "bool",
                  "title": "Tabs on top",
                  "desc": "TABS are on top of the screen",
                  "section": "UI",
                  "key": "tab_top"
                },

                { "type": "title",
                  "title": "General Settings" },

                { "type": "numeric",
                  "title": "Report rate",
                  "desc": "Rate in seconds to query for status from Smoothie",
                  "section": "General",
                  "key": "report_rate" },

                { "type": "numeric",
                  "title": "Blank Timeout",
                  "desc": "Inactive timeout in seconds before screen will blank",
                  "section": "General",
                  "key": "blank_timeout" },

                { "type": "bool",
                  "title": "Manual Tool change",
                  "desc": "On M6 let user do a manual tool change",
                  "section": "General",
                  "key": "manual_tool_change"
                },

                { "type": "title",
                  "title": "Web Settings" },

                { "type": "bool",
                  "title": "Web Server",
                  "desc": "Turn on Web server to remotely check progress",
                  "section": "Web",
                  "key": "webserver"
                },

                { "type": "bool",
                  "title": "Show Video",
                  "desc": "Display mjpeg video in web progress",
                  "section": "Web",
                  "key": "show_video"
                },

                { "type": "string",
                  "title": "Camera URL",
                  "desc": "URL for camera stream",
                  "section": "Web",
                  "key": "camera_url"
                },

                { "type": "title",
                  "title": "Extruder Settings" },

                { "type": "string",
                  "title": "Hotend Presets",
                  "desc": "Set the comma separated presets for the hotend temps",
                  "section": "Extruder",
                  "key": "hotend_presets"
                },

                { "type": "string",
                  "title": "Bed Presets",
                  "desc": "Set the comma separated presets for the bed temps",
                  "section": "Extruder",
                  "key": "bed_presets"
                }
            ]


        """
        config = ConfigParser()
        config.read('smoothiehost.ini')
        settings.add_json_panel('SmooPie application', config, data=jsondata)

    def on_config_change(self, config, section, key, value):
        #print("config changed: {} - {}: {}".format(section, key, value))
        token = (section, key)
        if token == ('UI', 'cnc'):
            self.is_cnc = value == "1"
        elif token == ('UI', 'tab_top'):
            self.tab_top = value == "1"
        elif token == ('Extruder', 'hotend_presets'):
            self.main_window.ids.extruder.ids.set_hotend_temp.values= value.split(',')
        elif token == ('Extruder', 'bed_presets'):
            self.main_window.ids.extruder.ids.set_bed_temp.values= value.split(',')
        elif token == ('General', 'blank_timeout'):
            self.blank_timeout= float(value)
        elif token == ('General', 'manual_tool_change'):
            self.manual_tool_change= value == '1'

    def on_stop(self):
        # The Kivy event loop is about to stop, stop the async main loop
        self.comms.stop(); # stop the aysnc loop
        if self.is_webserver:
            self.webserver.stop()
        # unblank if blanked
        self._on_touch(0, 0)

    def on_start(self):
        # in case we added something to the defaults, make sure they are written to the ini file
        self.config.update_config('smoothiehost.ini')

    def build(self):
        if self.config.getboolean('UI', 'desktop'):
            self.is_desktop= True
            # load the layouts for the desktop screen
            Builder.load_file('desktop.kv')
            #Window.size= (1280, 1024)
            Window.size= (1024, 768)
        else:
            self.is_desktop= False
            # load the layouts for rpi 7" touch screen
            Builder.load_file('rpi.kv')

        if self.config.getboolean('UI', 'cnc'):
            self.is_cnc= True
        else:
            self.is_cnc= False

        self.tab_top= self.config.getboolean('UI', 'tab_top')

        self.is_webserver= self.config.getboolean('Web', 'webserver')
        self.is_show_camera= self.config.getboolean('Web', 'show_video')

        self.comms= Comms(App.get_running_app(), self.config.getint('General', 'report_rate'))
        self.gcode_file= self.config.get('General', 'last_print_file')
        self.sm = ScreenManager()
        ms= MainScreen(name='main')
        self.sm.add_widget(ms)
        self.sm.add_widget(GcodeViewerScreen(name='viewer', comms= self.comms))
        self.main_window= ms.ids.main_window

        self.blank_timeout= self.config.getint('General', 'blank_timeout')
        Logger.info("SmoothieHost: screen blank set for {} seconds".format(self.blank_timeout))

        self.sm.bind(on_touch_down=self._on_touch)
        Clock.schedule_interval(self._every_second, 1)

        if not self.is_desktop:
            # setup for cnc or 3d printer
            # TODO need to also remove from tabs in desktop
            if self.is_cnc:
                # remove Extruder panel from carousel and tab
                self.main_window.ids.tc.remove_widget(self.main_window.ids.tc.extruder_tab)
                self.main_window.ids.carousel.remove_widget(self.main_window.ids.extruder)

            # else:
            #     # remove MPG panel
            #     self.main_window.ids.tc.remove_widget(self.main_window.ids.tc.mpg_tab)
            #     self.main_window.ids.carousel.remove_widget(self.main_window.ids.mpg_widget)

        # if not CNC mode then do not show the ZABC buttons in jogrose
        if not self.is_cnc:
            self.main_window.ids.tc.jogrose.jogrosemain.remove_widget(self.main_window.ids.tc.jogrose.abc_panel)

        if self.is_webserver:
            self.webserver= ProgressServer()
            self.webserver.start(self, 8000)

        if self.is_show_camera:
            url= self.config.get('Web', 'camera_url')
            self.sm.add_widget(CameraScreen(name='camera', url= url))

        return self.sm

    def _every_second(self, dt):
        if self.blank_timeout > 0 and not self.main_window.is_printing:
            self.last_touch_time += 1
            if self.last_touch_time >= self.blank_timeout:
                self.last_touch_time= 0
                self.blank_screen()

    def blank_screen(self):
        try:
            with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                f.write('1\n')
            self._blanked= True
        except:
            Logger.warning("SmoothieHost: unable to blank screen")

    def _on_touch(self, a, b):
        self.last_touch_time= 0
        if self._blanked:
            self._blanked= False
            try:
                with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                    f.write('0\n')
            except:
                pass

            return True

        return False

SmoothieHost().run()



