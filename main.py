import kivy

from kivy.config import Config
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
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior, FocusBehavior
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
# needed to fix sys.excepthook errors, fixed in 2.x.x
from kivy.uix.recycleview.views import RecycleDataViewBehavior, _cached_views, _view_base_cache
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.core.clipboard import Clipboard

from native_file_chooser import NativeFileChooser
from mpg_knob import Knob
from libs.hat import Hat

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
from notify import Notify
from calc_widget import CalcScreen
from uart_logger import UartLogger
from tmc_configurator import TMCConfigurator
from spindle_handler import SpindleHandler

import subprocess
import threading
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

# we must have Python version between 3.7.3 and 3.10.x
assert (3, 10, 99) >= sys.version_info >= (3, 7, 3), f"Python version needs to be >= 3.7.3 and <= 3.10.x, you have {sys.version}"

kivy.require('2.1.0')

# Window.softinput_mode = 'below_target'


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''
    touch_deselect_last = BooleanProperty(True)
    is_focusable = BooleanProperty(False)


class LogLabel(RecycleDataViewBehavior, Label):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(LogLabel, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(LogLabel, self).on_touch_down(touch):
            return True
        if touch.is_double_tap and self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            App.get_running_app().last_command = rv.data[index]['text']
            # also stick in clipboard if we are running X
            Clipboard.copy(rv.data[index]['text'])


class NumericInput(TextInput):
    """Text input that shows a numeric keypad"""
    def __init__(self, **kwargs):
        super(NumericInput, self).__init__(**kwargs)

    def on_focus(self, i, v):
        if v:
            self._last = self.text
            self.text = ""
            if App.get_running_app().is_touch:
                self.show_keyboard()
                if self.keyboard and self.keyboard.widget:
                    self.keyboard.widget.layout = "numeric.json"
                    self.m_keyboard = self.keyboard.widget
        else:
            if self.text == "":
                self.text = self._last
            if App.get_running_app().is_touch:
                if self.keyboard and self.keyboard.widget:
                    self.m_keyboard.layout = "qwerty"
                self.hide_keyboard()

    def on_parent(self, widget, parent):
        if App.get_running_app().is_touch:
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
                Logger.warning(f"DROWidget: cannot divide by: {v}")
                self.app.wpos[i] = self.app.wpos[i]
                return

        try:
            # needed because the filter does not allow -ive numbers WTF!!!
            f = float(v.strip())
        except Exception:
            Logger.warning(f"DROWidget: invalid float input: {v}")
            # set the display back to what it was, this looks odd but it forces the display to update
            self.app.wpos[i] = self.app.wpos[i]
            return

        Logger.debug(f"DROWidget: Set axis {axis} wpos to {f}")
        self.app.comms.write(f'G10 L20 P0 {axis.upper()}{f}\n')
        self.app.wpos[i] = f

    def select_wcs(self, v):
        self.app.comms.write(f'{v}\n')

    def reset_axis(self, a):
        # only used for ABC axis
        self.app.comms.write(f'G92 {a}0\n')

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
            self.app.comms.write(f'M220 S{round(self.last_pos, 1)}\n')
            return

        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
            return

        # if in non MPG mode then issue G0 in abs or rel depending on settings
        # if in MPG mode then issue $J commands when they occur
        if not self.ids.mpg_mode_tb.state == 'down':
            # normal mode
            cmd = 'G90' if self.ids.abs_mode_tb.state == 'down' else 'G91'

            # print('{} {}{} {}'.format(cmd1, self.selected_axis, round(self.last_pos, 3), cmd2))
            self.app.comms.write(f'M120 {cmd} G0 {self.selected_axis}{round(self.last_pos, 3)} M121\n')

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
            self.app.comms.write(f'$J {self.selected_axis.upper()}{d}\n')

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
    font_size = NumericProperty('15sp')

    def collide_point(self, x, y):
        return Vector(x, y).distance(self.center) <= self.width / 2


class CircularToggleButton(ToggleButtonBehavior, Widget):
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
    abc_sel = StringProperty('Z')

    def __init__(self, **kwargs):
        super(JogRoseWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.cont_moving = False

    def on_kv_post(self, args):
        self.hat.bind(pad=self.on_hat)

    def _get_speed(self):
        if self.ids.js100.state == 'down':
            return 1.0
        elif self.ids.js50.state == 'down':
            return 0.5
        elif self.ids.js25.state == 'down':
            return 0.25
        elif self.ids.js10.state == 'down':
            return 0.1
        else:
            return 0.5

    def on_hat(self, w, value):
        x, y = value
        axis = None
        if x != 0:
            axis = 'X'
            v = x
        elif y != 0:
            axis = 'Y'
            v = y

        if axis is not None:
            s = self._get_speed()
            # starts continuous jog
            # must not send another $J -c until ok is recieved from previous one
            if not self.cont_moving:
                self.cont_moving = True
                self.app.comms.ok_notify_cb = lambda x: self.got_ok(x)
                self.app.comms.write(f'$J -c {axis}{v} S{s}\n')

    def got_ok(self, f):
        self.cont_moving = False

    def hat_released(self):
        if self.cont_moving:
            self.app.comms.write('\x19')

    def handle_action(self, axis, v):
        if self.app.main_window.is_printing and not self.app.main_window.is_suspended:
            self.app.main_window.display("NOTE: Cannot jog while printing")
            return

        if axis == 'O':
            self.app.comms.write('M120 G21 G90 G0 X0 Y0 M121\n')
        elif axis == 'H':
            self.app.comms.write('$H\n')
        else:
            s = self._get_speed()
            self.app.comms.write(f'$J {axis}{v} S{s}\n')

    def motors_off(self):
        self.app.comms.write('M18\n')

    def safe_z(self):
        self.app.comms.write(f'$J Z{self.app.safez} S{self._get_speed()}\n')


class KbdWidget(GridLayout):
    def __init__(self, **kwargs):
        super(KbdWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def _add_line_to_log(self, s):
        self.app.main_window.display(s)

    def do_action(self, key):
        if key == 'Send':
            # Logger.debug(f"KbdWidget: Sending {self.display.text}")
            if self.display.text.strip():
                self._add_line_to_log(f'<< {self.display.text}')
                self.app.comms.write(f'{self.display.text}\n')
                self.app.last_command = self.display.text
            self.display.text = ''
        elif key == 'Repeat':
            self.display.text = self.app.last_command
        elif key == 'BS':
            self.display.text = self.display.text[:-1]
        elif key == '?':
            self.handle_input('?')
        else:
            self.display.text += key

    def handle_input(self, s):
        self.app.command_input(s)
        if s != '?':
            self.app.last_command = s

        self.display.text = ''


class MainWindow(BoxLayout):
    status = StringProperty('Idle')
    wpos = ListProperty([0, 0, 0])
    eta = StringProperty('Not Streaming')
    is_printing = BooleanProperty(False)
    is_suspended = BooleanProperty(False)
    is_uart_log_enabled = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self._trigger = Clock.create_trigger(self.async_get_display_data)
        self._q = queue.Queue()
        self.config = self.app.config
        self.last_path = self.config.get('General', 'last_gcode_path')
        self.paused = False
        self.last_line = 0
        self.is_sdprint = False
        self.save_console_data = None
        self.uart_log_data = []
        self.is_uart_log_in_view = False
        self.uart_log = None

    def on_touch_down(self, touch):
        if self.ids.log_window.collide_point(touch.x, touch.y):
            if touch.is_triple_tap:
                self.ids.log_window.data = []
                return True

        return super(MainWindow, self).on_touch_down(touch)

    def add_line_to_log(self, s, overwrite=False):
        ''' Add lines to the log window, which is trimmed to the last 200 lines '''
        if self.is_uart_log_in_view:
            # not in view at the moment
            self.save_console_data.append({'text': s})
            return

        max_lines = 200  # TODO needs to be configurable
        n = len(self.ids.log_window.data)
        if overwrite:
            self.ids.log_window.data[n - 1] = ({'text': s})
            return

        self.ids.log_window.data.append({'text': s})
        # we use some hysteresis here so we don't truncate every line added over max_lines
        n = n - max_lines  # how many lines over our max
        if n > 10:
            # truncate log to last max_lines, we delete the oldest 10 or so lines
            del self.ids.log_window.data[0:n]

    def connect(self):
        if self.app.is_connected:
            if self.is_printing:
                mb = MessageBox(text='Cannot Disconnect while printing - Abort first, then wait', cancel_text='OK')
                mb.open()
            else:
                self._disconnect()

        else:
            port = self.config.get('General', 'serial_port')
            self.add_line_to_log(f"Connecting to {port}...")
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
            if self.app.spindle_handler is not None:
                # convert from the PWM to RPM
                self.app.rpm = self.app.spindle_handler.reverse_lookup(self.app.sr)

        if 'L' in d:
            self.app.lp = d['L'][0]

        if 'SD' in d:
            rt = datetime.timedelta(seconds=int(d['SD'][0]))
            self.eta = f"SD: {rt} {d['SD'][1]}%"
            if not self.is_sdprint:
                self.is_sdprint = True
                self.is_printing = True
                self.paused = False
                self.ids.print_but.text = 'Pause'

        else:
            if self.is_sdprint:
                self.eta = 'Not Streaming'
                self.is_sdprint = False
                self.is_printing = False
                self.ids.print_but.text = 'Run'

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

    def ask_shutdown(self, *args):
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
            ports.append(f'serial://{p.device}')

        ports.append('network...')

        sb = SelectionBox(title='Select port', text='Select the port to open from drop down', values=ports, cb=self._change_port)
        sb.open()

    def _change_port(self, s):
        if s:
            Logger.info(f'MainWindow: Selected port {s}')

            if s.startswith('network'):
                mb = InputBox(title='Network address', text='Enter network address as "ipaddress[:port]"', cb=self._new_network_port)
                mb.open()

            else:
                self.config.set('General', 'serial_port', s)
                self.config.write()

    def _new_network_port(self, s):
        if s:
            self.config.set('General', 'serial_port', f'net://{s}')
            self.config.write()

    @mainthread
    def alarm_state(self, msg):
        ''' called when smoothie is in Alarm state (flg == True) or gets an error message (flg == False)'''
        s, was_printing, flg = msg
        if flg:
            self.add_line_to_log(f"! alarm state: {s}")
        else:
            self.add_line_to_log(f"! error message: {s}")

        if self.is_suspended:
            self.add_line_to_log("! NOTE: currently suspended so must Abort as resume will not work")
        elif was_printing:
            if self.app.notify_email:
                notify = Notify()
                notify.send(f'Run in ALARM state: {s}, last Z: {self.wpos[2]}, last line: {self.last_line}')

    def do_kill(self):
        if self.status == 'Alarm':
            self.app.comms.write('$X\n')
        else:
            # are you sure?
            mb = MessageBox(text='KILL - Are you Sure?', cb=self._do_kill)
            mb.open()

    def _do_kill(self, ok):
        if ok:
            if self.is_suspended:
                # we have to abort as well
                self._abort_print(True)
            else:
                self.app.comms.write('\x18')

    def abort_print(self):
        # are you sure?
        mb = MessageBox(text='Abort - Are you Sure?', cb=self._abort_print)
        mb.open()

    def _abort_print(self, ok):
        if ok:
            if self.is_suspended:
                # we have to KILL to get smoothie out of suspend state
                self.is_suspended = False
                self.app.comms.write('\x18')

            self.app.comms.stream_pause(False, True)

    @mainthread
    def action_paused(self, paused, suspended=False):
        # comms layer is telling us we paused or unpaused
        self.ids.print_but.text = 'Resume' if paused else 'Pause'
        self.paused = paused
        self.is_suspended = suspended
        if paused:
            if suspended:
                self.add_line_to_log(">>> Streaming Suspended, Resume or Abort as needed")
                if self.app.notify_email:
                    Notify().send(f'Run has been suspended: last Z: {self.wpos[2]}, last line: {self.last_line}')

            else:
                self.add_line_to_log(">>> Streaming Paused, Abort or Continue as needed")
        else:
            self.add_line_to_log(">>> Streaming Resumed")

    def start_print(self, no_prompt=False):
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

        elif not no_prompt:
            # get file to print
            f = Factory.filechooser()
            f.open(self.last_path, cb=self._start_print)
        else:
            self._start_print()

    def _start_print(self, file_path=None, directory=None):
        # start comms thread to stream the file
        # set comms.ping_pong to False for fast stream mode
        if file_path is None:
            file_path = self.app.gcode_file
        if directory is None:
            directory = self.last_path

        Logger.info(f'MainWindow: printing file: {file_path}')

        try:
            self.nlines = Comms.file_len(file_path, False)  # get number of lines so we can do progress and ETA
            Logger.debug(f'MainWindow: number of lines: {self.nlines}')
        except Exception:
            Logger.warning(f'MainWindow: exception in file_len: {traceback.format_exc()}')
            self.nlines = None

        self.start_print_time = datetime.datetime.now()
        self.display(f'>>> Running file: {file_path}, {self.nlines} lines')

        if self.app.comms.stream_gcode(file_path, progress=lambda x: self.display_progress(x)):
            self.display(f">>> Run started at: {self.start_print_time.strftime('%x %X')}")
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
        mb = MessageBox(text=f'ReRun\n{os.path.basename(self.app.gcode_file)}?', cb=self._reprint)
        mb.open()

    def _reprint(self, ok):
        if ok:
            self._start_print()

    @mainthread
    def start_last_file(self):
        # Will also pause if already printing
        if self.app.gcode_file:
            self.start_print(no_prompt=True)

    def review(self):
        self._show_viewer(self.app.gcode_file, self.last_path)

    def start_uart_log(self):
        if self.is_uart_log_enabled:
            # close it
            if self.uart_log:
                self.uart_log.close()
                self.display('Uart log port closed')
            if self.is_uart_log_in_view:
                self.toggle_uart_view("up")

            self.is_uart_log_enabled = False
            self.uart_log = None
            Logger.info('MainWindow: Closed Uart log port')
            return

        # open it
        ll = self.app.comms.get_ports()
        ports = []
        for p in ll:
            ports.append(f'{p.device}')

        sb = SelectionBox(title='Select Uart log port', text='Select the uart log port to open from drop down', values=ports, cb=self._set_uart_port)
        sb.open()

    @mainthread
    def _uart_log_input(self, dat):
        txt = dat.rstrip()
        Logger.info(f'BOOTLOG: {txt}')
        if dat.startswith('ERROR:') or dat.startswith('FATAL:'):
            txt = f"[color=ff0000]{txt}[/color]"
        elif dat.startswith('WARNING:'):
            txt = f"[color=ffff00]{txt}[/color]"
        elif dat.startswith('INFO:'):
            txt = f"[color=00ff00]{txt}[/color]"
        elif dat.startswith('DEBUG:'):
            txt = f"[color=0000ff]{txt}[/color]"
        else:
            txt = f"[color=ffffff]{txt}[/color]"

        d = {'text': txt}

        self.uart_log_data.append(d)

        if self.is_uart_log_in_view:
            # The uart log is in view
            self.ids.log_window.data.append(d)

    def _set_uart_port(self, s):
        if s:
            Logger.info(f'MainWindow: Selected Uart log port {s}')
            self.uart_log = UartLogger(s)
            if self.uart_log.open(self._uart_log_input):
                self.is_uart_log_enabled = True
                self.display(f'Uart log port {s} open')
            else:
                self.is_uart_log_enabled = False
                self.uart_log = None
                self.display(f'Error unable to open {s} as Uart log port')

    def toggle_uart_view(self, state):
        if state == "down":
            self.save_console_data = []
            for i in self.ids.log_window.data:
                self.save_console_data.append(i)
            self.ids.log_window.data = self.uart_log_data
            self.is_uart_log_in_view = True
        else:
            self.is_uart_log_in_view = False
            self.ids.log_window.data = self.save_console_data
            self.save_console_data = None

    @mainthread
    def stream_finished(self, ok):
        ''' called when streaming gcode has finished, ok is True if it completed '''
        self.ids.print_but.text = 'Run'
        self.is_printing = False
        now = datetime.datetime.now()
        self.display(f">>> Run finished {'ok' if ok else 'abnormally'}")
        self.display(f">>> Run ended at : {now.strftime('%x %X')}, last Z: {self.wpos[2]}, last line: {self.last_line}")
        et = datetime.timedelta(seconds=int((now - self.start_print_time).seconds))
        self.display(f">>> Elapsed time: {et}")
        self.eta = 'Not Streaming'
        if self.app.notify_email:
            notify = Notify()
            notify.send(f"Run finished {'ok' if ok else 'abnormally'}, last Z: {self.wpos[2]}, last line: {self.last_line}")
        Logger.info(f"MainWindow: Run finished {'ok' if ok else 'abnormally'}, last Z: {self.wpos[2]}, last line: {self.last_line}")

    def upload_gcode(self):
        # get file to upload
        f = Factory.filechooser()
        f.open(self.last_path, cb=self._upload_gcode)

    @mainthread
    def _upload_gcode_done(self, ok):
        now = datetime.datetime.now()
        self.display(f">>> Upload finished {'ok' if ok else 'abnormally'}")
        et = datetime.timedelta(seconds=int((now - self.start_print_time).seconds))
        self.display(f">>> Elapsed time: {et}")
        self.eta = 'Not Streaming'
        self.is_printing = False
        self.app.comms.fast_stream = False

    def _upload_gcode(self, file_path, dir_path):
        if not file_path:
            return

        # use built-in fast stream for uploads
        fast_stream = True
        try:
            self.nlines = Comms.file_len(file_path, fast_stream)  # get number of lines so we can do progress and ETA
            Logger.debug(f'MainWindow: number of lines: {self.nlines}')
        except Exception:
            Logger.warning(f'MainWindow: exception in file_len: {traceback.format_exc()}')
            self.nlines = None

        self.start_print_time = datetime.datetime.now()
        self.display(f'>>> Uploading file: {file_path}, {self.nlines} lines')

        # set fast stream mode if requested
        self.app.comms.fast_stream = fast_stream

        if not self.app.comms.upload_gcode(file_path, progress=lambda x: self.display_progress(x), done=self._upload_gcode_done):
            self.display('WARNING Unable to upload file')
            return
        else:
            self.is_printing = True

    def fast_stream_gcode(self):
        # get file to fast stream
        f = Factory.filechooser()
        f.open(self.last_path, cb=self._fast_stream_gcode)

    def _fast_stream_gcode(self, file_path, dir_path):
        if file_path and self.app.fast_stream_cmd:
            cmd = self.app.fast_stream_cmd.replace("{file}", file_path)
            t = threading.Thread(target=self._fast_stream_thread, daemon=True, args=(cmd,))
            t.start()

    def _fast_stream_thread(self, cmd):
        # execute the command
        self.async_display(f"External Fast stream > {cmd}")
        # p = subprocess.Popen(cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # result, err = p.communicate()
        # for l in result.splitlines():
        #     self.async_display(l)
        # for l in err.splitlines():
        #     self.async_display(l)
        # if p.returncode != 0:
        #     self.async_display("error return code: {}".format(p.returncode))

        self.start_print_time = datetime.datetime.now()
        with subprocess.Popen(cmd, shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True) as p:
            while True:
                s = p.stdout.readline()
                if not s:
                    break
                s = s.rstrip()
                if s.startswith('progress: '):
                    # progress: {},{}".format(n, nlines)
                    s = s[10:]
                    n, nlines = s.split(',')
                    self.nlines = int(nlines)
                    self.display_progress(int(n))
                else:
                    self.async_display(s)

        self.display_progress(0)

    @mainthread
    def display_progress(self, n):
        if n == 0:
            self.eta = 'Not Streaming'
            return

        if self.nlines and n <= self.nlines:
            now = datetime.datetime.now()
            d = (now - self.start_print_time).seconds
            if n > 10 and d > 10:
                # we have to wait a bit to get reasonable estimates
                lps = n / d
                eta = (self.nlines - n) / lps
            else:
                eta = 0

            self.eta = f"ETA: {'Paused' if self.paused else datetime.timedelta(seconds=int(eta))} | {n / self.nlines:.1%} | L{n}"

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
            f = f'/sd/{f}'
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
        Logger.info(f"MainWindow: SDcard print: {file_path}")
        self.app.comms.write(f'play {file_path}\n')

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
            Logger.error(f'MainWindow: {traceback.format_exc()}')

    def show_camera_screen(self):
        self.app.sm.current = 'camera'

    @mainthread
    def tool_change_prompt(self, l):
        # Print is paused by gcode command M6, prompt for tool change
        self.display(f"ACTION NEEDED: Manual Tool Change:\n Tool: {l}\nWait for machine to stop, then you can jog around to change the tool.\n tap Resume to continue\n**** REMEMBER to reset Z Height before Resuming ****\n")

    @mainthread
    def m0_dlg(self):
        MessageBox(text='M0 Pause, click OK to continue', cancel_text='OK', cb=self._m0_dlg).open()

    def _m0_dlg(self, ok):
        self.app.comms.release_m0()

    # called by query timer in comms context, return strings for queries to send
    def get_queries(self):
        if not self.app.is_connected or self.is_printing:
            return ""

        if not self.app.is_v2 and self.status in ['Run', 'Home']:
            # FIXME: for v1 we do not send these commands when running as they clog up the USB serial channel
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

    def edit_text(self, *args):
        # get file to view
        f = Factory.filechooser()
        f.open(self.last_path, title='File to Edit', filters=['*'], cb=self._edit_text)

    def _edit_text(self, file_path, directory=None):
        if not self.app.sm.has_screen('text_editor'):
            self.app.text_editor = TextEditor(name='text_editor')
            self.app.sm.add_widget(self.app.text_editor)

        self.app.text_editor.open(file_path)
        self.app.sm.current = 'text_editor'

    def on_previous(self):
        if self.app.is_desktop >= 1:
            Window.minimize()

    def open_tmc_configurator(self, arg=None):
        if not self.app.sm.has_screen('tmc_configurator'):
            tmc_configurator = TMCConfigurator(name='tmc_configurator')
            self.app.sm.add_widget(tmc_configurator)

        self.app.sm.current = 'tmc_configurator'

    def open_calculator(self, arg=None):
        if not self.app.sm.has_screen('calculator'):
            calculator = CalcScreen(name='calculator')
            self.app.sm.add_widget(calculator)

        self.app.sm.current = 'calculator'


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
    rpm = NumericProperty(0)
    is_inch = BooleanProperty(False)
    is_spindle_on = BooleanProperty(False)
    is_abs = BooleanProperty(True)
    tab_top = BooleanProperty(False)
    gcode_file = StringProperty()
    is_show_camera = BooleanProperty(False)
    is_spindle_camera = BooleanProperty(False)

    # Factory.register('Comms', cls=Comms)
    def __init__(self, **kwargs):
        super(SmoothieHost, self).__init__(**kwargs)
        self.main_window = None
        self.manual_tool_change = False
        self.is_v2 = True
        self.wait_on_m0 = False
        self.fast_stream_cmd = ""
        self.is_cnc = False
        self.is_desktop = 0
        self.webserver = False
        self._blanked = False
        self.blank_timeout = 0
        self.last_touch_time = 0
        self.camera_url = None
        self.loaded_modules = []
        self.last_probe = {'X': 0, 'Y': 0, 'Z': 0, 'status': False}
        self.tool_scripts = ToolScripts()
        self.desktop_changed = False
        self.command_history = None
        self.notify_email = False
        self.running_directory = os.path.dirname(os.path.realpath(__file__))
        self.hdmi = False
        self.is_touch = False
        self.minimized = False
        self.safez = 20
        self.last_command = ""
        self.spindle_handler = None
        self.cont_jog = False
        self.use_keypad = False

    def build_config(self, config):
        config.setdefaults('General', {
            'last_gcode_path': os.path.expanduser("~"),
            'last_print_file': '',
            'serial_port': 'serial:///dev/ttyACM0',
            'report_rate': '1.0',
            'blank_timeout': '0',
            'manual_tool_change': 'false',
            'wait_on_m0': 'false',
            'fast_stream_cmd': 'python3 -u comms.py serial:///dev/ttyACM1 {file} -f -q',
            'v2': 'false',
            'is_spindle_camera': 'false',
            'notify_email': 'false',
            'hdmi': 'false',
        })
        config.setdefaults('Jog', {
            'safez': '20'
        })
        config.setdefaults('UI', {
            'display_type': "RPI Touch",
            'cnc': 'false',
            'tab_top': 'false',
            'screen_size': 'auto',
            'screen_pos': 'auto',
            'screen_offset': '0,0',
            'filechooser': 'default',
            'touch_screen': 'false',
            'use_keypad': 'default'
        })
        config.setdefaults('Viewer', {
            'slice': "1.0",
            'vectors': "-1",
        })
        config.setdefaults('Extruder', {
            'last_bed_temp': '60',
            'last_hotend_temp': '185',
            'length': '20',
            'speed': '300',
            'hotend_presets': '185 (PLA), 230 (ABS)',
            'bed_presets': '60 (PLA), 110 (ABS)'
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

                { "type": "options",
                  "title": "Desktop Layout",
                  "desc": "Select Display layout, RPI is for 7in touch screen layout",
                  "section": "UI",
                  "key": "display_type",
                  "options": ["RPI Touch", "RPI Full Screen", "Small Desktop", "Large Desktop", "Wide Desktop"]
                },

                { "type": "bool",
                  "title": "Touch screen",
                  "desc": "Turn on for a touch screen",
                  "section": "UI",
                  "key": "touch_screen"
                },

                { "type": "options",
                  "title": "Use Keypad",
                  "desc": "use arrow keys on keypad to jog",
                  "section": "UI",
                  "key": "use_keypad",
                  "options": ["default", "yes", "no"]
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

                { "type": "string",
                  "title": "Fast Stream Command",
                  "desc": "Fast Stream command line",
                  "section": "General",
                  "key": "fast_stream_cmd"
                },

                { "type": "bool",
                  "title": "Notify via EMail",
                  "desc": "send email when runs finish",
                  "section": "General",
                  "key": "notify_email"
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
        settings.add_json_panel('Smoopi application', self.config, data=jsondata)

    def on_config_change(self, config, section, key, value):
        # print("config changed: {} - {}: {}".format(section, key, value))
        token = (section, key)
        if token == ('UI', 'cnc'):
            was_cnc = self.is_cnc
            self.is_cnc = value == "1"
            self.main_window.ids.macros.reload()
            if was_cnc and not self.is_cnc and self.is_desktop < 3:
                self.main_window.display("NOTICE: May need to Restart to get Extruder panel")
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
        elif token == ('General', 'fast_stream_cmd'):
            self.fast_stream_cmd = value
        elif token == ('General', 'notify_email'):
            self.notify_email = value == '1'
        elif token == ('Jog', 'safez'):
            self.safez = float(value)
        else:
            self.main_window.display("NOTICE: Restart is needed")

    def on_stop(self):
        # The Kivy event loop is about to stop, stop the async main loop
        self.comms.stop()   # stop the aysnc loop
        if self.is_webserver:
            self.webserver.stop()
        if self.is_touch and self.blank_timeout > 0 and self._blanked:
            # unblank if blanked
            self.unblank_screen()
        # stop any loaded modules
        for m in self.loaded_modules:
            m.stop()

    def on_start(self):
        # in case we added something to the defaults, make sure they are written to the ini file
        self.config.update_config(self.config_file)

    def window_request_close(self, win):
        if self.desktop_changed:
            # if the desktop changed we reset the window size and pos
            if self.config.get('UI', 'screen_size') != 'none':
                self.config.set('UI', 'screen_size', 'auto')
            if self.config.get('UI', 'screen_pos') != 'none':
                self.config.set('UI', 'screen_pos', 'auto')

            self.config.write()

        elif self.is_desktop >= 2:
            if self.config.get('UI', 'screen_size') != 'none':
                # Window.size is automatically adjusted for density, must divide by density when saving size
                self.config.set('UI', 'screen_size', f"{int(Window.size[0] / Metrics.density)}x{int(Window.size[1] / Metrics.density)}")

            if self.config.get('UI', 'screen_pos') != 'none':
                # Kivy seems to offset the value given by window managers
                # so this offset will correct for the top and left decorations
                off = self.config.get('UI', 'screen_offset')
                (t, l) = off.split(',')
                top = Window.top - int(t)
                left = Window.left - int(l)
                self.config.set('UI', 'screen_pos', f"{top},{left}")
                Logger.info(f'SmoothieHost: close Window.size: {Window.size}, Window.pos: {top}x{left}')

            self.config.write()

        return False

    def build(self):
        # Logger.debug('SmoothieHost: Backend used is: {}'.format(Window.get_gl_backend_name()))
        self.title = 'Smoopi'
        lt = self.config.get('UI', 'display_type')
        dtlut = {
            "RPI Touch": 0,
            "RPI Full Screen": 1,
            "Small Desktop": 2,
            "Large Desktop": 3,
            "Wide Desktop": 4
        }

        self.is_desktop = dtlut.get(lt, 0)

        # load the layouts
        if self.is_desktop == 1:
            # for full screen xwindows on a small screen (1024x600)
            Builder.load_file('desktop.kv')
            Window.size = (1024, 600)
            self.is_touch = True

        elif self.is_desktop >= 2:
            kvlut = {2: ('desktop.kv', (1024, 610)), 3: ('desktop_large.kv', (1280, 1024)), 4: ('desktop_wide.kv', (1280, 800))}
            Builder.load_file(kvlut[self.is_desktop][0])
            self.is_touch = self.config.getboolean('UI', 'touch_screen')
            if not self.is_touch:
                s = self.config.get('UI', 'screen_size')
                if s == 'auto':
                    Window.size = kvlut[self.is_desktop][1]
                elif 'x' in s:
                    (w, h) = s.split('x')
                    Window.size = (int(w), int(h))

                p = self.config.get('UI', 'screen_pos')
                if p != 'none' and p != 'auto' and ',' in p:
                    (t, l) = p.split(',')
                    Window.top = int(t)
                    Window.left = int(l)
                Window.bind(on_request_close=self.window_request_close)

        else:
            self.is_desktop = 0
            self.is_touch = True
            # load the layouts for rpi 7" touch screen
            Builder.load_file('rpi.kv')

        self.fast_stream_cmd = self.config.get('General', 'fast_stream_cmd')
        self.notify_email = self.config.getboolean('General', 'notify_email')
        self.is_cnc = self.config.getboolean('UI', 'cnc')
        self.tab_top = self.config.getboolean('UI', 'tab_top')
        self.is_webserver = self.config.getboolean('Web', 'webserver')
        self.is_show_camera = self.config.getboolean('Web', 'show_video')
        self.is_spindle_camera = self.config.getboolean('General', 'is_spindle_camera')
        self.manual_tool_change = self.config.getboolean('General', 'manual_tool_change')
        self.wait_on_m0 = self.config.getboolean('General', 'wait_on_m0')
        self.is_v2 = self.config.getboolean('General', 'v2')
        self.hdmi = self.config.getboolean('General', 'hdmi')
        self.safez = self.config.getfloat('Jog', 'safez')
        self.comms = Comms(App.get_running_app(), self.config.getfloat('General', 'report_rate'))
        self.gcode_file = self.config.get('General', 'last_print_file')

        # see if we want to force the use of the keypad
        t_use_keypad = self.config.get('UI', 'use_keypad')
        if t_use_keypad == 'default':
            self.use_keypad = not self.is_touch
        else:
            self.use_keypad = (t_use_keypad == 'yes')

        if self.is_touch:
            self.sm = ScreenManager(transition=NoTransition())
        else:
            self.sm = ScreenManager()

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

        if self.is_touch:
            # RPI touch screen
            # disable overscroll
            # self.main_window.ids.log_window.effect_cls = 'ScrollEffect'
            # self.main_window.ids.log_window.effect_y.friction = 1.0

            self.blank_timeout = self.config.getint('General', 'blank_timeout')
            Logger.info(f"SmoothieHost: screen blank set for {self.blank_timeout} seconds")
            self.sm.bind(on_touch_down=self._on_touch)
            self.sm.bind(on_touch_up=self._on_touch_up)
            self.sm.bind(on_touch_move=self._on_touch_move)

            if self.blank_timeout > 0:
                Clock.schedule_interval(self._every_second, 1)

            if self.is_desktop > 0:
                # remove log window entry widget
                self.main_window.ids.entry.focus = False
                self.main_window.ids.blleft.remove_widget(self.main_window.ids.entry)
                # add text editor tool to menu
                self.main_window.tools_menu.add_widget(ActionButton(text='Text Editor', on_press=self.main_window.edit_text))

                # add blanker
                if self.blank_timeout > 0:
                    self.main_window.system_menu.add_widget(ActionButton(text='Blank Screen', on_press=self.blank_screen))
                # add shutdown
                self.main_window.system_menu.add_widget(ActionButton(text='Shutdown', on_press=self.main_window.ask_shutdown))

                Window.bind(on_minimize=self._on_minimize)
                Window.bind(on_restore=self._on_restore)

        # select the file chooser to use
        # select which one we want from config
        filechooser = self.config.get('UI', 'filechooser')
        if not self.is_touch:
            if filechooser != 'default':
                NativeFileChooser.type_name = filechooser
                Factory.register('filechooser', cls=NativeFileChooser)
                try:
                    f = Factory.filechooser()
                except Exception:
                    Logger.error(f"SmoothieHost: can't use selected file chooser: {filechooser}")
                    Factory.unregister('filechooser')
                    Factory.register('filechooser', cls=FileDialog)

            else:
                # use Kivy filechooser
                Factory.register('filechooser', cls=FileDialog)

            if self.is_desktop > 1:
                # remove KBD tab
                self.main_window.ids.tabs.remove_widget(self.main_window.ids.tabs.console_tab)

        else:
            # use Kivy filechooser
            Factory.register('filechooser', cls=FileDialog)

        if self.use_keypad:
            # we want to capture arrow keys
            Window.bind(on_key_down=self._on_keyboard_down)
            Window.bind(on_key_up=self._on_keyboard_up)

        # setup for cnc or 3d printer
        if self.is_cnc:
            if self.is_desktop <= 3:
                # remove Extruder panel from tabpanel and tab
                self.main_window.ids.tabs.remove_widget(self.main_window.ids.tabs.extruder_tab)
            elif self.is_desktop == 4:
                # remove from panel
                self.main_window.ids.blright.remove_widget(self.main_window.ids.extruder_tab)

            # see if a spindle handler is enabled to translate the spindle speeds to PWM
            self.spindle_handler = SpindleHandler()
            if not self.spindle_handler.load():
                self.spindle_handler = None

        # if not CNC mode then do not show the ZABC buttons in jogrose
        if not self.is_cnc:
            self.main_window.ids.tabs.jog_rose.jogrosemain.remove_widget(self.main_window.ids.tabs.jog_rose.abc_panel)

        if self.is_webserver:
            self.webserver = ProgressServer()
            self.webserver.start(self, 8000)

        # add calculator to menu
        self.main_window.tools_menu.add_widget(ActionButton(text='Calculator', on_press=self.main_window.open_calculator))

        if self.is_show_camera:
            self.camera_url = self.config.get('Web', 'camera_url')
            self.sm.add_widget(CameraScreen(name='web cam'))
            self.main_window.tools_menu.add_widget(ActionButton(text='Web Cam', on_press=self._show_web_cam))

        if self.is_spindle_camera:
            ok = True
            if self.is_desktop <= 1:
                try:
                    self.sm.add_widget(SpindleCamera(name='spindle camera'))
                except Exception as err:
                    self.main_window.display('ERROR: failed to load spindle camera. Check logs')
                    Logger.error(f'Main: spindle camera exception: {err}')
                    ok = False

            if ok:
                self.main_window.tools_menu.add_widget(ActionButton(text='Spindle Cam', on_press=self._show_spindle_cam))

        if self.is_v2:
            self.main_window.tools_menu.add_widget(ActionButton(text='Set Datetime', on_press=self.tool_scripts.set_datetime))
            self.main_window.tools_menu.add_widget(ActionButton(text='TMC Config', on_press=self.main_window.open_tmc_configurator))

        # load any modules specified in config
        self._load_modules()

        if self.is_touch and self.blank_timeout > 0:
            # unblank if blanked
            self.unblank_screen()

        return self.sm

    def set_screen(self, s):
        self.sm.current = s

    def _show_spindle_cam(self, args=None):
        if self.is_desktop <= 1:
            self.sm.current = "spindle camera"
        else:
            # In desktop mode we run it as a separate window
            SpindleCamera.run_standalone(App.get_running_app())

    def _show_web_cam(self, args=None):
        self.sm.current = "web cam"

    def _on_keyboard_up(self, instance, key, scancode):
        # print("UP key: {}, scancode: {}".format(key, scancode))
        if self.cont_jog:
            self.cont_jog = False
            self.comms.write('\x19')

    def _on_keyboard_down(self, instance, key, scancode, codepoint, modifiers):
        # print("DOWN key: {}, scancode: {}, codepoint: {}, modifiers: {}".format(key, scancode, codepoint, modifiers))

        # if already in continuous jog ignore repeats
        if self.cont_jog:
            return True

        # control uses finer move, shift uses coarse move, alt does continuous jog until released
        v = 0.1

        if len(modifiers) >= 1:
            if 'ctrl' in modifiers:
                v = 0.01
            elif 'shift' in modifiers:
                v = 1
            elif 'alt' in modifiers:
                v = 1
                self.cont_jog = True

        choices = {
            273: f"Y{v}",
            275: f"X{v}",
            274: f"Y{-v}",
            276: f"X{-v}",
            280: f"Z{v}",
            281: f"Z{-v}",
        }
        '''
        # keypad keys
            264: f"Y{v}",
            262: f"X{v}",
            258: f"Y{-v}",
            260: f"X{-v}",
            265: f"Z{v}",
            259: f"Z{-v}",
        '''

        s = choices.get(key, None)
        if s is not None:
            if not (self.main_window.is_printing and not self.main_window.is_suspended):
                if self.cont_jog:
                    self.comms.write(f'$J -c {s}\n')
                else:
                    self.comms.write(f'$J {s}\n')
            else:
                self.cont_jog = False

            return True

        else:
            self.cont_jog = False

        # handle command history if in desktop mode
        if self.is_desktop > 1:
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
            self.main_window.display(f'> {s}')
            try:
                p = subprocess.Popen(s[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
                result, err = p.communicate(timeout=10)
                for l in result.splitlines():
                    self.main_window.display(l)
                for l in err.splitlines():
                    self.main_window.display(l)
                if p.returncode != 0:
                    self.main_window.display(f'returncode: {p.returncode}')
            except subprocess.TimeoutExpired:
                p.kill()
                self.main_window.display('> command timed out')
            except Exception as err:
                self.main_window.display(f'> command exception: {err}')

        elif s == '?':
            self.sm.current = 'gcode_help'

        else:
            self.main_window.display(f'<< {s}')
            self.comms.write(f'{s}\n')

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
                Logger.info(f"load_modules: loading module {key}")
                mod = importlib.import_module(f'modules.{key}')
                if mod.start(self.config['modules'][key]):
                    Logger.info(f"load_modules: loaded module {key}")
                    self.loaded_modules.append(mod)
                else:
                    Logger.info(f"load_modules: module {key} failed to start")

        except Exception:
            Logger.warn(f"load_modules: exception: {traceback.format_exc()}")

    def _every_second(self, dt):
        ''' called every second if blanking is enabled '''
        if self.minimized:
            # don't blank if minimized
            return

        if not self.is_touch:
            # we don't blank desktops
            return

        if self.blank_timeout > 0:
            if self.sm.current != 'main' or self.main_window.is_printing:
                # don't blank unless we are on main screen and not printing
                self.last_touch_time = 0

            elif not self._blanked:
                self.last_touch_time += 1
                if self.last_touch_time >= self.blank_timeout:
                    self.last_touch_time = 0
                    self.blank_screen()

    def blank_screen(self, *args):
        try:
            if self.hdmi:
                os.system("vcgencmd display_power 0")
            else:
                with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                    f.write('1\n')
            self._blanked = True
        except Exception:
            Logger.warning("SmoothieHost: unable to blank screen")

    def unblank_screen(self):
        try:
            if self.hdmi:
                os.system("vcgencmd display_power 1")
            else:
                with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                    f.write('0\n')
            self._blanked = False
        except Exception:
            pass

    def _on_touch(self, a, b):
        if self.minimized:
            return True

        if self.blank_timeout > 0:
            self.last_touch_time = 0
            if self._blanked:
                self._blanked = False
                self.unblank_screen()
                return True

        return False

    def _on_touch_up(self, a, b):
        if self.minimized:
            return True
        return False

    def _on_touch_move(self, a, b):
        if self.minimized:
            return True
        return False

    def _on_minimize(self, *args):
        self.minimized = True

    def _on_restore(self, *args):
        self.minimized = False

    def get_application_config(self):
        # allow a command line argument to select a different config file to use
        if(len(sys.argv) > 1):
            ext = sys.argv[1]
            self.config_file = f'{self.directory}/{self.name}-{ext}.ini'
        else:
            self.config_file = f'{self.directory}/{self.name}.ini'

        Logger.info(f"SmoothieHost: config file is: {self.config_file}")
        return super(SmoothieHost, self).get_application_config(defaultpath=self.config_file)

    def display_settings(self, settings):
        if not self.sm.has_screen('settings_screen'):
            settings_screen = Screen(name='settings_screen')
            settings_screen.add_widget(settings)
            self.sm.add_widget(settings_screen)

        self.sm.current = 'settings_screen'
        return True

    def close_settings(self, *largs):
        self.sm.current = 'main'


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
