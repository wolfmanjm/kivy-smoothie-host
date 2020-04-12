import kivy

from kivy.app import App
from kivy.lang import Builder

from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
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
from kivy.uix.actionbar import ActionButton

from kivy.properties import NumericProperty, StringProperty, ObjectProperty, ListProperty, BooleanProperty
from kivy.vector import Vector
from kivy.clock import Clock, mainthread
from kivy.factory import Factory
from kivy.logger import Logger
from kivy.core.window import Window
from kivy.config import ConfigParser
from kivy.metrics import dp, Metrics

from native_file_chooser import NativeFileChooser
from mpg_knob import Knob

from comms import Comms
from message_box import MessageBox
from input_box import InputBox
from selection_box import SelectionBox
from file_dialog import FileDialog
from viewer import GcodeViewerScreen
from web_server import ProgressServer
from camera_screen import CameraScreen
from spindle_camera import SpindleCamera
from config_editor import ConfigEditor
from configv2_editor import ConfigV2Editor
from gcode_help import GcodeHelp
from text_editor import TextEditor
from tool_scripts import ToolScripts

import subprocess
import traceback
import queue
import math
import os
import sys
import datetime
import configparser
from functools import partial
import collections
import importlib
import signal

Window.softinput_mode = 'below_target'


class NumericInput(TextInput):
    """Text input that shows a numeric keypad"""
    def __init__(self, **kwargs):
        super(NumericInput, self).__init__(**kwargs)

    def on_focus(self, i, v):
        if v:
            self._last = self.text
            self.text = ""
            if App.get_running_app().is_desktop == 0:
                self.show_keyboard()
                if self.keyboard and self.keyboard.widget:
                    self.keyboard.widget.layout = "numeric.json"
                    self.m_keyboard = self.keyboard.widget
        else:
            if self.text == "":
                self.text = self._last
            if App.get_running_app().is_desktop == 0:
                if self.keyboard and self.keyboard.widget:
                    self.m_keyboard.layout = "qwerty"
                self.hide_keyboard()

    def on_parent(self, widget, parent):
        if App.get_running_app().is_desktop != 0:
            return
        self.keyboard_mode = 'managed'


