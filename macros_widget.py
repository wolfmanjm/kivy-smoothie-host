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
import re

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
                    io= config.getboolean(section, 'io', fallback=False)
                    btn = Factory.MacroButton()
                    btn.text= name
                    btn.background_color= (1,1,0,1)
                    btn.bind(on_press= partial(self.exec_script, script, io, args))
                    self.add_widget(btn)

            # add simple macro buttons (with optional prompts)
            for (key, v) in config.items('macro buttons'):
                btn = Factory.MacroButton()
                btn.text= key
                btn.bind(on_press= partial(self.send, v))
                self.add_widget(btn)

        except Exception as err:
            Logger.warning('MacrosWidget: WARNING - exception parsing config file: {}'.format(err))

    def new_macro(self):
        o = MultiInputBox(title='Add Macro')
        o.setOptions(['Name', 'Command'], self._new_macro)
        o.open()

    def _new_macro(self, opts):
        if opts and opts['Name'] and opts['Command']:
            btn = Factory.MacroButton()
            btn.text= opts['Name']
            btn.bind(on_press= partial(self.send, opts['Command']))
            self.add_widget(btn)
            # write it to macros.ini
            try:
                config = configparser.ConfigParser()
                config.read('macros.ini')
                if not config.has_section("macro buttons"):
                    config.add_section("macro buttons")
                config.set("macro buttons", opts['Name'], opts['Command'])
                with open('macros.ini', 'w') as configfile:
                    config.write(configfile)

                Logger.info('MacrosWidget: added macro button {}'.format(opts['Name']))

            except Exception as err:
                Logger.error('MacrosWidget: ERROR - exception writing config file: {}'.format(err))


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

    def _substitute_args(self, m, arg):
        """ substitute {?prompt}) with prompted value """

        # get arguments to prompt for
        v= [x[2:-1] for x in m]

        mb = MultiInputBox(title="Arguments for {}".format(arg))
        mb.setOptions(v, partial(self._do_substitute_exec, m, arg))
        mb.open()

    def _do_substitute_exec(self, m, arg, opts):
        for i in m:
            v= opts[i[2:-1]]
            if v:
                arg= arg.replace(i, v)
            else:
                self.app.main_window.async_display("ERROR: argument missing for {}".format(i))
                return

        self.app.comms.write('{}\n'.format(arg))

    def send(self, cmd, *args):
        # look for {?prompt}) and substitute entered value if found
        m= re.findall(r'\{\?[^}]+\}', cmd)
        if m:
            self._substitute_args(m, cmd)
        else:
            # plain command just send it
            self.app.comms.write('{}\n'.format(cmd))

    def exec_script(self, cmd, io, params, *args):
        if params is not None:
            l= params.split(',')
            mb = MultiInputBox(title='Arguments')
            mb.setOptions(l, partial(self._exec_script_params, cmd, io))
            mb.open()

        else:
            self._exec_script(cmd, io)

    def _exec_script_params(self, cmd, io, opts):
        for x in opts:
            cmd += " " + x + " " + opts[x]

        self._exec_script(cmd, io)

    def _exec_script(self, cmd, io):
        # needs to be run in a thread
        t= threading.Thread(target=self._script_thread, daemon=True, args=(cmd,io,))
        t.start()

    def _send_it(self, p, x):
        p.stdin.write("{}\n".format(x))
        #print("{}\n".format(x))

    def _script_thread(self, cmd, io):
        try:
            if io:
                if not self.app.is_connected:
                    Logger.error('MacrosWidget:  Not connected')
                    self.app.main_window.async_display('> not connected')
                    io= False
                    return

                repeating= False
                if cmd.startswith('-'):
                    # repeating output on same line
                    repeating= True
                    cmd= cmd[1:]

                # I/O is piped to/from smoothie
                self.app.main_window.async_display("> running script: {}".format(cmd))
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True, bufsize=1)
                self.app.comms.redirect_incoming(lambda x: self._send_it(p, x))

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
                                if not repeating:
                                    self.app.main_window.async_display("<<< script: {}".format(s.rstrip()))
                                self.app.comms.write('{}'.format(s))

                        elif pr[0] == p.stderr.name:
                            e= p.stderr.readline()
                            if e:
                                if repeating:
                                    self.app.main_window.async_display('{}\r'.format(e.rstrip()))
                                else:
                                    self.app.main_window.async_display('>>> script: {}'.format(e.rstrip()))

                    p.poll()

                self.app.main_window.async_display('> script complete')
            else:
                # just display results
                self.app.main_window.async_display("> {}".format(cmd))
                p = subprocess.Popen(cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                result, err = p.communicate()
                for l in result.splitlines():
                    self.app.main_window.async_display(l)
                for l in err.splitlines():
                    self.app.main_window.async_display(l)
                if p.returncode != 0:
                    self.app.main_window.async_display("return code: {}".format(p.returncode))

        except Exception as err:
                Logger.error('MacrosWidget: script exception: {}'.format(err))
                self.app.main_window.async_display('>>> script exception, see log')

        finally:
            if io and self.app.is_connected:
                self.app.comms.redirect_incoming(None)
