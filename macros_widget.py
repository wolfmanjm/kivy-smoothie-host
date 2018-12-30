import kivy

from kivy.app import App
from kivy.logger import Logger
from kivy.uix.stacklayout import StackLayout
from kivy.config import ConfigParser
from kivy.clock import Clock, mainthread
from kivy.factory import Factory
from multi_input_box import MultiInputBox

import configparser
from functools import partial
import subprocess
import threading
import select

'''
user defined macros are configurable and stored in a configuration file called macros.ini
format is:-
button name = command to send
'''
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
                if section.startswith('toggle button '):
                    name= config.get(section, 'name', fallback=None)
                    poll= config.getboolean(section, 'poll', fallback=False)
                    lon= config.get(section, 'label on', fallback=None)
                    loff= config.get(section, 'label off', fallback=None)
                    cmd_on= config.get(section, 'command on', fallback=None)
                    cmd_off= config.get(section, 'command off', fallback=None)
                    if name is None or lon is None or loff is None or cmd_on is None or cmd_off is None:
                        Logger.error("MacrosWidget: config error - {} is invalid".format(section))
                        continue

                    tbtn = Factory.MacroToggleButton()
                    tbtn.text= lon
                    self.toggle_buttons[name]= (lon, loff, cmd_on, cmd_off, tbtn, poll)
                    tbtn.bind(on_press= partial(self._handle_toggle, name))
                    self.add_widget(tbtn)

                elif section.startswith('script '):
                    name= config.get(section, 'name', fallback=None)
                    script= config.get(section, 'exec', fallback=None)
                    args= config.get(section, 'args', fallback=None)
                    btn = Factory.MacroButton()
                    btn.text= name
                    btn.background_color= (1,1,0,1)
                    btn.bind(on_press= partial(self.exec_script, script, args))
                    self.add_widget(btn)

            # add simple macro buttons
            for (key, v) in config.items('macro buttons'):
                btn = Factory.MacroButton()
                btn.text= key
                btn.bind(on_press= partial(self.send, v))
                self.add_widget(btn)

        except Exception as err:
            Logger.warning('MacrosWidget: ERROR - exception parsing config file: {}'.format(err))

    def update_buttons(self):
        # check the state of the toggle macro buttons that have poll set, called when we switch to the macro window
        # we send the new $S command so it gets processed immediately despite being busy
        cmd= "$S"
        for name in self.toggle_buttons:
            if self.toggle_buttons[name][5]: # if poll is set
                cmd += " "
                cmd += name

        if len(cmd) <= 3:
            cmd= ""
        else:
            cmd += "\n"

        return cmd

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

    def exec_script(self, cmd, params, *args):
        if params is not None:
            l= params.split(',')
            mb = MultiInputBox(inputs= l, cb=partial(self._exec_script_params, cmd))
            mb.init()

        else:
            self._exec_script(cmd)

    def _exec_script_params(self, cmd, w):
        for x in w.values:
            cmd += " " + x

        self._exec_script(cmd)

    def _exec_script(self, cmd):
        # needs to be run in a thread
        t= threading.Thread(target=self._script_thread, daemon=True, args=(cmd,))
        t.start()

    def _send_it(self, p, x):
        p.stdin.write("{}\n".format(x))
        #print("{}\n".format(x))

    def _script_thread(self, cmd):
        Logger.info("MacrosWidget: running script: {}".format(cmd))
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True, bufsize=1)
            self.app.comms._reroute_incoming_data_to= lambda x: self._send_it(p, x)

            # so we can see which has output
            poll_obj = select.poll()
            poll_obj.register(p.stdout, select.POLLIN)
            poll_obj.register(p.stderr, select.POLLIN)

            while p.returncode is None:
                poll_result = poll_obj.poll(0)
                for pr in poll_result:
                    if pr[0] == p.stdout.name:
                        s= p.stdout.readline()
                        if s:
                            self.app.main_window.async_display("<<< script: {}".format(s.rstrip()))
                            self.app.comms.write('{}'.format(s))
                    elif pr[0] == p.stderr.name:
                        e= p.stderr.readline()
                        if e:
                            Logger.debug("MacrosWidget: script stderr: {}".format(e))
                            self.app.main_window.async_display('>>> script: {}'.format(e.rstrip()))

                p.poll()

        except Exception as err:
                Logger.error('MacrosWidget: script exception: {}'.format(err))
                self.app.main_window.async_display('>>> script exception, see log')

        finally:
            self.app.comms._reroute_incoming_data_to= None