class DROWidget(RelativeLayout):
    """DROWidget Shows realtime information in a DRO style"""
    curwcs = StringProperty('')

    def __init__(self, **kwargs):
        super(DROWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def enter_wpos(self, axis, v):
        i = ord(axis) - ord('x')
        v = v.strip()
        if v.startswith('/'):
            # we divide current value by this
            try:
                d = float(v[1:])
                v = str(self.app.wpos[i] / d)
            except Exception:
                Logger.warning("DROWidget: cannot divide by: {}".format(v))
                self.app.wpos[i] = self.app.wpos[i]
                return

        try:
            # needed because the filter does not allow -ive numbers WTF!!!
            f = float(v.strip())
        except Exception:
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
        # only used for ABC axis
        self.app.comms.write('G92 {}0\n'.format(a))

    def update_buttons(self):
        return "$I\n"

    def _on_curwcs(self):
        # foreach WCS button see if it is active or not
        for i in self.ids.wcs_buts.children:
            if i.text == self.curwcs:
                i.state = 'down'
            else:
                i.state = 'normal'


class MPGWidget(RelativeLayout):
    last_pos = NumericProperty(0)
    selected_axis = StringProperty('X')
    selected_index = NumericProperty(0)

    def __init__(self, **kwargs):
        super(MPGWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def handle_action(self):
        # Run button pressed
        if self.selected_index == -1:
            # change feed override
            self.app.comms.write('M220 S{}'.format(round(self.last_pos, 1)))
            return

        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
            return

        # if in non MPG mode then issue G0 in abs or rel depending on settings
        # if in MPG mode then issue $J commands when they occur
        if not self.ids.mpg_mode_tb.state == 'down':
            # normal mode
            cmd = 'G90' if self.ids.abs_mode_tb.state == 'down' else 'G91'

            # print('{} {}{} {}'.format(cmd1, self.selected_axis, round(self.last_pos, 3), cmd2))
            self.app.comms.write('M120 {} G0 {}{} M121\n'.format(cmd, self.selected_axis, round(self.last_pos, 3)))

    def handle_change(self, ticks):
        if self.selected_index == -1:
            # change feed override
            self.last_pos += ticks
            if self.last_pos < 1:
                self.last_pos = 1
            return

        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
            return

        # change an axis
        if self.ids.x01.active:
            d = 0.01 * ticks
        elif self.ids.x001.active:
            d = 0.001 * ticks
        else:
            d = 0.1 * ticks
        self.last_pos = self.last_pos + d
        axis = self.selected_axis
        # MPG mode
        if self.ids.mpg_mode_tb.state == 'down':
            self.app.comms.write('$J {}{}\n'.format(self.selected_axis.upper(), d))

    def index_changed(self, i):
        if i == -1:
            # Feedrate overide
            self.last_pos = self.app.fro
        elif self.ids.abs_mode_tb.state == 'down':
            # show current axis position
            self.last_pos = self.app.wpos[i]
        else:
            # relative mode zero it
            self.last_pos = 0

    def abs_mode_changed(self):
        self.index_changed(self.selected_index)


class CircularButton(ButtonBehavior, Widget):
    text = StringProperty()

    def collide_point(self, x, y):
        return Vector(x, y).distance(self.center) <= self.width / 2


class ArrowButton(ButtonBehavior, Widget):
    text = StringProperty()
    angle = NumericProperty()
    # def collide_point(self, x, y):
    #     bmin = Vector(self.center) - Vector(25, 25)
    #     bmax = Vector(self.center) + Vector(25, 25)
    #     return Vector.in_bbox((x, y), bmin, bmax)


class JogRoseWidget(BoxLayout):
    xy_feedrate = StringProperty()
    abc_sel = StringProperty('Z')

    def __init__(self, **kwargs):
        super(JogRoseWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.xy_feedrate = self.app.config.get('Jog', 'xy_feedrate')

    def handle_action(self, axis, v):
        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
            self.app.main_window.display("NOTE: Cannot jog while printing")
            return

        x10 = self.ids.x10cb.active
        if x10:
            v *= 10

        fr = self.xy_feedrate

        if axis == 'O':
            self.app.comms.write('M120 G21 G90 G0 X0 Y0 F{} M121\n'.format(fr))
        elif axis == 'H':
            self.app.comms.write('$H\n')
        else:
            self.app.comms.write('M120 G21 G91 G0 {}{} F{} M121\n'.format(axis, v, fr))

    def update_xy_feedrate(self):
        fr = self.ids.xy_feedrate.text
        self.app.config.set('Jog', 'xy_feedrate', fr)
        self.app.config.write()
        self.xy_feedrate = fr

    def motors_off(self):
        self.app.comms.write('M18\n')


class KbdWidget(GridLayout):
    def __init__(self, **kwargs):
        super(KbdWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_command = ""

    def _add_line_to_log(self, s):
        self.app.main_window.display(s)

    def do_action(self, key):
        if key == 'Send':
            # Logger.debug("KbdWidget: Sending {}".format(self.display.text))
            if self.display.text.strip():
                self._add_line_to_log('<< {}'.format(self.display.text))
                self.app.comms.write('{}\n'.format(self.display.text))
                self.last_command = self.display.text
            self.display.text = ''
        elif key == 'Repeat':
            self.display.text = self.last_command
        elif key == 'BS':
            self.display.text = self.display.text[:-1]
        elif key == '?':
            self.handle_input('?')
        else:
            self.display.text += key

    def handle_input(self, s):
        self.app.command_input(s)
        self.display.text = ''


class MainWindow(BoxLayout):
    status = StringProperty('Idle')
    wpos = ListProperty([0, 0, 0])
    eta = StringProperty('--:--:--')
    is_printing = BooleanProperty(False)
    is_suspended = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self._trigger = Clock.create_trigger(self.async_get_display_data)
        self._q = queue.Queue()
        self.config = self.app.config
        self.last_path = self.config.get('General', 'last_gcode_path')
        self.paused = False
        self.last_line = 0

        # print('font size: {}'.format(self.ids.log_window.font_size))
        # Clock.schedule_once(self.my_callback, 2) # hack to overcome the page layout not laying out initially

    def on_touch_down(self, touch):
        if self.ids.log_window.collide_point(touch.x, touch.y):
            if touch.is_triple_tap:
                self.ids.log_window.data = []
                return True

        return super(MainWindow, self).on_touch_down(touch)

    def add_line_to_log(self, s, overwrite=False):
        ''' Add lines to the log window, which is trimmed to the last 200 lines '''
        max_lines = 200  # TODO needs to be configurable
        n = len(self.ids.log_window.data)
        if overwrite:
            self.ids.log_window.data[n - 1] = ({'text': s})
            return

        self.ids.log_window.data.append({'text': s})
        # we use some hysterysis here so we don't truncate every line added over max_lines
        n = n - max_lines  # how many lines over our max
        if n > 10:
            # truncate log to last max_lines, we delete the oldest 10 or so lines
            del self.ids.log_window.data[0:n]

    def connect(self):
        if self.app.is_connected:
            if self.is_printing:
                mb = MessageBox(text='Cannot Disconnect while printing - Abort first, then wait')
                mb.open()
            else:
                self._disconnect()

        else:
            port = self.config.get('General', 'serial_port') if not self.app.use_com_port else self.app.use_com_port
            self.add_line_to_log("Connecting to {}...".format(port))
            self.app.comms.connect(port)

    def _disconnect(self, b=True):
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
            data = self._q.get(False)
            if data.endswith('\r'):
                self.add_line_to_log(data[0:-1], True)
            else:
                self.add_line_to_log(data)

    @mainthread
    def connected(self):
        Logger.debug("MainWindow: Connected...")
        self.add_line_to_log("...Connected")
        self.app.is_connected = True
        self.ids.connect_button.state = 'down'
        self.ids.connect_button.text = "Disconnect"
        self.ids.print_but.text = 'Run'
        self.paused = False
        self.is_printing = False

    @mainthread
    def disconnected(self):
        Logger.debug("MainWindow: Disconnected...")
        self.app.is_connected = False
        self.is_printing = False
        self.ids.connect_button.state = 'normal'
        self.ids.connect_button.text = "Connect"
        self.add_line_to_log("...Disconnected")

    @mainthread
    def update_status(self, stat, d):
        self.status = stat
        self.app.status = stat
        if 'WPos' in d:
            self.wpos = d['WPos']
            self.app.wpos = self.wpos

        if 'MPos' in d:
            self.app.mpos = d['MPos']

        if 'F' in d:
            if len(d['F']) == 2:
                self.app.fr = d['F'][0]
                self.app.frr = d['F'][0]
                self.app.fro = d['F'][1]
            elif len(d['F']) == 3:
                # NOTE fr is current actual feedrate and frr is requested feed rate (from the Fxxx)
                self.app.fr = d['F'][0]
                self.app.frr = d['F'][1]
                self.app.fro = d['F'][2]

        if 'S' in d:
            self.app.sr = d['S'][0]

        if 'L' in d:
            self.app.lp = d['L'][0]

        if not self.app.is_cnc:
            # extract temperature readings and update the extruder property
            # We only want to update once per query
            t = {}
            if 'T' in d:
                t['hotend0'] = (d['T'][0], d['T'][1])
            if 'T1' in d:
                t['hotend1'] = (d['T1'][0], d['T1'][1])
            if 'B' in d:
                t['bed'] = (d['B'][0], d['B'][1])

            if t:
                self.ids.extruder.update_temp(t)

    @mainthread
    def update_state(self, a):
        if not self.app.is_cnc:
            self.ids.extruder.curtool = int(a[9][1])
        self.ids.dro_widget.curwcs = a[1]
        self.app.is_inch = a[3] == 'G20'
        self.app.is_abs = a[4] == 'G90'
        self.app.is_spindle_on = a[7] == 'M3'

    @mainthread
    def alarm_state(self, s):
        ''' called when smoothie is in Alarm state and it is sent a gcode '''
        self.add_line_to_log("! Alarm state: {}".format(s))

    def ask_exit(self, restart=False):
        # are you sure?
        if restart:
            mb = MessageBox(text='Restart - Are you Sure?', cb=self._do_restart)
        else:
            mb = MessageBox(text='Exit - Are you Sure?', cb=self._do_exit)
        mb.open()

    def _do_exit(self, ok):
        if ok:
            self.app.stop()

    def _do_restart(self, ok):
        if ok:
            self.app.stop()
            os.execl(sys.executable, sys.executable, *sys.argv)

    def ask_shutdown(self):
        # are you sure?
        mb = MessageBox(text='Shutdown - Are you Sure?', cb=self._do_shutdown)
        mb.open()

    def _do_shutdown(self, ok):
        if ok:
            os.system('/sbin/shutdown -h now')
            self._do_exit(True)

    def change_port(self):
        ll = self.app.comms.get_ports()
        ports = [self.config.get('General', 'serial_port')]  # current port is first in list
        for p in ll:
            ports.append('serial://{}'.format(p.device))

        ports.append('network...')

        sb = SelectionBox(title='Select port', text='Select the port to open from drop down', values=ports, cb=self._change_port)
        sb.open()

    def _change_port(self, s):
        if s:
            Logger.info('MainWindow: Selected port {}'.format(s))

            if s.startswith('network'):
                mb = InputBox(title='Network address', text='Enter network address as "ipaddress[:port]"', cb=self._new_network_port)
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
        mb = MessageBox(text='Abort - Are you Sure?', cb=self._abort_print)
        mb.open()

    def _abort_print(self, ok):
        if ok:
            self.app.comms.stream_pause(False, True)

    @mainthread
    def action_paused(self, paused, suspended=False):
        # comms layer is telling us we paused or unpaused
        self.ids.print_but.text = 'Resume' if paused else 'Pause'
        self.paused = paused
        self.is_suspended = suspended
        if paused:
            if suspended:
                self.add_line_to_log(">>> Streaming Suspended, Resume or KILL as needed")
            else:
                self.add_line_to_log(">>> Streaming Paused, Abort or Continue as needed")

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
                    self.app.comms.write('resume\n')
                else:
                    self.app.comms.stream_pause(False)

                self.is_suspended = False

        else:
            # get file to print
            f = Factory.filechooser()
            f.open(self.last_path, cb=self._start_print)

    def _start_print(self, file_path=None, directory=None):
        # start comms thread to stream the file
        # set comms.ping_pong to False for fast stream mode
        if file_path is None:
            file_path = self.app.gcode_file
        if directory is None:
            directory = self.last_path

        Logger.info('MainWindow: printing file: {}'.format(file_path))

        try:
            self.nlines = Comms.file_len(file_path)  # get number of lines so we can do progress and ETA
            Logger.debug('MainWindow: number of lines: {}'.format(self.nlines))
        except Exception:
            Logger.warning('MainWindow: exception in file_len: {}'.format(traceback.format_exc()))
            self.nlines = None

        self.start_print_time = datetime.datetime.now()
        self.display('>>> Running file: {}, {} lines'.format(file_path, self.nlines))

        if self.app.comms.stream_gcode(file_path, progress=lambda x: self.display_progress(x)):
            self.display('>>> Run started at: {}'.format(self.start_print_time.strftime('%x %X')))
        else:
            self.display('WARNING Unable to start print')
            return

        self.set_last_file(directory, file_path)

        self.ids.print_but.text = 'Pause'
        self.is_printing = True
        self.paused = False

    def set_last_file(self, directory, file_path):
        if directory != self.last_path:
            self.last_path = directory
            self.config.set('General', 'last_gcode_path', directory)

        self.app.gcode_file = file_path
        self.config.set('General', 'last_print_file', file_path)
        self.config.write()

    def reprint(self):
        # are you sure?
        mb = MessageBox(text='ReRun {}?'.format(self.app.gcode_file), cb=self._reprint)
        mb.open()

    def _reprint(self, ok):
        if ok:
            self._start_print()

    @mainthread
    def start_last_file(self):
        if self.app.gcode_file:
            self._start_print()

    def review(self):
        self._show_viewer(self.app.gcode_file, self.last_path)

    @mainthread
    def stream_finished(self, ok):
        ''' called when streaming gcode has finished, ok is True if it completed '''
        self.ids.print_but.text = 'Run'
        self.is_printing = False
        now = datetime.datetime.now()
        self.display('>>> Run finished {}'.format('ok' if ok else 'abnormally'))
        self.display(">>> Run ended at : {}, Last line: {}".format(now.strftime('%x %X'), self.last_line))
        et = datetime.timedelta(seconds=int((now - self.start_print_time).seconds))
        self.display(">>> Elapsed time: {}".format(et))
        self.eta = '--:--:--'

    @mainthread
    def display_progress(self, n):
        if self.nlines and n <= self.nlines:
            now = datetime.datetime.now()
            d = (now - self.start_print_time).seconds
            if n > 10 and d > 10:
                # we have to wait a bit to get reasonable estimates
                lps = n / d
                eta = (self.nlines - n) / lps
            else:
                eta = 0

            # print("progress: {}/{} {:.1%} ETA {}".format(n, nlines, n/nlines, et))
            self.eta = '{} | {:.1%} | L{}'.format("Paused" if self.paused else datetime.timedelta(seconds=int(eta)), n / self.nlines, n)

        self.last_line = n

    def list_sdcard(self):
        if self.app.comms.list_sdcard(self._list_sdcard_results):
            # TODO open waiting dialog
            pass

    @mainthread
    def _list_sdcard_results(self, l):
        # dismiss waiting dialog
        fl = {}
        for f in l:
            f = '/sd/{}'.format(f)
            # if f.endswith('/'):
            #     fl[f[:-1]] = {'size': 0, 'isdir': True}
            # else:
            #     fl[f] = {'size': 0, 'isdir': False}

            # as we can't handle subdirectories yet we do not list them
            if not f.endswith('/'):
                fl[f] = {'size': 0, 'isdir': False}

        # get file to print
        f = FileDialog()
        f.open(title='SD File to print', file_list=fl, cb=self._start_sd_print)

    def _start_sd_print(self, file_path, directory):
        Logger.info("MainWindow: SDcard print: {}".format(file_path))
        self.app.comms.write('play {}\n'.format(file_path))

    def show_viewer(self):
        if self.is_printing:
            self._show_viewer(self.app.gcode_file, self.last_path)
        else:
            # get file to view
            f = Factory.filechooser()
            f.open(self.last_path, title='File to View', cb=self._show_viewer)

    def _show_viewer(self, file_path, directory):
        self.set_last_file(directory, file_path)
        self.app.sm.current = 'viewer'

    def do_kill(self):
        if self.status == 'Alarm':
            self.app.comms.write('$X\n')
        else:
            # are you sure?
            mb = MessageBox(text='KILL - Are you Sure?', cb=self._do_kill)
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
                need_update = True
                str = result.decode('utf-8').splitlines()
                self.add_line_to_log(">>> Update:")
                for l in str:
                    self.add_line_to_log(l)
                    if "up-to-date" in l:
                        need_update = False

                if need_update:
                    self.add_line_to_log(">>> Update: Restart may be required")
        except Exception:
            self.add_line_to_log(">>> Update: Error trying to update. See log")
            Logger.error('MainWindow: {}'.format(traceback.format_exc()))

    def show_camera_screen(self):
        self.app.sm.current = 'camera'

    @mainthread
    def tool_change_prompt(self, l):
        # Print is paused by gcode command M6, prompt for tool change
        self.display("ACTION NEEDED: Manual Tool Change:\n Tool: {}\nWait for machine to stop, then you can jog around to change the tool.\n tap resume to continue".format(l))

    @mainthread
    def m0_dlg(self):
        MessageBox(text='M0 Pause, click OK to continue', cb=self._m0_dlg).open()

    def _m0_dlg(self, ok):
        self.app.comms.release_m0()

    # called by query timer in comms context, return strings for queries to send
    def get_queries(self):
        if not self.app.is_connected or self.is_printing:
            return ""

        if not self.app.is_v2 and self.status == 'Run':
            # for v1 we do not send these commands when running as they clog up the USB serial channel
            return ""

        cmd = ""
        if self.app.is_desktop == 0:
            # we only send query for the tab we are on
            current_tab = self.ids.tabs.current_tab.text
            if current_tab == 'Macros':  # macros screen
                cmd += self.ids.macros.update_buttons()

            # always need the $I
            cmd += self.ids.dro_widget.update_buttons()

        else:
            # in desktop mode we need to poll for state changes for macros and DRO
            cmd += self.ids.macros.update_buttons()
            cmd += self.ids.dro_widget.update_buttons()

        return cmd

    def config_editor(self):
        self.app.config_editor.open()

    def text_editor(self):
        # get file to view
        f = Factory.filechooser()
        f.open(self.last_path, title='File to Edit', filters=['*'], cb=self._text_editor)

    def _text_editor(self, file_path, directory):
        self.app.text_editor.open(file_path)
        self.app.sm.current = 'text_editor'


class MainScreen(Screen):
    pass


class SmoothieHost(App):
    is_connected = BooleanProperty(False)
    status = StringProperty("Not Connected")
    wpos = ListProperty([0, 0, 0])
    mpos = ListProperty([0, 0, 0, 0, 0, 0])
    fr = NumericProperty(0)
    frr = NumericProperty(0)
    fro = NumericProperty(100)
    sr = NumericProperty(0)
    lp = NumericProperty(0)
    is_inch = BooleanProperty(False)
    is_spindle_on = BooleanProperty(False)
    is_abs = BooleanProperty(True)
    is_desktop = NumericProperty(0)
    is_cnc = BooleanProperty(False)
    tab_top = BooleanProperty(False)
    main_window = ObjectProperty()
    gcode_file = StringProperty()
    is_show_camera = BooleanProperty(False)
    is_spindle_camera = BooleanProperty(False)
    manual_tool_change = BooleanProperty(False)
    is_v2 = BooleanProperty(True)
    wait_on_m0 = BooleanProperty(False)

    # Factory.register('Comms', cls=Comms)
    def __init__(self, **kwargs):
        super(SmoothieHost, self).__init__(**kwargs)
        if len(sys.argv) > 1:
            # override com port
            self.use_com_port = sys.argv[1]
        else:
            self.use_com_port = None
        self.webserver = False
        self._blanked = False
        self.blank_timeout = 0
        self.last_touch_time = 0
        self.camera_url = None
        self.loaded_modules = []
        self.secs = 0
        self.fast_stream = False
        self.last_probe = {'X': 0, 'Y': 0, 'Z': 0, 'status': False}
        self.tool_scripts = ToolScripts()
        self.desktop_changed = False
        self.command_history = None

    def build_config(self, config):
        config.setdefaults('General', {
            'last_gcode_path': os.path.expanduser("~"),
            'last_print_file': '',
            'serial_port': 'serial:///dev/ttyACM0',
            'report_rate': '1.0',
            'blank_timeout': '0',
            'manual_tool_change': 'false',
            'wait_on_m0': 'false',
            'fast_stream': 'false',
            'v2': 'false',
            'is_spindle_camera': 'false'
        })
        config.setdefaults('UI', {
            'display_type': "RPI Touch",
            'cnc': 'false',
            'tab_top': 'false',
            'screen_size': 'auto',
            'screen_pos': 'auto',
            'filechooser': 'default'
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
            'camera_url': 'http://localhost:8080/?action=snapshot'
        })

    def build_settings(self, settings):
        jsondata = """
            [
                { "type": "title",
                  "title": "UI Settings" },

                { "type": "options",
                  "title": "Desktop Layout",
                  "desc": "Select Display layout, RPI is for 7in touch screen layout",
                  "section": "UI",
                  "key": "display_type",
                  "options": ["RPI Touch", "Small Desktop", "Large Desktop", "Wide Desktop", "RPI Full Screen"]
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

                { "type": "options",
                  "title": "File Chooser",
                  "desc": "Which filechooser to use in desktop mode",
                  "section": "UI",
                  "key": "filechooser",
                  "options": ["default", "wx", "zenity", "kdialog"]
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

                { "type": "bool",
                  "title": "Wait on M0",
                  "desc": "On M0 popup a dialog and pause until it is dismissed",
                  "section": "General",
                  "key": "wait_on_m0"
                },

                { "type": "bool",
                  "title": "Spindle Camera",
                  "desc": "Enable the spindle camera screen",
                  "section": "General",
                  "key": "is_spindle_camera"
                },

                { "type": "bool",
                  "title": "Version 2 Smoothie",
                  "desc": "Select for version 2 smoothie",
                  "section": "General",
                  "key": "v2"
                },

                { "type": "bool",
                  "title": "Fast Stream",
                  "desc": "Allow fast stream for laser over network",
                  "section": "General",
                  "key": "fast_stream"
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
        settings.add_json_panel('SmooPie application', self.config, data=jsondata)

    def on_config_change(self, config, section, key, value):
        # print("config changed: {} - {}: {}".format(section, key, value))
        token = (section, key)
        if token == ('UI', 'cnc'):
            self.is_cnc = value == "1"
            self.main_window.display("NOTICE: Restart is needed")
        elif token == ('UI', 'display_type'):
            self.desktop_changed = True
            self.main_window.display("NOTICE: Restart is needed")
        elif token == ('UI', 'tab_top'):
            self.tab_top = value == "1"
        elif token == ('Extruder', 'hotend_presets'):
            self.main_window.ids.extruder.ids.set_hotend_temp.values = value.split(',')
        elif token == ('Extruder', 'bed_presets'):
            self.main_window.ids.extruder.ids.set_bed_temp.values = value.split(',')
        elif token == ('General', 'blank_timeout'):
            self.blank_timeout = float(value)
        elif token == ('General', 'manual_tool_change'):
            self.manual_tool_change = value == '1'
        elif token == ('General', 'wait_on_m0'):
            self.wait_on_m0 = value == '1'
        elif token == ('Web', 'camera_url'):
            self.camera_url = value
        else:
            self.main_window.display("NOTICE: Restart is needed")

    def on_stop(self):
        # The Kivy event loop is about to stop, stop the async main loop
        self.comms.stop()   # stop the aysnc loop
        if self.is_webserver:
            self.webserver.stop()
        if self.blank_timeout > 0:
            # unblank if blanked
            self.unblank_screen()
        # stop any loaded modules
        for m in self.loaded_modules:
            m.stop()

    def on_start(self):
        # in case we added something to the defaults, make sure they are written to the ini file
        self.config.update_config('smoothiehost.ini')

    def window_request_close(self, win):
        if self.desktop_changed:
            # if the desktop changed we reset the window size and pos
            self.config.set('UI', 'screen_size', 'auto')
            self.config.set('UI', 'screen_pos', 'auto')
            self.config.write()

        elif self.is_desktop == 2 or self.is_desktop == 3:
            # Window.size is automatically adjusted for density, must divide by density when saving size
            self.config.set('UI', 'screen_size', "{}x{}".format(int(Window.size[0] / Metrics.density), int(Window.size[1] / Metrics.density)))
            self.config.set('UI', 'screen_pos', "{},{}".format(Window.top, Window.left))
            Logger.info('close: Window.size: {}, Window.top: {}, Window.left: {}'.format(Window.size, Window.top, Window.left))

            self.config.write()

        return False

    def build(self):
        lt = self.config.get('UI', 'display_type')
        dtlut = {
            "RPI Touch": 0,
            "Small Desktop": 1,
            "Large Desktop": 2,
            "Wide Desktop": 3,
            "RPI Full Screen": 4
        }

        self.is_desktop = dtlut.get(lt, 0)

        # load the layouts for the desktop screen
        if self.is_desktop == 1:
            Builder.load_file('desktop.kv')
            Window.size = (1024, 768)

        elif self.is_desktop == 2 or self.is_desktop == 3 or self.is_desktop == 4:
            Builder.load_file('desktop_large.kv' if self.is_desktop == 2 else 'desktop_wide.kv')
            if self.is_desktop != 4:
                # because rpi_egl does not like to be told the size
                s = self.config.get('UI', 'screen_size')
                if s == 'auto':
                    Window.size = (1280, 1024) if self.is_desktop == 2 else (1280, 800)
                elif 'x' in s:
                    (w, h) = s.split('x')
                    Window.size = (int(w), int(h))
                p = self.config.get('UI', 'screen_pos')
                if p != 'auto' and ',' in p:
                    (t, l) = p.split(',')
                    Window.top = int(t)
                    Window.left = int(l)
            Window.bind(on_request_close=self.window_request_close)

        else:
            self.is_desktop = 0
            # load the layouts for rpi 7" touch screen
            Builder.load_file('rpi.kv')

        self.is_cnc = self.config.getboolean('UI', 'cnc')
        self.tab_top = self.config.getboolean('UI', 'tab_top')
        self.is_webserver = self.config.getboolean('Web', 'webserver')
        self.is_show_camera = self.config.getboolean('Web', 'show_video')
        self.is_spindle_camera = self.config.getboolean('General', 'is_spindle_camera')
        self.manual_tool_change = self.config.getboolean('General', 'manual_tool_change')
        self.wait_on_m0 = self.config.getboolean('General', 'wait_on_m0')
        self.is_v2 = self.config.getboolean('General', 'v2')

        self.comms = Comms(App.get_running_app(), self.config.getfloat('General', 'report_rate'))
        self.gcode_file = self.config.get('General', 'last_print_file')
        self.sm = ScreenManager(transition=NoTransition())
        ms = MainScreen(name='main')
        self.main_window = ms.ids.main_window
        self.sm.add_widget(ms)
        self.sm.add_widget(GcodeViewerScreen(name='viewer', comms=self.comms))
        if self.is_v2:
            self.config_editor = ConfigV2Editor(name='config_editor')
        else:
            self.config_editor = ConfigEditor(name='config_editor')
        self.sm.add_widget(self.config_editor)
        self.gcode_help = GcodeHelp(name='gcode_help')
        self.sm.add_widget(self.gcode_help)
        if self.is_desktop == 0:
            self.text_editor = TextEditor(name='text_editor')
            self.sm.add_widget(self.text_editor)

        self.blank_timeout = self.config.getint('General', 'blank_timeout')
        Logger.info("SmoothieHost: screen blank set for {} seconds".format(self.blank_timeout))

        self.sm.bind(on_touch_down=self._on_touch)
        Clock.schedule_interval(self._every_second, 1)

        # select the file chooser to use
        # select which one we want from config
        filechooser = self.config.get('UI', 'filechooser')
        if self.is_desktop > 0:
            if filechooser != 'default':
                NativeFileChooser.type_name = filechooser
                Factory.register('filechooser', cls=NativeFileChooser)
                try:
                    f = Factory.filechooser()
                except Exception:
                    Logger.error("SmoothieHost: can't use selected file chooser: {}".format(filechooser))
                    Factory.unregister('filechooser')
                    Factory.register('filechooser', cls=FileDialog)

            else:
                # use Kivy filechooser
                Factory.register('filechooser', cls=FileDialog)

            # we want to capture arrow keys
            Window.bind(on_key_down=self._on_keyboard_down)
        else:
            # use Kivy filechooser
            Factory.register('filechooser', cls=FileDialog)

        # setup for cnc or 3d printer
        if self.is_cnc:
            if self.is_desktop < 3:
                # remove Extruder panel from tabpanel and tab
                self.main_window.ids.tabs.remove_widget(self.main_window.ids.tabs.extruder_tab)

        # if not CNC mode then do not show the ZABC buttons in jogrose
        if not self.is_cnc:
            self.main_window.ids.tabs.jog_rose.jogrosemain.remove_widget(self.main_window.ids.tabs.jog_rose.abc_panel)

        if self.is_webserver:
            self.webserver = ProgressServer()
            self.webserver.start(self, 8000)

        if self.is_show_camera:
            self.camera_url = self.config.get('Web', 'camera_url')
            self.sm.add_widget(CameraScreen(name='web cam'))
            self.main_window.tools_menu.add_widget(ActionButton(text='Web Cam', on_press=lambda x: self._show_web_cam()))

        if self.is_spindle_camera:
            if self.is_desktop in [0, 4]:
                try:
                    self.sm.add_widget(SpindleCamera(name='spindle camera'))
                except Exception as err:
                    self.main_window.display('ERROR: failed to load spindle camera. Check logs')
                    Logger.error('Main: spindle camera exception: {}'.format(err))

            self.main_window.tools_menu.add_widget(ActionButton(text='Spindle Cam', on_press=lambda x: self._show_spindle_cam()))

        # load any modules specified in config
        self._load_modules()

        if self.blank_timeout > 0:
            # unblank if blanked
            self.unblank_screen()

        return self.sm

    def _show_spindle_cam(self):
        if self.is_desktop in [0, 4]:
            self.sm.current = "spindle camera"
        else:
            # we run it as a separate program so it is in its own window
            subprocess.Popen(['python3', 'spindle_camera.py'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _show_web_cam(self):
        self.sm.current = "web cam"

    def _on_keyboard_down(self, instance, key, scancode, codepoint, modifiers):
        # print("key: {}, scancode: {}, codepoint: {}, modifiers: {}".format(key, scancode, codepoint, modifiers))
        # control uses finer move, shift uses coarse move
        v = 0.1
        if len(modifiers) >= 1:
            if 'ctrl' in modifiers:
                v = 0.01
            elif 'shift' in modifiers:
                v = 1

        choices = {
            273: "Y{}".format(v),
            275: "X{}".format(v),
            274: "Y{}".format(-v),
            276: "X{}".format(-v),
            280: "Z{}".format(v),
            281: "Z{}".format(-v)
        }

        s = choices.get(key, None)
        if s is not None:
            if not (self.main_window.is_printing and not self.main_window.is_suspended):
                self.comms.write('$J {}\n'.format(s))

            return True

        # handle command history if in desktop mode
        if self.is_desktop > 0:
            if v == 0.01:  # it is a control key
                if codepoint == 'p':
                    # get previous history by finding all the recently sent commands
                    if not self.command_history:
                        self.command_history = [x['text'] for x in self.main_window.ids.log_window.data if x['text'].startswith('<< ')]

                    if self.command_history:
                        last = self.command_history.pop()
                        self.main_window.ids.entry.text = last[3:]

                elif codepoint == 'n':
                    # TODO get next history
                    pass
                elif codepoint == 'c':
                    # clear console
                    self.main_window.ids.log_window.data = []
                    self.command_history = None

            elif self.command_history:
                self.command_history = None

        return False

    def command_input(self, s):
        if s.startswith('!'):
            # shell command send to unix shell
            self.main_window.display('> {}'.format(s))
            try:
                p = subprocess.Popen(s[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
                result, err = p.communicate()
                for l in result.splitlines():
                    self.main_window.display(l)
                for l in err.splitlines():
                    self.main_window.display(l)
                if p.returncode != 0:
                    self.main_window.display('returncode: {}'.format(p.returncode))
            except Exception as err:
                self.main_window.display('> command exception: {}'.format(err))

        elif s == '?':
            self.gcode_help.populate()
            self.sm.current = 'gcode_help'

        else:
            self.main_window.display('<< {}'.format(s))
            self.comms.write('{}\n'.format(s))

    # when we hit enter it refocuses the the input
    def _refocus_text_input(self, *args):
        Clock.schedule_once(self._refocus_it)

    def _refocus_it(self, *args):
        self.main_window.ids.entry.focus = True

    def _load_modules(self):
        if not self.config.has_section('modules'):
            return

        try:
            for key in self.config['modules']:
                Logger.info("load_modules: loading module {}".format(key))
                mod = importlib.import_module('modules.{}'.format(key))
                if mod.start(self.config['modules'][key]):
                    Logger.info("load_modules: loaded module {}".format(key))
                    self.loaded_modules.append(mod)
                else:
                    Logger.info("load_modules: module {} failed to start".format(key))

        except Exception:
            Logger.warn("load_modules: exception: {}".format(traceback.format_exc()))

    def _every_second(self, dt):
        ''' called every second '''

        self.secs += 1
        if self.blank_timeout > 0 and not self.main_window.is_printing:
            self.last_touch_time += 1
            if self.last_touch_time >= self.blank_timeout:
                self.last_touch_time = 0
                self.blank_screen()

    def blank_screen(self):
        try:
            with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                f.write('1\n')
            self._blanked = True
        except Exception:
            Logger.warning("SmoothieHost: unable to blank screen")

    def unblank_screen(self):
        try:
            with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                f.write('0\n')
        except Exception:
            pass

    def _on_touch(self, a, b):
        self.last_touch_time = 0
        if self._blanked:
            self._blanked = False
            self.unblank_screen()
            return True

        return False


def handle_exception(exc_type, exc_value, exc_traceback):
    """ handle all exceptions """

    # KeyboardInterrupt is a special case.
    # We don't raise the error dialog when it occurs.
    if issubclass(exc_type, KeyboardInterrupt):
        return

    Logger.error("Unhandled Exception:")
    Logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    try:
        App.get_running_app().stop()
    except Exception:
        pass


# we want to handle TERM signal cleanly (sent by sv down)
def handleSigTERM(a, b):
    App.get_running_app().stop()


signal.signal(signal.SIGTERM, handleSigTERM)

# install handler for exceptions
sys.excepthook = handle_exception
SmoothieHost().run()
